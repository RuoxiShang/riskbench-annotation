"""Extract all Action 2-2 records with full context for manual review."""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/Users/annashang/code/riskbench/pipeline_v2/risk_evaluation/analysis/judge_mixed")
AGENTS = ["claude-sonnet", "claude-opus", "gpt-5.4"]
OUT = Path("/tmp/action_2_2_review.jsonl")

def load_agent(agent):
    recs = []
    by_id = set()
    for version in ("version_a", "version_b"):
        vdir = ROOT / agent / version
        if not vdir.exists(): continue
        for fp in sorted(vdir.glob("*.jsonl")):
            with open(fp) as f:
                for rec in json.load(f):
                    sid = rec.get("scenario_id")
                    if sid in by_id: continue
                    by_id.add(sid)
                    rec["_agent"] = agent
                    rec["_version"] = version
                    recs.append(rec)
    return recs

def classify_pattern(votes):
    valid = [v for v in votes if v is not None]
    if not valid: return None, None
    vc = Counter(valid)
    counts = tuple(sorted(vc.values(), reverse=True))
    if counts != (2,2): return None, None
    pattern = tuple(sorted(v if v is not None else "NULL" for v in votes))
    return pattern, "2-2"

rows = []
pattern_counts = Counter()
for agent in AGENTS:
    for rec in load_agent(agent):
        votes = rec.get("agent_action_votes") or []
        pat, cat = classify_pattern(votes)
        if cat != "2-2": continue
        pattern_counts[pat] += 1
        # Extract the 4 judge rationales
        judges = rec.get("per_judge_breakdown", [])
        judge_rows = []
        for j in judges:
            judge_rows.append({
                "model": j.get("model"),
                "action_category": j.get("action_category"),
                "action_explanation": j.get("action_explanation"),
            })
        rows.append({
            "scenario_id": rec.get("scenario_id"),
            "agent_model": rec.get("_agent"),
            "version": rec.get("_version"),
            "dimension_code": rec.get("dimension_code"),
            "truncation_type": rec.get("truncation_type"),
            "pattern": list(pat),
            "votes": votes,
            "formatted_interaction": rec.get("formatted_interaction", "")[:3000],
            "agent_thought": rec.get("agent_thought", "")[:1500],
            "agent_action": rec.get("agent_action", ""),
            "ground_truth_rationale": rec.get("ground_truth_rationale", ""),
            "safe_actions": rec.get("safe_actions"),
            "unsafe_action": rec.get("unsafe_action"),
            "agent_profile_snippet": (rec.get("agent_profile") or "")[:400],
            "per_judge": judge_rows,
        })

# Sort by pattern for easier review
pattern_order = [p for p, _ in pattern_counts.most_common()]
rows.sort(key=lambda r: (pattern_order.index(tuple(r["pattern"])), r["scenario_id"]))

with open(OUT, "w") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"Wrote {len(rows)} records to {OUT}")
print(f"\nPattern counts:")
for pat, cnt in pattern_counts.most_common():
    print(f"  {pat}  -> {cnt}")
