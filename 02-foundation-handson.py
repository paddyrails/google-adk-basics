"""
02 - Foundation Hands-On: Google ADK Core Concepts
===================================================
Demonstrates: LlmAgent, Tools, Sessions, State, Runner, Callbacks, Events

Scenario: A "Smart Assistant" that can:
  1. Look up employee info (custom FunctionTool)
  2. Track how many tool calls were made (state + callbacks)
  3. Log every LLM call (before_model_callback)
  4. Process and display the event stream
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()  # Load GOOGLE_API_KEY from .env

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.tools import FunctionTool
from google.genai import types

# ============================================================
# 1. TOOLS — Custom FunctionTool
# ============================================================
# Docstrings are critical — the LLM reads them to decide when to call the tool.
# Type hints are required — they generate the function call schema.

EMPLOYEE_DB = {
    "alice": {"name": "Alice Johnson", "role": "Senior Engineer", "department": "Platform", "salary_band": "L6"},
    "bob": {"name": "Bob Smith", "role": "Product Manager", "department": "Growth", "salary_band": "L5"},
    "carol": {"name": "Carol Lee", "role": "Data Scientist", "department": "ML", "salary_band": "L6"},
}

def lookup_employee(employee_id: str) -> dict:
    """Looks up employee information by their employee ID.

    Args:
        employee_id: The employee's ID (e.g., 'alice', 'bob', 'carol').

    Returns:
        dict with employee details or an error message.
    """
    emp = EMPLOYEE_DB.get(employee_id.lower())
    if emp:
        return {"status": "found", **emp}
    return {"status": "not_found", "error": f"No employee with ID '{employee_id}'"}


def list_all_employees() -> dict:
    """Lists all available employee IDs in the system.

    Returns:
        dict with a list of employee IDs.
    """
    return {"employees": list(EMPLOYEE_DB.keys())}


# ============================================================
# 2. CALLBACKS — Intercept LLM calls and tool executions
# ============================================================

def before_model_callback(callback_context, llm_request, **kwargs):
    """Called before every LLM call. Logs the call and returns None to proceed."""
    call_count = callback_context.state.get("llm_call_count", 0) + 1
    callback_context.state["llm_call_count"] = call_count
    print(f"\n  [before_model] LLM call #{call_count}")
    # Return None = proceed with LLM call
    return None


def after_tool_callback(tool, args, tool_context, tool_response, **kwargs):
    """Called after every tool execution. Tracks tool usage in state."""
    tool_count = tool_context.state.get("tool_call_count", 0) + 1
    tool_context.state["tool_call_count"] = tool_count
    print(f"  [after_tool] Tool '{tool.name}' call #{tool_count} completed")
    # Return None = use original tool result
    return None


# ============================================================
# 3. AGENT — LlmAgent with instructions, tools, and callbacks
# ============================================================

agent = LlmAgent(
    name="hr_assistant",
    model="gemini-2.5-flash",
    instruction="""You are an HR assistant that helps look up employee information.

You have access to an employee database. When asked about employees:
1. Use list_all_employees to show available IDs
2. Use lookup_employee to get details about a specific employee

Be concise and professional in your responses.""",
    description="An HR assistant that looks up employee information",  # Used by other agents for routing
    tools=[lookup_employee, list_all_employees],
    before_model_callback=before_model_callback,
    after_tool_callback=after_tool_callback,
)

# ============================================================
# 4. RUNNER + SESSION — Execute and process events
# ============================================================

async def run_conversation():
    """Runs a multi-turn conversation demonstrating sessions, state, and events."""

    # InMemoryRunner = convenience wrapper (creates InMemorySessionService + InMemoryArtifactService)
    runner = InMemoryRunner(agent=agent, app_name="hr_app")

    user_id = "user_001"
    session_id = "session_001"

    # Create a session with initial state
    session = await runner.session_service.create_session(
        app_name="hr_app",
        user_id=user_id,
        session_id=session_id,
        state={"user:name": "Paddy", "user:role": "Senior Engineer"}  # Pre-loaded state
    )

    print("=" * 60)
    print("Foundation Hands-On: HR Assistant Agent")
    print("=" * 60)

    # --- Turn 1: Simple query ---
    queries = [
        "Who are all the employees in the system?",
        "Tell me about Alice",
        "Compare Alice and Bob's departments",
    ]

    for i, query in enumerate(queries, 1):
        print(f"\n{'─' * 60}")
        print(f"👤 Turn {i}: {query}")
        print(f"{'─' * 60}")

        msg = types.Content(role="user", parts=[types.Part(text=query)])

        # run_async returns AsyncGenerator[Event, None]
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=msg,
        ):
            # ── EVENT PROCESSING ──
            # Each event has: author, content, actions, partial, turn_complete

            if event.partial:
                # Streaming chunk — skip for cleaner output
                continue

            if event.content and event.content.parts:
                for part in event.content.parts:
                    # Tool call event
                    if part.function_call:
                        print(f"  🛠️  Tool call: {part.function_call.name}({part.function_call.args})")

                    # Tool response event
                    elif part.function_response:
                        print(f"  📦 Tool result: {part.function_response.response}")

                    # Text response
                    elif part.text and event.is_final_response():
                        print(f"\n  🤖 Agent: {part.text}")

    # ── SESSION STATE INSPECTION ──
    print(f"\n{'=' * 60}")
    print("Session State After Conversation:")
    print(f"{'=' * 60}")
    final_session = await runner.session_service.get_session(
        app_name="hr_app", user_id=user_id, session_id=session_id
    )
    for key, value in final_session.state.items():
        print(f"  {key}: {value}")

    print(f"\n  Total events in session: {len(final_session.events)}")


# ============================================================
# 5. RUN IT
# ============================================================
if __name__ == "__main__":
    asyncio.run(run_conversation())
