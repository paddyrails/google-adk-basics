# 10. Security — API Keys, PII, Auth, Compliance, Audit

## Security Layers in ADK

The 4 callback hooks are your primary interception points:
- `before_model_callback` → Input validation, PII redaction, injection detection
- `after_model_callback` → Output filtering, PII scanning
- `before_tool_callback` → Authorization, argument validation
- `after_tool_callback` → Field-level filtering, audit logging

## 1. API Key Management
- **Dev**: `.env` file with `GOOGLE_API_KEY`
- **Production**: Google Secret Manager with IAM-controlled access
- **Best**: Use Vertex AI (`GOOGLE_GENAI_USE_VERTEXAI=True`) — no API key needed, IAM handles auth
- **GKE**: Workload Identity Federation (no JSON key files)

## 2. PII Handling
```python
def pii_before_model(callback_context, llm_request, **kwargs):
    for content in llm_request.contents:
        for part in content.parts:
            if re.search(r"\b\d{3}-\d{2}-\d{4}\b", part.text):  # SSN
                part.text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN_REDACTED]", part.text)
    return None  # Proceed with redacted content
```
- Production: Use Google Cloud DLP API for robust detection
- GDPR: `session_service.delete_session()` for right to erasure

## 3. Prompt Injection Defense
```python
INJECTION_PATTERNS = [
    r"ignore.*previous.*instructions",
    r"you are now",
    r"reveal.*system.*prompt",
]
# Check in before_model_callback, return Content to block
```

## 4. Authorization (RBAC)
```python
def auth_before_tool(tool, args, tool_context, **kwargs):
    role = tool_context.state.get("user:role", "viewer")
    if tool.name == "delete_record" and role != "admin":
        return {"error": "Permission denied"}
    return None
```

## 5. Data Residency
- **Vertex AI**: Set `GOOGLE_CLOUD_LOCATION` — data stays in that region
- **Sessions**: Your database, your region (Cloud SQL in same region)
- **VPC Service Controls**: Network-level enforcement against data exfiltration

## 6. Compliance

| What Google Provides (Vertex AI) | What You Implement |
|---|---|
| SOC 1/2/3, ISO 27001 | RBAC in callbacks |
| HIPAA BAA (must sign) | PII handling, data minimization |
| Encryption at rest (AES-256) | Audit logging |
| Encryption in transit (TLS 1.3) | Session retention policies |
| CMEK support | Input validation |

## 7. Audit Logging
```python
def audit_before_tool(tool, args, tool_context, **kwargs):
    audit.log("tool_invocation", tool=tool.name, user=tool_context.session.user_id,
              session=tool_context.session.id, args=sanitize(args))
    return None
```

## 8. Secure Deployment Checklist
1. `--no-allow-unauthenticated` on Cloud Run
2. VPC connector with `--vpc-egress=all-traffic`
3. Non-root container user
4. Read-only root filesystem (`readOnlyRootFilesystem: true`)
5. Drop all capabilities (`capabilities: drop: ["ALL"]`)
6. Network policies restricting pod communication
7. Security headers (HSTS, X-Frame-Options, CSP)
8. Rate limiting middleware
