"""Per-dimension problematic rate (top vote share < 3/4)."""
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
                    by_id[sid] = rec
    return list(by_id.values())

def top_share(votes):
    valid = [v for v in votes if v is not None]
    if not valid: return None
    return Counter(valid).most_common(1)[0][1] / len(valid)

def prob(rec, key):
    s = top_share(rec.get(key) or [])
    return s is not None and s < THRESHOLD

# canonical dimension order
DIM_ORDER = [
    "ORIGINAL",
    "RS1_HARM_INTENSITY", "RS2_SCOPE_SCALE", "RS3_TARGET",
    "RS4_DEPENDENCY", "RS5_OVERSIGHT", "RS6_REVERSIBILITY",
    "SD1_AMBIGUITY", "SD2_PROVENANCE", "SD3_OBFUSCATION",
    "SD4_EMOTIONAL", "SD5_DISTRACTION",
]

for agent in AGENTS:
    records = load_agent(agent)
    print(f"\n{'='*100}\nAGENT: {agent}  (N={len(records)})\n{'='*100}")
    print(f"{'Dimension':<22} {'N':>5}  "
          f"{'Det%':>7}  {'Act%':>7}  {'Saf%':>7}  {'Any%':>7}")
    print("-"*100)
    for dim in DIM_ORDER:
        sub = [r for r in records if r.get("dimension_code") == dim]
        if not sub: continue
        n = len(sub)
        d = sum(prob(r, "agent_thought_detection_votes") for r in sub)
        a = sum(prob(r, "agent_action_votes") for r in sub)
        s = sum(prob(r, "agent_action_safety_votes") for r in sub)
        any_cnt = sum(
            prob(r, "agent_thought_detection_votes") or
            prob(r, "agent_action_votes") or
            prob(r, "agent_action_safety_votes") for r in sub
        )
        print(f"{dim:<22} {n:>5}  "
              f"{d/n*100:>6.1f}% {a/n*100:>6.1f}% {s/n*100:>6.1f}% {any_cnt/n*100:>6.1f}%")

# pooled across agents
print(f"\n{'='*100}\nPOOLED across all agents\n{'='*100}")
pooled = defaultdict(lambda: {"n":0, "d":0, "a":0, "s":0, "any":0})
for agent in AGENTS:
    for r in load_agent(agent):
        dim = r.get("dimension_code")
        pooled[dim]["n"] += 1
        dp = prob(r, "agent_thought_detection_votes")
        ap = prob(r, "agent_action_votes")
        sp = prob(r, "agent_action_safety_votes")
        pooled[dim]["d"] += dp
        pooled[dim]["a"] += ap
        pooled[dim]["s"] += sp
        pooled[dim]["any"] += (dp or ap or sp)
print(f"{'Dimension':<22} {'N':>5}  "
      f"{'Det%':>7}  {'Act%':>7}  {'Saf%':>7}  {'Any%':>7}")
print("-"*100)
for dim in DIM_ORDER:
    p = pooled.get(dim)
    if not p or p["n"] == 0: continue
    n = p["n"]
    print(f"{dim:<22} {n:>5}  "
          f"{p['d']/n*100:>6.1f}% {p['a']/n*100:>6.1f}% {p['s']/n*100:>6.1f}% {p['any']/n*100:>6.1f}%")
