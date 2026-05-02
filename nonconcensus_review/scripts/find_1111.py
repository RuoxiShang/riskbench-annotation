"""Find records where all 4 judges disagree (1-1-1-1)."""
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
    records_by_id = {}
    for version in ("version_a", "version_b"):
        vdir = ROOT / agent / version
        if not vdir.exists(): continue
        for fp in sorted(vdir.glob("*.jsonl")):
            with open(fp) as f:
                for rec in json.load(f):
                    sid = rec.get("scenario_id")
                    if sid in records_by_id: continue
                    records_by_id[sid] = rec
    return list(records_by_id.values())

for agent in AGENTS:
    records = load_agent(agent)
    print(f"\n{'='*78}\nAGENT: {agent}  (N={len(records)})\n{'='*78}")
    for task_name, key in TASKS:
        hits = []
        for r in records:
            votes = r.get(key) or []
            # filter nulls from consideration
            valid = [v for v in votes if v is not None]
            if not valid: continue
            vc = Counter(valid)
            # 1-1-1-1 = 4 distinct labels each appearing once (from 4 judges, no nulls)
            if len(votes) == 4 and all(v is not None for v in votes) and len(vc) == 4:
                hits.append(r)
        print(f"  {task_name}: {len(hits)} records with 1-1-1-1")
        for r in hits[:3]:
            votes = r.get(key)
            sid = r.get("scenario_id")
            print(f"    {sid}  votes={votes}")
