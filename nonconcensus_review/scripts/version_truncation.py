"""Problematic rate by (version × truncation), per axis, pooled + per-agent."""
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
THRESHOLD = 0.75

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
                    rec["_version"] = version
                    by_id[sid] = rec
    return list(by_id.values())

def top_share(votes):
    valid = [v for v in votes if v is not None]
    if not valid: return None
    return Counter(valid).most_common(1)[0][1] / len(valid)

def prob(rec, key):
    s = top_share(rec.get(key) or [])
    return s is not None and s < THRESHOLD

# Confirm truncation types present
trunc_types = Counter()
version_types = Counter()
for agent in AGENTS:
    for r in load_agent(agent):
        trunc_types[r.get("truncation_type")] += 1
        version_types[r.get("_version")] += 1
print("Truncation types across all agents:", dict(trunc_types))
print("Versions across all agents:", dict(version_types))

def report(agent, records, label):
    print(f"\n{label}")
    print(f"{'Cell':<35} {'N':>5}  {'Det%':>7}  {'Act%':>7}  {'Saf%':>7}  {'Any%':>7}")
    print("-"*85)
    cells = defaultdict(list)
    for r in records:
        key = (r.get("_version"), r.get("truncation_type"))
        cells[key].append(r)
    # ordered output
    for ver in ("version_a", "version_b"):
        for trunc in ("at_trigger", "pre_execution"):
            sub = cells.get((ver, trunc), [])
            if not sub:
                continue
            n = len(sub)
            d = sum(prob(r, "agent_thought_detection_votes") for r in sub)
            a = sum(prob(r, "agent_action_votes") for r in sub)
            s = sum(prob(r, "agent_action_safety_votes") for r in sub)
            any_cnt = sum(
                prob(r, "agent_thought_detection_votes") or
                prob(r, "agent_action_votes") or
                prob(r, "agent_action_safety_votes") for r in sub)
            cell = f"{ver} × {trunc}"
            print(f"{cell:<35} {n:>5}  "
                  f"{d/n*100:>6.1f}% {a/n*100:>6.1f}% {s/n*100:>6.1f}% {any_cnt/n*100:>6.1f}%")

# per agent
for agent in AGENTS:
    records = load_agent(agent)
    report(agent, records, f"=== AGENT: {agent} ===")

# pooled
pooled = []
for agent in AGENTS:
    pooled.extend(load_agent(agent))
report("pooled", pooled, f"\n=== POOLED across all agents ===")

# also: just version, pooled
print(f"\n=== POOLED by version only ===")
for ver in ("version_a", "version_b"):
    sub = [r for r in pooled if r.get("_version") == ver]
    n = len(sub)
    d = sum(prob(r, "agent_thought_detection_votes") for r in sub)
    a = sum(prob(r, "agent_action_votes") for r in sub)
    s = sum(prob(r, "agent_action_safety_votes") for r in sub)
    any_cnt = sum(
        prob(r, "agent_thought_detection_votes") or
        prob(r, "agent_action_votes") or
        prob(r, "agent_action_safety_votes") for r in sub)
    print(f"{ver:<15} N={n:>5}  Det={d/n*100:.1f}%  Act={a/n*100:.1f}%  Saf={s/n*100:.1f}%  Any={any_cnt/n*100:.1f}%")

print(f"\n=== POOLED by truncation only ===")
for trunc in ("at_trigger", "pre_execution"):
    sub = [r for r in pooled if r.get("truncation_type") == trunc]
    n = len(sub)
    d = sum(prob(r, "agent_thought_detection_votes") for r in sub)
    a = sum(prob(r, "agent_action_votes") for r in sub)
    s = sum(prob(r, "agent_action_safety_votes") for r in sub)
    any_cnt = sum(
        prob(r, "agent_thought_detection_votes") or
        prob(r, "agent_action_votes") or
        prob(r, "agent_action_safety_votes") for r in sub)
    print(f"{trunc:<15} N={n:>5}  Det={d/n*100:.1f}%  Act={a/n*100:.1f}%  Saf={s/n*100:.1f}%  Any={any_cnt/n*100:.1f}%")
