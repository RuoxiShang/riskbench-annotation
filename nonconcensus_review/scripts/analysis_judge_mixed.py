"""Re-run agreement + problematic analysis using analysis/judge_mixed/ buckets.

Files there are JSON arrays (pretty-printed) of records that landed in each
(D, A, safe/unsafe) cell after majority voting, split by version_a/version_b.
We load all buckets per agent, dedup on scenario_id, and compute metrics.
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path("/Users/annashang/code/riskbench/pipeline_v2/risk_evaluation/analysis/judge_mixed")
THRESHOLD = 0.75

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
        if not vdir.exists():
            continue
        for fp in sorted(vdir.glob("*.jsonl")):
            with open(fp) as f:
                arr = json.load(f)
            for rec in arr:
                sid = rec.get("scenario_id")
                if sid in records_by_id:
                    continue
                rec["_version"] = version
                records_by_id[sid] = rec
    return list(records_by_id.values())

def classify(votes):
    if not votes: return "no_data", None
    valid = [v for v in votes if v is not None]
    if not valid: return "no_data", None
    vc = Counter(valid)
    top = vc.most_common(1)[0][1]
    n = sum(vc.values())
    if len(vc) == 1: return "unanimous", top / len(votes)
    if top > n / 2:  return "majority",  top / len(votes)
    return "split", top / len(votes)

def top_share(votes):
    if not votes: return None
    valid = [v for v in votes if v is not None]
    if not valid: return None
    return Counter(valid).most_common(1)[0][1] / len(valid)

for agent in AGENTS:
    records = load_agent(agent)
    n = len(records)
    nj = 0
    for r in records:
        v = r.get("agent_thought_detection_votes") or []
        if v:
            nj = len(v); break
    print(f"\n{'='*78}\nAGENT: {agent}  (unique records={n}, judges={nj})\n{'='*78}")
    if n == 0:
        continue

    # agreement breakdown per axis
    print(f"\n  Agreement breakdown:")
    for task_name, key in TASKS:
        kinds = Counter()
        for r in records:
            k, _ = classify(r.get(key) or [])
            kinds[k] += 1
        total = sum(kinds.values())
        print(f"    {task_name:<10}: "
              f"unanimous={kinds['unanimous']} ({kinds['unanimous']/total*100:.1f}%)  "
              f"majority={kinds['majority']} ({kinds['majority']/total*100:.1f}%)  "
              f"split={kinds['split']} ({kinds['split']/total*100:.1f}%)  "
              f"no_data={kinds['no_data']}")

    # problematic (<3/4 share) per axis + aggregate
    print(f"\n  Problematic (top share < {THRESHOLD:.0%}):")
    per_axis = {}
    for task_name, key in TASKS:
        flagged = set()
        patterns = Counter()
        for i, r in enumerate(records):
            votes = r.get(key) or []
            s = top_share(votes)
            if s is None: continue
            if s < THRESHOLD:
                flagged.add(i)
                pat = tuple(sorted(v if v is not None else "NULL" for v in votes))
                patterns[pat] += 1
        per_axis[task_name] = flagged
        print(f"    {task_name:<10}: {len(flagged)} ({len(flagged)/n*100:.1f}%)")
        for pat, cnt in patterns.most_common(5):
            print(f"      {pat} -> {cnt}")

    any_flag = set().union(*per_axis.values())
    all_flag = set(range(n))
    for s in per_axis.values():
        all_flag &= s
    # cross-axis overlap (any kind of non-unanimous, not just problematic)
    def is_disagree(votes):
        k, _ = classify(votes or [])
        return k in ("majority", "split")
    d_dis = a_dis = s_dis = 0
    any_dis = all_dis = 0
    d_only = a_only = s_only = 0
    for r in records:
        dv = r.get("agent_thought_detection_votes") or []
        av = r.get("agent_action_votes") or []
        sv = r.get("agent_action_safety_votes") or []
        dd = is_disagree(dv); aa = is_disagree(av); ss = is_disagree(sv)
        d_dis += dd; a_dis += aa; s_dis += ss
        if dd or aa or ss: any_dis += 1
        if dd and aa and ss: all_dis += 1
        if dd and not aa and not ss: d_only += 1
        if aa and not dd and not ss: a_only += 1
        if ss and not dd and not aa: s_only += 1
    print(f"\n  Cross-axis (any non-unanimous, i.e. majority+split):")
    print(f"    any axis    : {any_dis} ({any_dis/n*100:.1f}%)")
    print(f"    all 3 axes  : {all_dis} ({all_dis/n*100:.1f}%)")
    print(f"    det-only    : {d_only}")
    print(f"    act-only    : {a_only}")
    print(f"    saf-only    : {s_only}")
    print(f"\n  Problematic aggregate (<3/4):")
    print(f"    ≥1 axis flagged : {len(any_flag)} ({len(any_flag)/n*100:.1f}%)")
    print(f"    all 3 flagged   : {len(all_flag)} ({len(all_flag)/n*100:.1f}%)")
