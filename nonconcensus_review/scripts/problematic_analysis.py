"""Distribution of 'problematic' records: top vote share < 3/4 (75%)."""
import json
from collections import Counter
from pathlib import Path

BASE = Path("/Users/annashang/code/riskbench/pipeline_v2/risk_evaluation/agent_outputs_evaluation/judge_mixed")
THRESHOLD = 0.75  # below 3/4 = problematic

FILES = {
    "claude-sonnet": BASE / "agent_eval_claude-sonnet_judge_mixed.jsonl",
    "claude-opus":   BASE / "agent_eval_claude-opus_judge_mixed.jsonl",
    "gpt-5.4":       BASE / "agent_eval_gpt-5.4_judge_mixed.jsonl",
}

TASKS = [
    ("Detection", "agent_thought_detection_votes"),
    ("Action",    "agent_action_votes"),
    ("Safety",    "agent_action_safety_votes"),
]

def top_share(votes):
    valid = [v for v in votes if v is not None]
    if not valid:
        return None
    return Counter(valid).most_common(1)[0][1] / len(valid)

def load(path):
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]

for agent, path in FILES.items():
    records = load(path)
    n_records = len(records)
    # infer num judges
    nj = 0
    for r in records:
        v = r.get("agent_thought_detection_votes") or []
        if v:
            nj = len(v); break
    print(f"\n{'='*78}\nAGENT: {agent}  (N={n_records}, judges={nj})\n{'='*78}")

    # --- per-task problematic counts ---
    print(f"\n  Per-axis: records with top-vote share < {THRESHOLD:.0%}")
    per_axis_flagged = {}  # task_name -> set of record indices
    for task_name, key in TASKS:
        flagged = set()
        patterns = Counter()
        for i, rec in enumerate(records):
            votes = rec.get(key, [])
            share = top_share(votes)
            if share is None:
                continue
            if share < THRESHOLD:
                flagged.add(i)
                pat = tuple(sorted(v if v is not None else "NULL" for v in votes))
                patterns[pat] += 1
        per_axis_flagged[task_name] = flagged
        pct = len(flagged) / n_records * 100
        print(f"    {task_name:<10}: {len(flagged):>5} ({pct:5.1f}%)")
        for pat, cnt in patterns.most_common(5):
            print(f"      {pat}  ->  {cnt}")

    # --- aggregate: records flagged on ≥1 axis ---
    any_flagged = set().union(*per_axis_flagged.values())
    all_flagged = set(range(n_records))
    for s in per_axis_flagged.values():
        all_flagged &= s
    print(f"\n  Aggregate across axes:")
    print(f"    flagged on ≥1 axis : {len(any_flagged):>5} ({len(any_flagged)/n_records*100:5.1f}%)")
    print(f"    flagged on all 3   : {len(all_flagged):>5} ({len(all_flagged)/n_records*100:5.1f}%)")

    # --- how many axes flagged per record ---
    axis_count = Counter()
    for i in range(n_records):
        c = sum(1 for s in per_axis_flagged.values() if i in s)
        axis_count[c] += 1
    print(f"\n  Records by # of problematic axes:")
    for k in sorted(axis_count):
        print(f"    {k} axes flagged: {axis_count[k]:>5} ({axis_count[k]/n_records*100:5.1f}%)")
