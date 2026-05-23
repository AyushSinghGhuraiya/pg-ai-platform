"""
Standalone verification script — tests all external service connections.
Run from project root: python scripts/verify_setup.py

Exit code 0 = all required services pass.
Exit code 1 = one or more required services fail.
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
import time
from pathlib import Path

# Force UTF-8 output on Windows so print() doesn't crash on special chars
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Load .env from project root
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


# ── Helpers ───────────────────────────────────────────────────────────────────

def ok(label: str, detail: str = "") -> None:
    suffix = f"  ({detail})" if detail else ""
    print(f"  [OK]   {label}{suffix}")


def fail(label: str, error: str = "") -> None:
    suffix = f"  -> {error}" if error else ""
    print(f"  [FAIL] {label}{suffix}")


def skip(label: str, reason: str = "") -> None:
    suffix = f"  ({reason})" if reason else ""
    print(f"  [SKIP] {label}{suffix}")


# ── Individual checks ─────────────────────────────────────────────────────────

async def check_supabase() -> bool:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not (url and key):
        skip("Supabase", "SUPABASE_URL or SERVICE_KEY not set")
        return True  # optional for basic run

    try:
        from supabase._async.client import create_client

        start = time.perf_counter()
        client = await create_client(url, key)
        result = await client.table("tenants").select("id").limit(1).execute()
        ms = round((time.perf_counter() - start) * 1000)
        ok("Supabase", f"{ms}ms, {len(result.data)} tenant(s) found")
        return True
    except Exception as e:
        fail("Supabase", str(e))
        return False


async def check_redis() -> bool:
    rest_url = os.getenv("UPSTASH_REDIS_REST_URL", "")
    token = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
    if not (rest_url and token):
        skip("Redis (Upstash)", "REST URL or TOKEN not set")
        return True

    try:
        from upstash_redis.asyncio import Redis

        start = time.perf_counter()
        r = Redis(url=rest_url, token=token)
        pong = await r.ping()
        ms = round((time.perf_counter() - start) * 1000)
        ok("Redis (Upstash)", f"{ms}ms, ping={pong}")
        return True
    except Exception as e:
        fail("Redis (Upstash)", str(e))
        return False


async def check_gemini() -> bool:
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        skip("Gemini API", "GEMINI_API_KEY not set")
        return True

    try:
        import litellm

        os.environ["GEMINI_API_KEY"] = key
        start = time.perf_counter()
        response = await litellm.acompletion(
            model="gemini/gemini-2.0-flash",
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=5,
        )
        ms = round((time.perf_counter() - start) * 1000)
        text = response.choices[0].message.content or ""
        ok("Gemini API", f"{ms}ms, response='{text.strip()[:30]}'")
        return True
    except Exception as e:
        err = str(e)
        if "429" in err or "RateLimit" in err or "rate_limit" in err.lower():
            ok("Gemini API", "API key valid (rate limited on free tier - normal)")
            return True
        fail("Gemini API", err[:120])
        return False


async def check_groq() -> bool:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        skip("Groq API", "GROQ_API_KEY not set")
        return True

    try:
        import litellm

        os.environ["GROQ_API_KEY"] = key
        start = time.perf_counter()
        response = await litellm.acompletion(
            model="groq/llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=5,
        )
        ms = round((time.perf_counter() - start) * 1000)
        text = response.choices[0].message.content or ""
        ok("Groq API", f"{ms}ms, response='{text.strip()[:30]}'")
        return True
    except Exception as e:
        fail("Groq API", str(e)[:120])
        return False


async def check_langfuse() -> bool:
    pub = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    sec = os.getenv("LANGFUSE_SECRET_KEY", "")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    if not (pub and sec):
        skip("LangFuse", "PUBLIC_KEY or SECRET_KEY not set")
        return True

    try:
        from langfuse import Langfuse

        start = time.perf_counter()
        lf = Langfuse(public_key=pub, secret_key=sec, host=host)
        lf.auth_check()
        ms = round((time.perf_counter() - start) * 1000)
        ok("LangFuse", f"{ms}ms, auth ok")
        return True
    except Exception as e:
        fail("LangFuse", str(e)[:120])
        return False


def check_sentry() -> bool:
    dsn = os.getenv("SENTRY_DSN", "")
    if not dsn:
        skip("Sentry", "SENTRY_DSN not set")
        return True

    try:
        import sentry_sdk

        # Just validate the DSN format (init sends a background event)
        client = sentry_sdk.Client(dsn=dsn)
        if client.options.get("dsn"):
            ok("Sentry", "DSN format valid, SDK ready")
            return True
        fail("Sentry", "DSN rejected by SDK")
        return False
    except Exception as e:
        fail("Sentry", str(e)[:120])
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> int:
    print("\nPG AI Platform — Service Verification")
    print("=" * 45)

    results = await asyncio.gather(
        check_supabase(),
        check_redis(),
        check_gemini(),
        check_groq(),
        check_langfuse(),
        return_exceptions=True,
    )
    sentry_ok = check_sentry()

    all_results = list(results) + [sentry_ok]
    failures = [r for r in all_results if r is False]
    errors = [r for r in all_results if isinstance(r, Exception)]

    print("=" * 45)
    if failures or errors:
        print(f"  {len(failures) + len(errors)} check(s) failed.\n")
        return 1
    else:
        print("  All checks passed.\n")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
