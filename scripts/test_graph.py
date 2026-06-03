"""
Standalone LangGraph foundation tests. Uses MemorySaver (no DB required).
Run: cd backend && .venv/Scripts/python.exe ../scripts/test_graph.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


async def test_initial_state() -> bool:
    print("\n=== TEST 1: Initial State ===")
    try:
        from agent.state import (
            create_initial_state,
            get_retry_count,
            increment_retry,
            is_slot_filled,
            log_decision,
        )

        s = create_initial_state("lead-1", "tenant-1")
        assert s["session_id"]
        assert s["lead_id"] == "lead-1"
        assert list(s["slots"].keys()) == [
            "sector", "pg_type", "budget", "visit_date", "landmark", "name", "move_in_date"
        ]
        assert not is_slot_filled(s, "sector")
        assert get_retry_count(s, "sector") == 0
        assert increment_retry(s, "sector")["retry_counts"]["sector"] == 1
        assert len(log_decision(s, "n", "d")["decision_log"]) == 1
        print("  [OK] state has", len(s), "fields, all helpers work")
        return True
    except Exception as exc:
        print("  [FAIL]", exc)
        import traceback
        traceback.print_exc()
        return False


async def test_compilation() -> bool:
    print("\n=== TEST 2: Graph Compilation ===")
    try:
        from langgraph.checkpoint.memory import MemorySaver

        from agent.graph import build_graph

        g = build_graph(checkpointer=MemorySaver())
        print("  [OK] compiled:", type(g).__name__)
        return True
    except Exception as exc:
        print("  [FAIL]", exc)
        import traceback
        traceback.print_exc()
        return False


async def test_invoke() -> bool:
    print("\n=== TEST 3: Graph Invocation ===")
    try:
        from langgraph.checkpoint.memory import MemorySaver

        from agent.graph import build_graph
        from agent.state import create_initial_state

        g = build_graph(checkpointer=MemorySaver())
        s = create_initial_state("lead-invoke", "tenant")
        s["current_user_message"] = "Hi, I need a PG"
        cfg = {"configurable": {"thread_id": "lead-invoke"}}
        r = await g.ainvoke(s, cfg)

        assert r.get("last_response") == "Sir, kis sector me PG dhundh rahe ho?", repr(r.get("last_response"))
        assert r.get("turn_count") == 1
        assert r.get("retry_counts", {}).get("sector") == 1
        assert len(r.get("messages", [])) >= 1

        print("  [OK] response:", r.get("last_response"))
        print("  [OK] turn_count:", r.get("turn_count"),
              "| sector_retry:", r["retry_counts"]["sector"],
              "| msgs:", len(r["messages"]))
        return True
    except Exception as exc:
        print("  [FAIL]", exc)
        import traceback
        traceback.print_exc()
        return False


async def test_persistence() -> bool:
    print("\n=== TEST 4: State Persistence ===")
    try:
        from langgraph.checkpoint.memory import MemorySaver

        from agent.graph import build_graph
        from agent.state import create_initial_state

        mem = MemorySaver()
        g = build_graph(checkpointer=mem)
        cfg = {"configurable": {"thread_id": "lead-persist"}}

        s1 = create_initial_state("lead-persist", "tenant")
        s1["current_user_message"] = "Hi"
        r1 = await g.ainvoke(s1, cfg)
        assert r1["turn_count"] == 1
        print("  Turn 1 turn_count:", r1["turn_count"])

        snap = await g.aget_state(cfg)
        assert snap and snap.values
        assert snap.values["turn_count"] == 1
        print("  Checkpoint loaded — turn_count:", snap.values["turn_count"])

        # Turn 2: only update the fields that change — let checkpoint supply the rest
        from datetime import datetime
        turn2_input = {
            "current_user_message": "Sector 44",
            "messages": [{
                "role": "user",
                "content": "Sector 44",
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {},
            }],
            "last_user_message_at": datetime.utcnow().isoformat(),
        }
        r2 = await g.ainvoke(turn2_input, cfg)
        assert r2["turn_count"] == 2, f"Expected 2 got {r2['turn_count']}"
        print("  Turn 2 turn_count:", r2["turn_count"])
        print("  [OK] state persists across invocations")
        return True
    except Exception as exc:
        print("  [FAIL]", exc)
        import traceback
        traceback.print_exc()
        return False


async def test_routing() -> bool:
    print("\n=== TEST 5: Router Logic ===")
    try:
        from agent.router import strict_router
        from agent.state import create_initial_state

        def chk(state, expected):
            got = strict_router(state)
            assert got == expected, f"Expected {expected!r} got {got!r}"
            print(f"  [OK] -> {expected}")

        s = create_initial_state("t", "t")
        chk(s, "ask_sector_open")
        s["retry_counts"]["sector"] = 1
        chk(s, "ask_sector_helpful")
        s["retry_counts"]["sector"] = 2
        chk(s, "ask_sector_examples")
        s["retry_counts"]["sector"] = 3
        chk(s, "ask_sector_options")
        s["retry_counts"]["sector"] = 5
        chk(s, "human_handoff")

        s2 = create_initial_state("t2", "t2")
        s2["slots"]["sector"] = {"value": "44", "confidence": 0.95, "method": "explicit", "history": []}
        chk(s2, "ask_pg_type")
        s2["slots"]["pg_type"] = {"value": "boys", "confidence": 0.9, "method": "explicit", "history": []}
        chk(s2, "ask_budget")
        s2["slots"]["budget"] = {"value": "12000", "confidence": 0.9, "method": "explicit", "history": []}
        chk(s2, "search_properties")

        s3 = create_initial_state("t3", "t3")
        s3["needs_human"] = True
        chk(s3, "human_handoff")

        s4 = create_initial_state("t4", "t4")
        s4["sentiment"] = "angry"
        chk(s4, "human_handoff")

        return True
    except Exception as exc:
        print("  [FAIL]", exc)
        import traceback
        traceback.print_exc()
        return False


async def main() -> bool:
    print("=" * 55)
    print("  LANGGRAPH FOUNDATION TESTS  (MemorySaver - no DB)")
    print("=" * 55)

    tests = [
        ("Initial State",     test_initial_state),
        ("Graph Compilation", test_compilation),
        ("Graph Invocation",  test_invoke),
        ("State Persistence", test_persistence),
        ("Router Logic",      test_routing),
    ]

    results = []
    for name, fn in tests:
        results.append((name, await fn()))

    print("\n" + "=" * 55)
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    total = sum(1 for _, ok in results if ok)
    print(f"\n  {total}/{len(results)} passed")
    print("=" * 55)
    return total == len(results)


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(main()) else 1)
