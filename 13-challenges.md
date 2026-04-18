# 13. Challenges — Real-World Engineering Problems with ADK Agents

*Different from Limitations (#6): Limitations = framework bugs/missing features. Challenges = hard engineering problems you face building production agents.*

## The 12 Challenges

| # | Challenge | Severity | ADK Built-in | You Must Build |
|---|-----------|----------|-------------|----------------|
| 1 | Non-determinism | Critical | Eval framework | Statistical testing, model pinning |
| 2 | Debugging multi-agent | High | Dev UI, OTel | Production tracing |
| 3 | Prompt brittleness | High | Code-first design | Prompt versioning, regression gates |
| 4 | Hallucination management | Critical | Grounding tools | Input validation, defense-in-depth |
| 5 | Cost explosion in loops | High | `max_iterations` | Token budgets, monitoring |
| 6 | State management complexity | High | State scoping | Key conventions, staleness checks |
| 7 | Tool reliability | Critical | ReflectAndRetryPlugin | Circuit breakers, timeouts |
| 8 | Context window overflow | Medium | Event compaction | Token-based compaction |
| 9 | Agent evaluation | High | Golden datasets | CI/CD integration |
| 10 | Production incidents | Critical | None | Retry, session isolation, alerting |
| 11 | Migration challenges | Medium | Semver, changelog | Version pinning, schema backup |
| 12 | Team collaboration | Medium | Code-first | Prompt review process |

---

## 1. Non-Determinism

Same query → different tool calls, different reasoning, different answer every time.

**Impact:** Traditional `assertEqual` testing is meaningless. CI/CD is flaky.

**Mitigations:**
- **Pin model versions:** `gemini-2.5-flash-preview-05-20` not `gemini-2.5-flash`
- **Trajectory evaluation:** Check the *process* (which tools called), not just the answer
- **Statistical testing:** Run N times, assert 90%+ pass rate
- **Temperature=0** for testing (still not fully deterministic)

## 2. Debugging Multi-Agent Systems

When a 5-agent pipeline fails, which agent went wrong?

**Tools:**
- `adk web` Dev UI — event timeline + trace waterfall (dev only)
- OpenTelemetry spans — automatic for every agent/tool/LLM call
- `before_agent_callback` — custom trace logging
- **Gap:** No production-grade distributed tracing (need Arize/AgentOps/LangWatch)

## 3. Prompt Brittleness

Adding "Be concise" to instructions causes agent to skip calling verification tools.

**Mitigations:**
- **Decompose** monolithic agents into specialized sub-agents (5-10 rules each)
- **Version control** prompts as separate files
- **Regression testing** with golden datasets on every prompt change
- **Structured output** (`output_schema`) to constrain behavior

## 4. Hallucination Management

Agents don't just generate wrong text — they call the **wrong tools** with **fabricated parameters**.

**Categories:**
1. Tool selection hallucination (calls `delete_user` instead of `deactivate_user`)
2. Parameter fabrication (invents order IDs that don't exist)
3. Result misinterpretation (tool says "failed", agent tells user "success")

**Defense-in-depth:**
```python
# Validate tool inputs BEFORE execution
def safe_transfer(amount: float, to_account: str, tool_context) -> dict:
    if to_account not in get_valid_accounts():
        return {"error": f"Unknown account: {to_account}"}
    return execute_transfer(amount, to_account)
```

## 5. Cost Explosion in Loops

`LoopAgent` is a cost multiplier. 10 iterations × 4 sub-agents = 40 LLM calls.

**Known issues:**
- LoopAgent stuck in infinite loop ([#1100](https://github.com/google/adk-python/issues/1100))
- `exit_loop` called but never exits ([#2988](https://github.com/google/adk-python/issues/2988))
- `escalate` propagates ALL the way up, skipping subsequent pipeline steps ([#2808](https://github.com/google/adk-python/issues/2808))

**Critical:** Always set `max_iterations`. There is no default.

## 6. State Management Complexity

All agents share `session.state`. In `ParallelAgent`, this creates race conditions.

**Rules:**
- Each parallel agent must write to a **unique key** (`agent_a:result`, `agent_b:result`)
- Never store non-serializable objects in state
- Validate state freshness (add timestamps, check staleness)
- Use `temp:` prefix for ephemeral data

## 7. Tool Reliability

A single API failure crashes the entire multi-agent workflow. No built-in retry.

**Patterns:**
- `tenacity` for exponential backoff
- Circuit breaker pattern (3 failures → stop trying for 60s)
- `ReflectAndRetryToolPlugin` — tells LLM what went wrong, lets it try different approach
- Always set tool execution timeouts

## 8. Context Window Overflow

Long conversations accumulate events → exceed model's context window.

**Strategies:**
- `GetSessionConfig(num_recent_events=20)` — only load recent events
- `SlidingWindowCompactionConfig` — auto-summarize old events (experimental)
- Summarize tool outputs before returning (5000-token API response → 500-token summary)
- Use `session.state` for persistent data instead of conversation history

## 9. Agent Evaluation

"How do I know my agent is good?" is harder than testing traditional software.

**ADK evaluation metrics:**

| Metric | What It Measures |
|--------|-----------------|
| `tool_trajectory_avg_score` | Right tools in right order? |
| `response_match_score` (ROUGE) | Word overlap with expected answer |
| `final_response_match_v2` | Semantic equivalence (LLM judge) |
| `hallucinations_v1` | Is each sentence grounded? |
| `safety_v1` | Harmlessness |

**CI/CD pipeline:**
```
PR touches prompt/tools → adk eval golden_dataset.json → score drops → BLOCK merge
```

## 10. Production Incidents

### 429 Cascade
Rate limit → error corrupts session context → subsequent queries resume failed workflow → wrong execution path.
**Fix:** Create new sessions after errors. Never reuse a 429'd session.

### Infinite Loops
Agent calls same tool with same params forever. Often triggered by `output_schema` + tools.
**Fix:** `max_iterations`, token budget tracking, loop detection in callbacks.

### Model Version Changes
Google silently updates `gemini-2.5-flash` alias. Agent breaks Monday with no code changes.
**Fix:** Pin specific versions. Run golden dataset eval on a schedule.

## 11. Migration Challenges

ADK v1.14, v1.17, v1.19 all broke database schemas with no migration scripts. v1.0.0 moved all services to async, requiring rewrites.

**Rules:**
- Pin `google-adk==1.31.0` in requirements.txt (never `>=`)
- Always backup database before upgrading
- Read CHANGELOG before every version bump
- Test upgrades in staging with production data clone

## 12. Team Collaboration

**Prompt review checklist for PRs:**
1. Has the golden dataset been updated?
2. Has `adk eval` been run?
3. Are there new edge cases needing test coverage?
4. Does the change affect sub-agent delegation?
5. Is it backward-compatible with existing state keys?

**Project structure:**
```
agents/order_agent/
  __init__.py, instructions.py, tools.py, eval_data/golden_dataset.json
shared/callbacks.py, state_utils.py
tests/test_order_agent.py
```
