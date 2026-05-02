"""Break the 'split' bucket into 2-2, 2-1-1, and 1-1-1-1."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path("/Users/annashang/code/riskbench/pipeline_v2/risk_evaluation/analysis/judge_mixed")
AGENTS = ["claude-sonnet", "claude-opus", "gpt-5.4"]
TASKS = [
    ("Detection", "agent_thought_detection_votes"),
    ("Action",    "agent_action_votes"),
    ("Safety",    "agent_action_safety_votes"),
]

def load_agent(agent):
    by_id = {}
    for version in ("version_a", "version_b"):
        vdir = ROOT / agent / version
        if not vdir.exists(): continue
        for fp in sorted(vdir.glob("*.jsonl")):
            with open(fp) as f:
                for rec in json.load(f):
                    sid = rec.get("scenario_id")
                    if sid in by_id: continue
                    by_id[sid] = rec
    return list(by_id.values())

for agent in AGENTS:
    records = load_agent(agent)
    print(f"\n=== {agent} (N={len(records)}) ===")
    for task_name, key in TASKS:
        c22 = c211 = c1111 = 0
        total = 0
        for r in records:
            votes = r.get(key) or []
            valid = [v for v in votes if v is not None]
            if not valid: continue
            total += 1
            vc = Counter(valid)
            top = vc.most_common(1)[0][1]
            n = sum(vc.values())
            if top <= n/2:  # this is a "split" in our original def
                # sub-classify by the vote count multiset
                counts = tuple(sorted(vc.values(), reverse=True))
                if counts == (2,2): c22 += 1
                elif counts == (2,1,1): c211 += 1
                elif counts == (1,1,1,1): c1111 += 1
                else: pass  # could happen with <4 valid votes (nulls)
        print(f"  {task_name:<10}: 2-2={c22}  2-1-1={c211}  1-1-1-1={c1111}  (total split={c22+c211+c1111})")
