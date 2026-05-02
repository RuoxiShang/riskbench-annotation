"""Summarize judge (dis)agreement across the judge_mixed eval files."""
import json
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path("/Users/annashang/code/riskbench/pipeline_v2/risk_evaluation/agent_outputs_evaluation/judge_mixed")

FILES = {
    "claude-sonnet": BASE / "agent_eval_claude-sonnet_judge_mixed.jsonl",
    "claude-opus":   BASE / "agent_eval_claude-opus_judge_mixed.jsonl",
    "gpt-5.4":       BASE / "agent_eval_gpt-5.4_judge_mixed.jsonl",
}

TASKS = [
    ("Detection (D0-D3)", "agent_thought_detection_votes"),
    ("Action    (A0-A5)", "agent_action_votes"),
    ("Safety (SAFE/UNSAFE)", "agent_action_safety_votes"),
]

def classify(votes):
    """Return (kind, pattern) where kind in {unanimous, majority, split, no_data},
    and pattern is a sorted tuple of the votes (with Nones marked)."""
    if not votes:
        return "no_data", tuple()
    marked = tuple(sorted([v if v is not None else "NULL" for v in votes]))
    vc = Counter(v for v in votes if v is not None)
    if not vc:
        return "no_data", marked
    top = vc.most_common(1)[0][1]
    n = sum(vc.values())
    if top == n and len(vc) == 1:
        return "unanimous", marked
    if top > n / 2:
        return "majority", marked
    return "split", marked

def load(path):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]

def summarize(agent, records):
    print(f"\n{'='*78}\nAGENT: {agent}  (N={len(records)})\n{'='*78}")
    for task_name, key in TASKS:
        kinds = Counter()
        patterns = Counter()          # disagreement patterns only
        pattern_all = Counter()       # all patterns
        null_rows = 0
        for rec in records:
            votes = rec.get(key, [])
            kind, pat = classify(votes)
            kinds[kind] += 1
            pattern_all[pat] += 1
            if kind in ("majority", "split"):
                patterns[pat] += 1
            if any(v is None for v in (votes or [])):
                null_rows += 1

        total = sum(kinds.values())
        print(f"\n  {task_name}")
        print(f"    unanimous : {kinds['unanimous']:>5} ({kinds['unanimous']/total*100:5.1f}%)")
        print(f"    majority  : {kinds['majority']:>5} ({kinds['majority']/total*100:5.1f}%)")
        print(f"    split     : {kinds['split']:>5} ({kinds['split']/total*100:5.1f}%)")
        print(f"    no_data   : {kinds['no_data']:>5} ({kinds['no_data']/total*100:5.1f}%)")
        print(f"    rows with any NULL vote: {null_rows}")
        print(f"    top disagreement patterns (votes tuple -> count):")
        for pat, cnt in patterns.most_common(10):
            print(f"      {pat}  ->  {cnt}")

def cross_task(records, agent):
    """How often does detection/action/safety disagree TOGETHER on the same record?"""
    print(f"\n  --- Cross-task disagreement overlap for {agent} ---")
    d = 0; a = 0; s = 0
    d_only = 0; a_only = 0; s_only = 0
    any_disagree = 0; all_disagree = 0
    for rec in records:
        dv = rec.get("agent_thought_detection_votes", [])
        av = rec.get("agent_action_votes", [])
        sv = rec.get("agent_action_safety_votes", [])
        d_dis = classify(dv)[0] in ("majority", "split")
        a_dis = classify(av)[0] in ("majority", "split")
        s_dis = classify(sv)[0] in ("majority", "split") if sv else False
        d += d_dis; a += a_dis; s += s_dis
        if d_dis and not a_dis and not s_dis: d_only += 1
        if a_dis and not d_dis and not s_dis: a_only += 1
        if s_dis and not d_dis and not a_dis: s_only += 1
        if d_dis or a_dis or s_dis: any_disagree += 1
        if d_dis and a_dis and s_dis: all_disagree += 1
    n = len(records)
    print(f"    any-axis disagreement    : {any_disagree} ({any_disagree/n*100:.1f}%)")
    print(f"    all three axes disagree  : {all_disagree} ({all_disagree/n*100:.1f}%)")
    print(f"    detection-only disagree  : {d_only}")
    print(f"    action-only disagree     : {a_only}")
    print(f"    safety-only disagree     : {s_only}")

for agent, path in FILES.items():
    if not path.exists():
        print(f"MISSING: {path}")
        continue
    records = load(path)
    summarize(agent, records)
    cross_task(records, agent)
