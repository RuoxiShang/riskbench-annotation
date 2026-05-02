"""Extract Action 2-1-1 and 1-1-1-1 records with full context for review."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path("/Users/annashang/code/riskbench/pipeline_v2/risk_evaluation/analysis/judge_mixed")
AGENTS = ["claude-sonnet", "claude-opus", "gpt-5.4"]
OUT_211 = Path("/tmp/action_2_1_1_review.jsonl")
OUT_1111 = Path("/tmp/action_1_1_1_1_review.jsonl")

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
    if not valid or len(votes) != 4: return None, None
    vc = Counter(valid)
    counts = tuple(sorted(vc.values(), reverse=True))
    if counts == (2, 1, 1): return "2-1-1", tuple(sorted(v if v is not None else "NULL" for v in votes))
    if counts == (1, 1, 1, 1): return "1-1-1-1", tuple(sorted(v if v is not None else "NULL" for v in votes))
    return None, None

rows_211 = []
rows_1111 = []
pattern_counts_211 = Counter()
pattern_counts_1111 = Counter()
# also track 3-category-combination for 2-1-1 clustering
combo_counts_211 = Counter()
# track top-vote for 2-1-1
top_label_211 = Counter()

for agent in AGENTS:
    for rec in load_agent(agent):
        votes = rec.get("agent_action_votes") or []
        cat, pat = classify_pattern(votes)
        if cat is None: continue

        judges = rec.get("per_judge_breakdown", [])
        judge_rows = []
        for j in judges:
            judge_rows.append({
                "model": j.get("model"),
                "action_category": j.get("action_category"),
                "action_explanation": j.get("action_explanation"),
            })

        row = {
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
        }
        if cat == "2-1-1":
            rows_211.append(row)
            pattern_counts_211[pat] += 1
            # categories involved (distinct)
            vc = Counter(votes)
            cats_involved = frozenset(vc.keys())
            combo_counts_211[cats_involved] += 1
            # top label
            top = vc.most_common(1)[0][0]
            top_label_211[top] += 1
        else:
            rows_1111.append(row)
            pattern_counts_1111[pat] += 1

# write files
with open(OUT_211, "w") as f:
    for r in rows_211:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
with open(OUT_1111, "w") as f:
    for r in rows_1111:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"Wrote {len(rows_211)} records to {OUT_211}")
print(f"Wrote {len(rows_1111)} records to {OUT_1111}")

print(f"\n2-1-1 pattern counts (all {len(pattern_counts_211)} distinct patterns):")
for pat, cnt in pattern_counts_211.most_common():
    print(f"  {pat}  -> {cnt}")

print(f"\n2-1-1 by 3-category-combination (top 15):")
for combo, cnt in combo_counts_211.most_common(15):
    print(f"  {sorted(combo)}  -> {cnt}")

print(f"\n2-1-1 by TOP vote label:")
for lab, cnt in top_label_211.most_common():
    print(f"  {lab}  -> {cnt}")

print(f"\n1-1-1-1 patterns (all):")
for pat, cnt in pattern_counts_1111.most_common():
    print(f"  {pat}  -> {cnt}")
