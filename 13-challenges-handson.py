"""
13 - Challenges Hands-On: Real-World ADK Engineering Problems
===============================================================
Exercise 1: Non-determinism — Run same query 3x, compare results
Exercise 2: Cost explosion — LoopAgent with token tracking
Exercise 3: Tool reliability — Failing tool + circuit breaker
Exercise 4: Agent evaluation — Golden dataset + trajectory scoring
"""

import asyncio
import os
import time
from dotenv import load_dotenv

load_dotenv()

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.runners import InMemoryRunner
from google.adk.tools import exit_loop
from google.genai import types

MODEL = "gemini-2.5-flash"


# ============================================================
# EXERCISE 1: Non-Determinism — Same query, different results
# ============================================================

async def exercise_nondeterminism():
    print("=" * 60)
    print("EXERCISE 1: Non-Determinism — 3 runs, same query")
    print("=" * 60)

    def lookup_product(product_id: str) -> dict:
        """Looks up a product by ID.
        Args:
            product_id: The product identifier.
        """
        products = {
            "A100": {"name": "Widget Pro", "price": 49.99, "stock": 15},
            "B200": {"name": "Gadget Plus", "price": 79.99, "stock": 0},
        }
        return products.get(product_id, {"error": f"Unknown product: {product_id}"})

    def check_inventory(product_id: str) -> dict:
        """Checks inventory for a product.
        Args:
            product_id: The product to check.
        """
        inventory = {"A100": 15, "B200": 0}
        return {"product_id": product_id, "in_stock": inventory.get(product_id, -1) > 0}

    agent = LlmAgent(
        name="shop_agent",
        model=MODEL,
        instruction="""You help with product inquiries. Use lookup_product for details
and check_inventory for stock status. Be concise.""",
        tools=[lookup_product, check_inventory],
    )

    query = "Is Widget Pro (A100) in stock and how much does it cost?"
    results = []

    for run in range(3):
        runner = InMemoryRunner(agent=agent, app_name=f"nondet_{run}")
        await runner.session_service.create_session(
            app_name=f"nondet_{run}", user_id="u1", session_id=f"s{run}",
        )
        msg = types.Content(role="user", parts=[types.Part(text=query)])

        tools_called = []
        response = ""
        async for event in runner.run_async(user_id="u1", session_id=f"s{run}", new_message=msg):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_call:
                        tools_called.append(part.function_call.name)
                    if event.is_final_response() and part.text:
                        response = part.text

        results.append({"run": run + 1, "tools": tools_called, "response": response[:100]})

    print(f"\n  Query: {query}\n")
    for r in results:
        print(f"  Run {r['run']}: Tools={r['tools']}")
        print(f"         Response: {r['response']}")
        print()

    # Check if all runs used the same tool sequence
    tool_sequences = [tuple(r["tools"]) for r in results]
    if len(set(tool_sequences)) == 1:
        print("  Result: All 3 runs used SAME tool sequence (deterministic this time)")
    else:
        print("  Result: DIFFERENT tool sequences across runs (non-determinism!)")
    print(f"  Sequences: {[list(s) for s in set(tool_sequences)]}")


# ============================================================
# EXERCISE 2: Cost Explosion — LoopAgent token tracking
# ============================================================

