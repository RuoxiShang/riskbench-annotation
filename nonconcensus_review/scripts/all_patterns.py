"""All disagreement patterns for Detection, Action, Safety - per agent and pooled."""
import json
from collections import Counter, defaultdict
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

def pattern_category(votes):
    """Classify vote multiset as 4-0, 3-1, 2-2, 2-1-1, or 1-1-1-1."""
    valid = [v for v in votes if v is not None]
    if not valid: return None
    vc = Counter(valid)
    counts = tuple(sorted(vc.values(), reverse=True))
    # Also note nulls
    if counts == (4,): return "4-0"
    if counts == (3,1): return "3-1"
    if counts == (2,2): return "2-2"
    if counts == (2,1,1): return "2-1-1"
    if counts == (1,1,1,1): return "1-1-1-1"
    # handle records with nulls
    if counts == (3,): return "3-0-NULL"
    if counts == (2,1): return "2-1-NULL"
    if counts == (1,1,1): return "1-1-1-NULL"
    return f"other-{counts}"

def sorted_pat(votes):
    return tuple(sorted(v if v is not None else "NULL" for v in votes))

# Pool all records across agents
pooled_records = []
per_agent_records = {}
for agent in AGENTS:
    recs = load_agent(agent)
    per_agent_records[agent] = recs
    pooled_records.extend(recs)

for task_name, key in TASKS:
    print(f"\n{'='*90}")
    print(f"TASK: {task_name}   (votes field: {key})")
    print(f"{'='*90}")

    # Pooled by category first
    cat_counts = Counter()
    pat_by_cat = defaultdict(Counter)      # category -> pattern -> count
    pat_by_cat_agent = defaultdict(lambda: defaultdict(Counter))  # cat -> pat -> agent -> count

    for agent, recs in per_agent_records.items():
        for r in recs:
            votes = r.get(key) or []
            if not votes: continue
            cat = pattern_category(votes)
            pat = sorted_pat(votes)
            cat_counts[cat] += 1
            pat_by_cat[cat][pat] += 1
            pat_by_cat_agent[cat][pat][agent] += 1

    total = sum(cat_counts.values())
    print(f"\nPooled across {len(AGENTS)} agents - category summary (N={total}):")
    for cat in ["4-0", "3-1", "2-2", "2-1-1", "1-1-1-1"]:
        c = cat_counts.get(cat, 0)
        print(f"  {cat:<8}  {c:>5}  ({c/total*100:5.1f}%)")
    other_total = sum(c for k,c in cat_counts.items() if k not in {"4-0","3-1","2-2","2-1-1","1-1-1-1"})
    if other_total:
        print(f"  (with NULLs / other): {other_total}")

    # Non-unanimous patterns
    print(f"\nAll non-unanimous patterns (pooled, with per-agent breakdown):")
    for cat in ["3-1", "2-2", "2-1-1", "1-1-1-1"]:
        pats = pat_by_cat.get(cat, {})
        if not pats: continue
        total_cat = sum(pats.values())
        print(f"\n  --- {cat}  (total {total_cat} records) ---")
        # sort patterns by count desc
        for pat, cnt in sorted(pats.items(), key=lambda x: -x[1]):
            per_ag = pat_by_cat_agent[cat][pat]
            ag_str = "  ".join(f"{a[:6]}={per_ag.get(a,0)}" for a in AGENTS)
            print(f"    {str(pat):<40} total={cnt:>4}   {ag_str}")
