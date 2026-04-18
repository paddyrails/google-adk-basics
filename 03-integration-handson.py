"""
03 - Integration Hands-On: Google ADK Integration Patterns
============================================================
Three exercises:
  Exercise 1: ADK project structure + adk web (setup)
  Exercise 2: Streaming responses (token-by-token output)
  Exercise 3: FastAPI REST API serving an ADK agent
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types


# ============================================================
# EXERCISE 1: Create proper ADK project structure
# ============================================================
# This function creates the folder structure needed for `adk web`

def setup_adk_project():
    """Creates a proper ADK project structure for the dev UI."""
    base = os.path.dirname(os.path.abspath(__file__))
    agent_dir = os.path.join(base, "my_agent")
    os.makedirs(agent_dir, exist_ok=True)

    # __init__.py — re-export root_agent
    init_content = 'from .agent import root_agent\n'
    with open(os.path.join(agent_dir, "__init__.py"), "w") as f:
        f.write(init_content)

    # agent.py — the actual agent definition
    agent_content = '''"""My first ADK agent — a helpful coding assistant."""

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
        "lines": len(code.strip().split("\\n")),
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
'''
    with open(os.path.join(agent_dir, "agent.py"), "w") as f:
        f.write(agent_content)

    # .env — copy from parent
    parent_env = os.path.join(base, ".env")
    agent_env = os.path.join(agent_dir, ".env")
    if os.path.exists(parent_env):
        with open(parent_env, "r") as src, open(agent_env, "w") as dst:
            dst.write(src.read())

    print("=" * 60)
    print("EXERCISE 1: ADK Project Structure Created")
    print("=" * 60)
    print(f"""
  {agent_dir}/
    __init__.py    <- re-exports root_agent
    agent.py       <- defines root_agent with tools
    .env           <- API keys

  To launch the Dev UI, run:
    cd {base}
    adk web --port 8000

  Then open http://localhost:8000 in your browser.
  Select 'my_agent' from the dropdown and chat!
""")


# ============================================================
# EXERCISE 2: Streaming Responses
# ============================================================

async def exercise_streaming():
    """Demonstrates token-by-token streaming from an ADK agent."""

    agent = LlmAgent(
        model="gemini-2.5-flash",
        name="storyteller",
        instruction="You are a creative storyteller. Keep stories under 100 words.",
    )

    runner = InMemoryRunner(agent=agent, app_name="streaming_demo")
    session = await runner.session_service.create_session(
        app_name="streaming_demo", user_id="u1", session_id="s1"
    )

    print("=" * 60)
    print("EXERCISE 2: Streaming Response (token-by-token)")
    print("=" * 60)
    print("\nQuery: Tell me a short story about a robot learning to cook\n")
    print("-" * 60)

    msg = types.Content(role="user", parts=[types.Part(text="Tell me a short story about a robot learning to cook")])

    token_count = 0
    async for event in runner.run_async(user_id="u1", session_id="s1", new_message=msg):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    if event.partial:
                        # Streaming token — print without newline
                        print(part.text, end="", flush=True)
                        token_count += 1
                    elif event.is_final_response():
                        # Final complete response (if streaming didn't cover it)
                        if token_count == 0:
                            print(part.text)

    print(f"\n{'-' * 60}")
    print(f"Streamed {token_count} partial events")


# ============================================================
# EXERCISE 3: FastAPI Integration
# ============================================================

def exercise_fastapi():
    """Creates a FastAPI server file that serves an ADK agent."""
    base = os.path.dirname(os.path.abspath(__file__))
    server_path = os.path.join(base, "03-fastapi-server.py")

    server_code = '''"""
FastAPI server serving an ADK agent as a REST API.
Run with: uvicorn 03-fastapi-server:app --host 0.0.0.0 --port 8080 --reload
"""

import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# --- Agent Definition ---
def get_greeting(name: str) -> dict:
    """Generates a personalized greeting.

    Args:
        name: The person\'s name.
    """
    return {"greeting": f"Hello, {name}! Welcome aboard."}

agent = LlmAgent(
    model="gemini-2.5-flash",
    name="greeter",
    instruction="You are a friendly greeter. Use the get_greeting tool when someone introduces themselves.",
    tools=[get_greeting],
)

# --- Runner (create once, reuse across requests) ---
APP_NAME = "greeter_app"
session_service = InMemorySessionService()
runner = Runner(app_name=APP_NAME, agent=agent, session_service=session_service)

# --- FastAPI App ---
app = FastAPI(title="ADK Agent API")

@app.post("/chat")
async def chat(request: Request):
    """Send a message and get a response."""
    body = await request.json()
    query = body.get("query", "")
    user_id = body.get("user_id", "default_user")
    session_id = body.get("session_id", "default_session")

    # Ensure session exists
    session = await session_service.get_session(APP_NAME, user_id, session_id)
    if not session:
        session = await session_service.create_session(APP_NAME, user_id, session_id)

    response_text = ""
    tool_calls = []

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=query)]),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call:
                    tool_calls.append({"name": part.function_call.name, "args": part.function_call.args})
                if event.is_final_response() and part.text:
                    response_text = part.text

    return JSONResponse(content={
        "response": response_text,
        "tool_calls": tool_calls,
        "session_id": session_id,
    })

@app.post("/chat/stream")
async def chat_stream(request: Request):
    """Send a message and get a streamed response."""
    body = await request.json()
    query = body.get("query", "")
    user_id = body.get("user_id", "default_user")
    session_id = body.get("session_id", "default_session")

    session = await session_service.get_session(APP_NAME, user_id, session_id)
    if not session:
        await session_service.create_session(APP_NAME, user_id, session_id)

    async def stream():
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=query)]),
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        yield part.text

    return StreamingResponse(stream(), media_type="text/plain")

@app.get("/health")
async def health():
    return {"status": "ok", "agent": agent.name}
'''

    with open(server_path, "w") as f:
        f.write(server_code)

    print("=" * 60)
    print("EXERCISE 3: FastAPI Server Created")
    print("=" * 60)
    print(f"""
  File: {server_path}

  To run:
    pip install fastapi uvicorn
    uvicorn 03-fastapi-server:app --host 0.0.0.0 --port 8080 --reload

  Endpoints:
    POST /chat          - Send message, get JSON response
    POST /chat/stream   - Send message, get streamed response
    GET  /health        - Health check

  Test with curl:
    curl -X POST http://localhost:8080/chat \\
      -H "Content-Type: application/json" \\
      -d '{{"query": "Hi, my name is Paddy", "user_id": "u1", "session_id": "s1"}}'
""")


# ============================================================
# MAIN — Run all exercises
# ============================================================

async def main():
    # Exercise 1: Create ADK project structure
    setup_adk_project()

    # Exercise 2: Streaming demo
    await exercise_streaming()

    # Exercise 3: Create FastAPI server file
    print()
    exercise_fastapi()

    print("\n" + "=" * 60)
    print("All exercises complete!")
    print("=" * 60)
    print("""
Next steps to try:
  1. Run `adk web --port 8000` to launch the Dev UI
  2. Run the FastAPI server and test with curl
  3. Try adding LiteLLM models (requires pip install litellm)
""")


if __name__ == "__main__":
    asyncio.run(main())