async def exercise_cost_explosion():
    print("\n" + "=" * 60)
    print("EXERCISE 2: Cost Explosion — LoopAgent Token Tracking")
    print("=" * 60)

    token_tracker = {"calls": 0, "total_input": 0, "total_output": 0, "per_iteration": []}

    def track_after_model(callback_context, llm_response, **kwargs):
        if hasattr(llm_response, 'usage_metadata') and llm_response.usage_metadata:
            um = llm_response.usage_metadata
            inp = um.prompt_token_count or 0
            out = um.candidates_token_count or 0
            token_tracker["calls"] += 1
            token_tracker["total_input"] += inp
            token_tracker["total_output"] += out
            token_tracker["per_iteration"].append({"call": token_tracker["calls"], "input": inp, "output": out})
        return None

    writer = LlmAgent(
        name="writer",
        model=MODEL,
        instruction="Write a haiku about: {topic}. If there's feedback, improve it: {feedback}",
        output_key="haiku",
        after_model_callback=track_after_model,
    )

    critic = LlmAgent(
        name="critic",
        model=MODEL,
        instruction="""Review this haiku: {haiku}
Check: Does it have exactly 3 lines? Is it about the topic?
If it's good, call exit_loop. If not, provide specific feedback.""",
        tools=[exit_loop],
        output_key="feedback",
        after_model_callback=track_after_model,
    )

    loop = LoopAgent(
        name="haiku_refiner",
        sub_agents=[writer, critic],
        max_iterations=3,
    )

    runner = InMemoryRunner(agent=loop, app_name="cost_app")
    await runner.session_service.create_session(
        app_name="cost_app", user_id="u1", session_id="cost_s1",
        state={"topic": "artificial intelligence", "feedback": ""},
    )

    msg = types.Content(role="user", parts=[types.Part(text="Write and refine a haiku")])
    print(f"\n  Running LoopAgent (max 3 iterations)...\n")

    async for event in runner.run_async(user_id="u1", session_id="cost_s1", new_message=msg):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text and not event.partial:
                    preview = part.text[:80].replace("\n", " | ")
                    print(f"  [{event.author}]: {preview}")

    # Cost analysis
    print(f"\n  === Cost Analysis ===")
    print(f"  Total LLM calls: {token_tracker['calls']}")
    print(f"  Total input tokens: {token_tracker['total_input']}")
    print(f"  Total output tokens: {token_tracker['total_output']}")

    for entry in token_tracker["per_iteration"]:
        print(f"    Call #{entry['call']}: in={entry['input']} out={entry['output']}")

    input_cost = (token_tracker["total_input"] / 1_000_000) * 0.15
    output_cost = (token_tracker["total_output"] / 1_000_000) * 0.60
    total_cost = input_cost + output_cost
    print(f"  Estimated cost: ${total_cost:.6f}")
    print(f"  Cost per iteration: ${total_cost / max(token_tracker['calls'] / 2, 1):.6f}")
    print(f"  If this ran 100 iterations: ~${total_cost / max(token_tracker['calls'] / 2, 1) * 100:.4f}")


# ============================================================
# EXERCISE 3: Tool Reliability — Failing tool + circuit breaker
# ============================================================

async def exercise_tool_reliability():
    print("\n" + "=" * 60)
    print("EXERCISE 3: Tool Reliability — Failing Tool + Recovery")
    print("=" * 60)

    call_count = {"api": 0}

    def unreliable_api(query: str) -> dict:
        """Calls an external API that sometimes fails.
        Args:
            query: The search query.
        """
        call_count["api"] += 1
        # Fail on first 2 calls, succeed on 3rd
        if call_count["api"] <= 2:
            raise ConnectionError(f"API timeout (attempt {call_count['api']})")
        return {"result": f"Data for '{query}'", "source": "external_api"}

    def fallback_search(query: str) -> dict:
        """Local fallback search when external API is unavailable.
        Args:
            query: The search query.
        """
        return {"result": f"Cached data for '{query}'", "source": "local_cache"}

    # Error handler that gracefully degrades
    def handle_tool_error(tool, args, tool_context, error, **kwargs):
        print(f"  [ERROR] Tool '{tool.name}' failed: {error}")
        tool_context.state["tool_errors"] = tool_context.state.get("tool_errors", 0) + 1
        errors = tool_context.state["tool_errors"]

        if errors >= 2:
            print(f"  [CIRCUIT BREAKER] {errors} failures — suggesting fallback")
            return {
                "error": str(error),
                "suggestion": "Use the fallback_search tool instead.",
                "failures": errors,
            }
        return {
            "error": str(error),
            "suggestion": "Please retry the same query.",
            "failures": errors,
        }

    agent = LlmAgent(
        name="resilient_agent",
        model=MODEL,
        instruction="""You search for information. Try unreliable_api first.
If it fails multiple times, use fallback_search instead. Report the source of data.""",
        tools=[unreliable_api, fallback_search],
        on_tool_error_callback=handle_tool_error,
    )

    runner = InMemoryRunner(agent=agent, app_name="reliability_app")
    await runner.session_service.create_session(
        app_name="reliability_app", user_id="u1", session_id="rel_s1",
    )

    msg = types.Content(role="user", parts=[types.Part(text="Search for 'Python ADK tutorials'")])
    print(f"\n  Simulating: API fails twice, then agent should use fallback\n")

    async for event in runner.run_async(user_id="u1", session_id="rel_s1", new_message=msg):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call:
                    print(f"  [TOOL CALL] {part.function_call.name}({part.function_call.args})")
                if event.is_final_response() and part.text:
                    print(f"\n  [FINAL] {part.text[:200]}")

    print(f"\n  Total API attempts: {call_count['api']}")


# ============================================================
# EXERCISE 4: Agent Evaluation — Trajectory Scoring
# ============================================================

