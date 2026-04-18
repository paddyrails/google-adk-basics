import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from google.adk.agents import SequentialAgent, ParallelAgent, LoopAgent, LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.tools import exit_loop
from google.genai import types

MODEL = "gemini-2.5-flash"

async def execise_sequential():

    researcher = LlmAgent(
        name="researcher",
        model=MODEL,
        instruction="Reasearch the topic and provide 3-4 key facts. Topic {topic}. Be concise, bullet points only",
        output_key="research_findings"
    )

    writer = LlmAgent(
        name="writer",
        model=MODEL,
        instruction=""",
        Write short paragraph (3-4) sentences based on these research findings: {research_findings}


        Make it engaging and informative
        """,
        output_key="draft"
    )

    editor = LlmAgent(
        name="editor",
        model=MODEL,
        instruction="""
        Edit this draft for clarity. Fix any issuses. Keep it concise:
        {draft}

        Return only final edited text
        """
    )

    pipeline = SequentialAgent(
        name="content_pipeline",
        sub_agents=[researcher, writer, editor]
    )

    runner = InMemoryRunner(agent=pipeline, app_name="pipeline_app")
    session = await runner.session_service.create_session(
        app_name="pipeline_app",
        user_id="u1",
        session_id="s1",
        state={"topic": "why Python is popular for AI development"}
    )

    msg = types.Content(role="user", parts=[types.Part(text="Create content about the given topic")])

    async for event in runner.run_async(user_id="u1", session_id="s1", new_message=msg):
        if event.partial:
            continue
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text and not event.partial:
                    print(f"  [{event.author}]: {part.text[:200]}...")
                    print()


    final_session = await runner.session_service.get_session(
        app_name="pipeline_app", user_id="u1", session_id="s1"
    )

    print("State keys populated:")
    for key in ["research_findings", "draft", "final_text"]:
        val = final_session.state.get(key, "NOT SET")
        print(f"  {key}: {val[:80]}...")


async def exercise_parallel():
    print("\n" + "=" * 60)
    print("EXERCISE 2: ParallelAgent — Multi-Perspective Analysis")
    print("=" * 60)

    optimist = LlmAgent(
        name="optimist",
        model=MODEL,
        instruction="Analyze this proposal OPTIMISTICALLY in 2 sentences. What could go right? Proposal: {proposal}",
        output_key="optimist_view",
    )

    pessimist = LlmAgent(
        name="pessimist",
        model=MODEL,
        instruction="Analyze this proposal PESSIMISTICALLY in 2 sentences. What could go wrong? Proposal: {proposal}",
        output_key="pessimist_view",
    )

    realist = LlmAgent(
        name="realist",
        model=MODEL,
        instruction="Analyze this proposal REALISTICALLY in 2 sentences. What is most likely? Proposal: {proposal}",
        output_key="realist_view",
    )

    # Fan-out: all 3 run concurrently
    fan_out= ParallelAgent(
        name="perspectives",
        sub_agents=[optimist, pessimist, realist]
    )

    # Fan-in: synthesize results
    synthesizer = LlmAgent(
        name="synthesizer",
        model=MODEL,
        instruction="""Synthesize these three perspectives into a balanced 3-sentence recommendation:

Optimistic view: {optimist_view}
Pessimistic view: {pessimist_view}
Realistic view: {realist_view}""",
        output_key="recommendation",
    )

    #Full pipeline
    analysis = SequentialAgent(
        name="balanced_analysis",
        sub_agents=[fan_out, synthesizer]
    )

    runner = InMemoryRunner(agent=analysis, app_name="analysis_app")
    session = await runner.session_service.create_session(
        app_name="analysis_app",
        user_id="u1",
        session_id="s2",
        state={"proposal": "Migrating our monolithic Python app to microservices using Kubernetes"},
    )

    msg = types.Content(role="user", parts=[types.Part(text="Analyze the proposal")])

    print("\nProposal: Migrating monolithic Python app to microservices on K8s\n")

    async for event in runner.run_async(user_id="u1", session_id="s2", new_message=msg):
        if event.partial:
            continue
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(f"  [{event.author}]: {part.text[:200]}")
                    print()

    final_session = await runner.session_service.get_session(
        app_name="analysis_app", user_id="u1", session_id="s2"
    )
    print("Final recommendation:")
    print(f"  {final_session.state.get('recommendation', 'NOT SET')[:300]}")



async def exercise_loop():
    print("\n" + "=" * 60)
    print("EXERCISE 3: LoopAgent — Self-Correcting Code Review")
    print("=" * 60)

    # Generator writes/revises code
    coder = LlmAgent(
        name="coder",
        model=MODEL,
        instruction="""Write a Python function based on these requirements: {requirements}

If there is reviewer feedback, address ALL points:
{reviewer_feedback}

Return ONLY the Python code, no explanation.""",
        output_key="generated_code",
    )

    # Reviewer checks quality and either approves (exit_loop) or gives feedback
    reviewer = LlmAgent(
        name="reviewer",
        model=MODEL,
        instruction="""Review this Python code for:
1. Correctness (handles edge cases?)
2. Has type hints?
3. Has a docstring?
4. Handles errors?

Code:
{generated_code}

If ALL 4 criteria are met, call the exit_loop tool to approve.
If ANY criteria are NOT met, list the specific issues to fix. Do NOT call exit_loop.""",
        tools=[exit_loop],
        output_key="reviewer_feedback",
    )


    review_loop = LoopAgent(
        name="code_review",
        sub_agents=[coder, reviewer],
        max_iterations=3
    )

    runner = InMemoryRunner(agent=review_loop, app_name="loop_app")
    session = await runner.session_service.create_session(
        app_name="loop_app",
        user_id="u1",
        session_id="s3",
        state={
            "requirements": "Write a function called 'fibonacci' that returns the nth Fibonacci number. Handle negative inputs.",
            "reviewer_feedback": "",
        },
    )

    msg = types.Content(role="user", parts=[types.Part(text="Generate and review the code")])

    print("\nRequirements: fibonacci(n) with edge case handling\n")

    iteration = 0
    async for event in runner.run_async(user_id="u1", session_id="s3", new_message=msg):
        if event.partial:
            continue
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call:
                    print(f"  [{event.author}] Tool: {part.function_call.name}()")
                elif part.text:
                    # Track iterations by author switches
                    label = event.author
                    preview = part.text[:150].replace("\n", " | ")
                    print(f"  [{label}]: {preview}")

    final_session = await runner.session_service.get_session(
        app_name="loop_app", user_id="u1", session_id="s3"
    )
    print(f"\nFinal code:\n{final_session.state.get('generated_code', 'NOT SET')}")

async def main():
    # await execise_sequential()
    # await exercise_parallel()
    await exercise_loop()

    
if __name__ == "__main__":
    asyncio.run(main())    