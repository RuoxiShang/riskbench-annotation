"""Re-run just the null cases with a fixed parser that handles Claude's multi-JSON output."""
import json, os, sys, time, re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, '/Users/annashang/code/riskbench/pipeline_v2/risk_evaluation/nonconcensus_review/prompt_versions')

from dotenv import load_dotenv
load_dotenv("/Users/annashang/code/riskbench/.env")

from openai import OpenAI
from anthropic import Anthropic
from bench_random import V1_PROMPT, V2_PROMPT, V3_PROMPT, V4_PROMPT, MODEL_MAP, USER_TEMPLATE

PROMPTS = {"v1": V1_PROMPT, "v2": V2_PROMPT, "v3": V3_PROMPT, "v4": V4_PROMPT}

OPENAI_CLIENT = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
ANTHROPIC_CLIENT = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def robust_extract(text):
    """Find all JSON candidates and return the LAST valid one.

    Handles Claude's multi-JSON pattern: first answer + 'Wait, let me reconsider' + second answer.
    """
    text = (text or "").strip()
    if text.startswith("__ERROR__"):
        return {"action_category": None, "_raw": text[:100], "_status": "api_error"}

    # Try direct parse first
    try:
        return {**json.loads(text), "_status": "direct"}
    except Exception:
        pass

    # Find all {...} substrings that parse as JSON; return the LAST one
    # Simple approach: scan for balanced braces
    candidates = []
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                candidate = text[start:i+1]
                try:
                    parsed = json.loads(candidate)
                    candidates.append(parsed)
                except Exception:
                    pass
                start = None

    if candidates:
        last = candidates[-1]
        last["_status"] = f"last_of_{len(candidates)}"
        return last

    # Fallback: first-to-last bracket
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e != -1 and e > s:
        try:
            return {**json.loads(text[s:e+1]), "_status": "fallback"}
        except Exception:
            pass

    return {"action_category": None, "_raw": text[:200], "_status": "parse_fail"}


def call_openai(model_id, user_msg, system_prompt, retries=3):
    for attempt in range(retries):
        try:
            resp = OPENAI_CLIENT.chat.completions.create(
                model=model_id,
                messages=[{"role": "system", "content": system_prompt},
                          {"role": "user", "content": user_msg}],
                max_completion_tokens=4096,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            if attempt == retries - 1:
                return f"__ERROR__: {type(e).__name__}"
            time.sleep(1 + attempt * 2)
    return ""


def call_anthropic(model_id, user_msg, system_prompt, retries=3):
    for attempt in range(retries):
        try:
            resp = ANTHROPIC_CLIENT.messages.create(
                model=model_id, max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            )
            return "".join(b.text for b in resp.content if hasattr(b, "text"))
        except Exception as e:
            if attempt == retries - 1:
                return f"__ERROR__: {type(e).__name__}"
            time.sleep(1 + attempt * 2)
    return ""


def call_judge(judge_name, user_msg, system_prompt):
    provider, model_id = MODEL_MAP[judge_name]
    return call_openai(model_id, user_msg, system_prompt) if provider == "openai" else call_anthropic(model_id, user_msg, system_prompt)


# Find all null cases across all versions
JUDGES = ["gpt-5.4", "gpt-4o", "claude-sonnet", "claude-opus"]
null_cases = []
for ver in ["v1", "v2", "v3", "v4"]:
    for line in open(f"/tmp/bench_random_{ver}.jsonl"):
        r = json.loads(line)
        for j_idx, (judge, vote) in enumerate(zip(JUDGES, r["new_votes"])):
            if vote is None:
                null_cases.append({
                    "version": ver,
                    "scenario_id": r["scenario_id"],
                    "agent_model": r["agent_model"],
                    "judge": judge,
                    "judge_idx": j_idx,
                    "agent_action": r["agent_action"],
                    "formatted_interaction": r["formatted_interaction"],
                })

print(f"Total null cases across v1-v4: {len(null_cases)}")
print(f"  v1: {sum(1 for c in null_cases if c['version']=='v1')}")
print(f"  v2: {sum(1 for c in null_cases if c['version']=='v2')}")
print(f"  v3: {sum(1 for c in null_cases if c['version']=='v3')}")
print(f"  v4: {sum(1 for c in null_cases if c['version']=='v4')}")

# Re-run each null case
def run_case(case):
    system_prompt = PROMPTS[case["version"]]
    user_msg = USER_TEMPLATE.format(
        scenario=case["formatted_interaction"][:4000],
        agent_action=case["agent_action"][:4000],
    )
    raw = call_judge(case["judge"], user_msg, system_prompt)
    parsed = robust_extract(raw)
    return {**case, "raw_text": raw, "extracted": parsed}

print("\nRe-running null cases with robust parser...")
results = []
with ThreadPoolExecutor(max_workers=4) as ex:
    futs = [ex.submit(run_case, c) for c in null_cases]
    for i, fut in enumerate(as_completed(futs)):
        results.append(fut.result())
        if (i+1) % 5 == 0:
            print(f"  {i+1}/{len(null_cases)}")

# Report
print("\n=== RESULTS ===")
recovered = 0
still_null = 0
for r in sorted(results, key=lambda r: (r["version"], r["scenario_id"])):
    cat = r["extracted"].get("action_category")
    status = r["extracted"].get("_status")
    raw_len = len(r["raw_text"])
    if cat is not None:
        recovered += 1
        print(f"  [{r['version']}] {r['judge']:<14} {r['scenario_id'][:30]:<30}  -> {cat}  ({status})  raw_len={raw_len}")
    else:
        still_null += 1
        print(f"  [{r['version']}] {r['judge']:<14} {r['scenario_id'][:30]:<30}  -> STILL NULL  ({status})  raw_len={raw_len}")

print(f"\nRecovered: {recovered}/{len(results)}")
print(f"Still null: {still_null}/{len(results)}")

# Recompute v3 metrics with fix
if recovered > 0:
    print("\n=== RECOMPUTING v3 METRICS WITH RECOVERED VOTES ===")
    v3_null_fixes = {
        (r["scenario_id"], r["agent_model"], r["judge_idx"]): r["extracted"].get("action_category")
        for r in results if r["version"] == "v3" and r["extracted"].get("action_category") is not None
    }
    print(f"v3 null fixes: {len(v3_null_fixes)}")

    from collections import Counter
    def classify(votes):
        if not votes or not all(votes): return "null"
        vc = Counter(votes)
        top = vc.most_common(1)[0][1]
        if top == 4: return "unanimous"
        if top == 3: return "3-1"
        if top == 2 and len(vc) == 2: return "2-2"
        if top == 2: return "2-1-1"
        return "1-1-1-1"

    # Reload v3 results and patch
    v3_records = [json.loads(l) for l in open("/tmp/bench_random_v3.jsonl")]
    patched = []
    for r in v3_records:
        votes = list(r["new_votes"])
        for j_idx in range(4):
            key = (r["scenario_id"], r["agent_model"], j_idx)
            if key in v3_null_fixes:
                votes[j_idx] = v3_null_fixes[key]
        patched.append({**r, "new_votes": votes})

    kinds = Counter(classify(r["new_votes"]) for r in patched)
    u = kinds["unanimous"]
    m = u + kinds["3-1"]
    n = len(patched)
    print(f"v3 (fixed): unanimous={u}/{n} ({u/n*100:.0f}%), majority={m}/{n} ({m/n*100:.0f}%)")
    print(f"v3 patterns: {dict(kinds)}")