async def exercise_evaluation():
    print("\n" + "=" * 60)
    print("EXERCISE 4: Agent Evaluation — Trajectory Scoring")
    print("=" * 60)

    def get_order(order_id: str) -> dict:
        """Fetches order details.
        Args:
            order_id: The order ID.
        """
        orders = {
            "ORD-123": {"status": "delivered", "total": 49.99, "item": "Widget"},
            "ORD-456": {"status": "processing", "total": 129.00, "item": "Gadget"},
        }
        return orders.get(order_id, {"error": "Order not found"})

    def check_refund_eligibility(order_id: str) -> dict:
        """Checks if an order is eligible for refund.
        Args:
            order_id: The order ID to check.
        """
        return {"order_id": order_id, "eligible": True, "reason": "Within 30-day window"}

    agent = LlmAgent(
        name="refund_agent",
        model=MODEL,
        instruction="""You process refund requests. Always:
1. First look up the order with get_order
2. Then check refund eligibility with check_refund_eligibility
3. Report the result to the user""",
        tools=[get_order, check_refund_eligibility],
    )

    # Golden test cases with expected trajectories
    golden_tests = [
        {
            "query": "I want to refund order ORD-123",
            "expected_tools": ["get_order", "check_refund_eligibility"],
            "expected_keywords": ["eligible", "refund"],
        },
        {
            "query": "Can I return order ORD-456?",
            "expected_tools": ["get_order", "check_refund_eligibility"],
            "expected_keywords": ["eligible"],
        },
    ]

    print(f"\n  Running {len(golden_tests)} golden test cases...\n")
    results = []

    for i, test in enumerate(golden_tests):
        runner = InMemoryRunner(agent=agent, app_name=f"eval_{i}")
        await runner.session_service.create_session(
            app_name=f"eval_{i}", user_id="u1", session_id=f"eval_s{i}",
        )

        msg = types.Content(role="user", parts=[types.Part(text=test["query"])])
        actual_tools = []
        response = ""

        async for event in runner.run_async(user_id="u1", session_id=f"eval_s{i}", new_message=msg):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_call:
                        actual_tools.append(part.function_call.name)
                    if event.is_final_response() and part.text:
                        response = part.text

        # Score trajectory
        expected = test["expected_tools"]
        trajectory_match = actual_tools == expected
        trajectory_score = 1.0 if trajectory_match else (
            len(set(actual_tools) & set(expected)) / len(expected)
        )

        # Score response (keyword check)
        keywords_found = sum(1 for kw in test["expected_keywords"] if kw.lower() in response.lower())
        response_score = keywords_found / len(test["expected_keywords"])

        result = {
            "test": i + 1,
            "query": test["query"][:40],
            "expected_tools": expected,
            "actual_tools": actual_tools,
            "trajectory_score": trajectory_score,
            "response_score": response_score,
            "passed": trajectory_score >= 0.9 and response_score >= 0.8,
        }
        results.append(result)

        status = "PASS" if result["passed"] else "FAIL"
        print(f"  Test {i+1}: [{status}]")
        print(f"    Query: {test['query']}")
        print(f"    Expected tools: {expected}")
        print(f"    Actual tools:   {actual_tools}")
        print(f"    Trajectory: {trajectory_score:.0%} | Response: {response_score:.0%}")
        print()

    # Summary
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    avg_trajectory = sum(r["trajectory_score"] for r in results) / total
    avg_response = sum(r["response_score"] for r in results) / total

    print(f"  === Evaluation Summary ===")
    print(f"  Tests passed: {passed}/{total}")
    print(f"  Avg trajectory score: {avg_trajectory:.0%}")
    print(f"  Avg response score: {avg_response:.0%}")

    if avg_trajectory >= 0.9:
        print(f"  CI/CD verdict: PASS (trajectory >= 90%)")
    else:
        print(f"  CI/CD verdict: FAIL (trajectory < 90%)")


# ============================================================
# MAIN
# ============================================================

async def main():
    await exercise_nondeterminism()
    await exercise_cost_explosion()
    await exercise_tool_reliability()
    await exercise_evaluation()

    print("\n" + "=" * 60)
    print("All challenge exercises complete!")
    print("=" * 60)
    print("""
Challenges demonstrated:
  1. Non-determinism  — Same query may produce different tool sequences
  2. Cost explosion   — LoopAgent multiplies tokens per iteration
  3. Tool reliability — Failing tools + circuit breaker + fallback
  4. Evaluation       — Golden dataset + trajectory scoring for CI/CD
""")


if __name__ == "__main__":
    asyncio.run(main())
