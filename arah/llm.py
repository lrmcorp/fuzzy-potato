from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time

import httpx

from .config import Settings
from .db import DB

log = logging.getLogger("arah.llm")

# USD per token, used only when OpenRouter does not report the cost itself.
FALLBACK_PRICE = {"in": 1.0e-6, "out": 2.0e-6}


class BudgetExceeded(Exception):
    pass


class LLMError(Exception):
    pass


def spend(db: DB) -> dict:
    now = time.time()
    lt = time.localtime(now)
    day_start = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    month_start = time.mktime((lt.tm_year, lt.tm_mon, 1, 0, 0, 0, 0, 0, -1))
    day = db.one("SELECT COALESCE(SUM(cost_usd),0) s FROM llm_usage WHERE ts>=?", (int(day_start),))["s"]
    month = db.one("SELECT COALESCE(SUM(cost_usd),0) s, COUNT(*) n FROM llm_usage WHERE ts>=?", (int(month_start),))
    return {"day": float(day), "month": float(month["s"]), "calls_month": month["n"]}


def budget_state(db: DB, settings: Settings) -> dict:
    s = spend(db)
    return {
        **s,
        "cap_day": settings.budget_usd_day,
        "cap_month": settings.budget_usd_month,
        "over": s["day"] >= settings.budget_usd_day or s["month"] >= settings.budget_usd_month,
        # Past 80% of the month's cap the deep model is swapped for the cheap one.
        "saver": s["month"] >= 0.8 * settings.budget_usd_month,
    }


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("{"):]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise LLMError("model did not return JSON")
    return json.loads(text[start:end + 1])


def claude_calls_today(db: DB) -> int:
    lt = time.localtime()
    day_start = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    return db.one("SELECT COUNT(*) n FROM llm_usage WHERE ts>=? AND model LIKE 'claude:%'", (int(day_start),))["n"]


async def _claude_json(db: DB, settings: Settings, role: str, system: str, user: str, deep: bool) -> dict:
    """One call through the Claude Code CLI in print mode, on the plan the CLI is signed in with.

    No tools are offered, so the model can only read the prompt and answer. The
    prompt goes in on stdin because headlines in it are untrusted text.
    """
    if claude_calls_today(db) >= settings.claude_calls_day:
        raise BudgetExceeded(f"daily Claude call limit reached ({settings.claude_calls_day})")
    model = settings.claude_deep if deep else settings.claude_quick
    env = dict(os.environ)
    # An API key in the environment would be billed instead of the plan.
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(name, None)
    args = [settings.claude_bin, "-p", "--output-format", "json", "--model", model, "--system-prompt", system,
            "--tools", "", "--no-session-persistence", "--disable-slash-commands"]
    with tempfile.TemporaryDirectory(prefix="arah-claude-") as cwd:
        try:
            proc = await asyncio.create_subprocess_exec(
                *args, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, cwd=cwd, env=env)
            out, err = await asyncio.wait_for(proc.communicate(user.encode()), timeout=300)
        except asyncio.TimeoutError:
            proc.kill()
            raise LLMError("the Claude CLI did not answer within five minutes")
        except OSError as e:
            raise LLMError(f"could not start the Claude CLI: {e}")
    try:
        data = json.loads(out.decode() or "{}")
    except json.JSONDecodeError:
        data = {}
    if proc.returncode != 0 or data.get("is_error") or "result" not in data:
        detail = str(data.get("result") or err.decode()[-300:] or "no output").strip()
        low = detail.lower()
        kind = "auth" if ("login" in low or "authenticat" in low or "api key" in low) else \
            "limit" if ("limit" in low or "quota" in low) else "error"
        db.set("llm_error", {"at": int(time.time()), "kind": kind})
        raise LLMError(f"Claude CLI failed: {detail[:300]}")
    usage = data.get("usage") or {}
    # The plan is not billed per call. The CLI's list-price estimate is stored as 0 cost so
    # the dollar budget only counts OpenRouter; the call count is what limits Claude.
    db.x("INSERT INTO llm_usage (ts, model, role, tokens_in, tokens_out, cost_usd) VALUES (?,?,?,?,?,?)",
         (int(time.time()), f"claude:{model}", role,
          usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0) + usage.get("cache_read_input_tokens", 0),
          usage.get("output_tokens", 0), 0.0))
    db.set("llm_error", None)
    return _extract_json(str(data["result"]))


