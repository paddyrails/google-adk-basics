"""My first ADK agent — a helpful coding assistant."""

from google.adk.agents import LlmAgent

def explain_code(code: str) -> dict:
    """Analyzes and explains a piece of code.

    Args:
        code: The code snippet to explain.

    Returns:
        dict with the explanation.
    """
    return {
        "status": "success",
        "language": "detected",
        "lines": len(code.strip().split("\n")),
        "note": "The LLM will provide the actual explanation using this metadata."
    }

def suggest_improvement(code: str) -> dict:
    """Suggests improvements for a piece of code.

    Args:
        code: The code snippet to improve.

    Returns:
        dict with improvement suggestions.
    """
    return {
        "status": "success",
        "note": "The LLM will provide actual suggestions based on the code."
    }

root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="code_assistant",
    description="A coding assistant that explains and improves code",
    instruction="""You are a helpful coding assistant. You can:
1. Explain code snippets using the explain_code tool
2. Suggest improvements using the suggest_improvement tool

Be concise and practical in your responses.""",
    tools=[explain_code, suggest_improvement],
)
