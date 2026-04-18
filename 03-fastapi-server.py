"""
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
        name: The person's name.
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