# After a provider refuses for credit, login or quota, skip it for a while instead of
# failing one request per call before every fallback.
SKIP_SECONDS = 30 * 60


async def chat_json(db: DB, settings: Settings, role: str, system: str, user: str, deep: bool = False,
                    max_tokens: int = 6000, temperature: float = 0.3) -> dict:
    """One JSON-returning call. Tries the main provider, then the fallback if one is set up."""
    order = settings.provider_order
    if not order:
        raise LLMError("no LLM provider configured")
    now = time.time()
    awake = [p for p in order if now - (db.get(f"llm_skip:{p}") or 0) > SKIP_SECONDS] or order
    last: Exception | None = None
    for i, provider in enumerate(awake):
        try:
            if provider == "claude":
                out = await _claude_json(db, settings, role, system, user, deep)
            else:
                out = await _openrouter_json(db, settings, role, system, user, deep, max_tokens, temperature)
            db.set("llm_last", {"at": int(time.time()), "provider": provider, "fallback": provider != order[0]})
            db.set("llm_error", None)
            return out
        except (LLMError, BudgetExceeded) as e:
            last = e
            if isinstance(e, BudgetExceeded) or (db.get("llm_error") or {}).get("kind") in ("credit", "auth", "limit"):
                db.set(f"llm_skip:{provider}", int(time.time()))
            if i + 1 < len(awake):
                log.warning("%s unavailable (%s); falling back to %s", provider, str(e)[:120], awake[i + 1])
    assert last is not None
    raise last


async def _openrouter_json(db: DB, settings: Settings, role: str, system: str, user: str, deep: bool,
                           max_tokens: int, temperature: float) -> dict:
    """One call through OpenRouter, with spend recorded against the dollar budget."""
    state = budget_state(db, settings)
    if state["over"]:
        raise BudgetExceeded(f"LLM budget reached (${state['month']:.2f} this month, ${state['day']:.2f} today)")
    model = settings.model_deep if deep and not state["saver"] else settings.model_quick
    headers = {"Authorization": f"Bearer {settings.openrouter_key}", "X-Title": "ARAH"}
    last: Exception | None = None
    async with httpx.AsyncClient(timeout=180) as client:
        for attempt in range(4):
            payload = {
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_object"},
                "temperature": temperature,
                # The limit covers hidden reasoning as well as the answer, so it is generous;
                # reasoning is kept light because the inputs are already digested.
                "max_tokens": max_tokens,
                "reasoning": {"effort": "low"},
                "usage": {"include": True},
            }
            try:
                r = await client.post(f"{settings.openrouter_url}/chat/completions", json=payload, headers=headers)
                if r.status_code == 402 and model != settings.model_quick:
                    # Not enough credit for the deep model: finish the job on the cheap one.
                    log.warning("not enough OpenRouter credit for %s; falling back to %s", model, settings.model_quick)
                    model = settings.model_quick
                    continue
                if r.status_code in (401, 402, 403):
                    db.set("llm_error", {"at": int(time.time()), "kind": "credit" if r.status_code == 402 else "auth"})
                    raise LLMError(f"OpenRouter refused the request ({r.status_code}): {r.text[:200]}")
                if r.status_code == 429 or r.status_code >= 500:
                    raise httpx.HTTPStatusError("retryable", request=r.request, response=r)
                r.raise_for_status()
                data = r.json()
                if "error" in data:
                    raise LLMError(str(data["error"])[:300])
                usage = data.get("usage") or {}
                tin, tout = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
                cost = usage.get("cost")
                if cost is None:
                    cost = tin * FALLBACK_PRICE["in"] + tout * FALLBACK_PRICE["out"]
                db.x("INSERT INTO llm_usage (ts, model, role, tokens_in, tokens_out, cost_usd) VALUES (?,?,?,?,?,?)",
                     (int(time.time()), model, role, tin, tout, float(cost)))
                choice = data["choices"][0]
                db.set("llm_error", None)
                if choice.get("finish_reason") == "length":
                    raise LLMError("the model ran out of tokens before finishing its answer")
                return _extract_json(choice["message"].get("content") or "")
            except LLMError:
                raise
            except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as e:
                last = e
                await asyncio.sleep(2 * (attempt + 1))
    raise LLMError(f"LLM call failed after retries: {last}")
