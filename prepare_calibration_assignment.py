#!/usr/bin/env python3
"""Build the final-human-review bundle.

Selects 134 items from calibration_labeler_sheet.jsonl + calibration_metadata.jsonl:
  - all 69 tie22 items
  - all 38 two_one_one items
  - 1 per unanimous cell  (12 cells)
  - 1 per majority cell   (15 cells)

Assigns 3 core-6 annotators per item (each gets 67 items, axis-interleaved) plus
a stratified ~50-item bonus list for each of 3 optional annotators.

Output: final_human_review_data.json — a single inline bundle consumed by
final-human-review.html as `const DATA = {...}`.
"""
import argparse
import json
import random
import zlib
from collections import Counter, defaultdict
from pathlib import Path

CORE = ["Anna", "Orfeas", "Yu", "Christina", "Ani", "Rico"]
BONUS = ["Manos", "Chryssa", "Shang Hong"]
SEED = 42
BONUS_SIZE = 50


def cell_key(stratum):
    """Canonical hashable key for a (axis, state, key) cell."""
    k = stratum["key"]
    if isinstance(k, list):
        k = tuple(k)
    return (stratum["axis"], stratum["state"], k)


def load_rows(sheet_path, meta_path):
    sheet = {int(json.loads(l)["row_id"]): json.loads(l)
             for l in open(sheet_path) if l.strip()}
    meta  = {int(json.loads(l)["row_id"]): json.loads(l)
             for l in open(meta_path)  if l.strip()}
    rows = []
    for rid, s in sheet.items():
        m = meta[rid]
        rows.append({
            "row_id":            rid,
            "scenario_id":       s["scenario_id"],
            "axis_to_label":     s["axis_to_label"],
            "allowed_values":    s["allowed_values"],
            "scenario_context":  s["scenario_context"],
            "agent_thought":     s["agent_thought"],
            "agent_action":      s["agent_action"],
            "ground_truth_rationale": s["ground_truth_rationale"],
            "agent_source":      m["agent_source"],
            "primary_stratum":   m["primary_stratum"],
            "_cell":             cell_key(m["primary_stratum"]),
        })
    return rows


def select_items(rows):
    """Apply the 134-item selection schema."""
    by_state = defaultdict(list)
    for r in rows:
        by_state[r["primary_stratum"]["state"]].append(r)

    selected = []
    selected += by_state["tie22"]
    selected += by_state["two_one_one"]

    rng = random.Random(SEED)
    for state in ("unanimous", "majority"):
        cells = defaultdict(list)
        for r in by_state[state]:
            cells[r["_cell"]].append(r)
        for cell in sorted(cells.keys(), key=str):
            items = sorted(cells[cell], key=lambda x: x["row_id"])
            selected.append(rng.choice(items))

    return selected


AXIS_ORDER = {"safety": 0, "detection": 1, "action": 2}
STATE_RANK = {"unanimous": 0, "majority": 1, "tie22": 2, "two_one_one": 3}


def order_items(items, seed):
    """Per-annotator ordering:
      1. Axis blocks in AXIS_ORDER (safety → detection → action).
      2. Inside each axis block, difficulty ascending
         (unanimous → majority → tie22 → 2-1-1).
      3. Random shuffle within each (axis, state) bucket (per-annotator seed).
      4. Scenario clustering within an axis block: when the same scenario_id
         appears more than once inside the same axis block, later occurrences
         are pulled to sit right after the first. Cross-axis same-scenario
         pairs are NOT clustered (they live in different blocks by design).
    """
    rng = random.Random(seed)

    # Bucket by (axis, state) and shuffle within each bucket.
    buckets = defaultdict(list)
    for it in items:
        buckets[(it["axis_to_label"], it["primary_stratum"]["state"])].append(it)
    for k in buckets:
        rng.shuffle(buckets[k])

    # Flatten: axis blocks × difficulty ascending within each axis.
    ordered = []
    axes = sorted({k[0] for k in buckets}, key=AXIS_ORDER.get)
    for axis in axes:
        for state in sorted(
                {k[1] for k in buckets if k[0] == axis}, key=STATE_RANK.get):
            ordered.extend(buckets[(axis, state)])

    # Scenario clustering — only within the same axis block.
    by_sid_axis = defaultdict(list)
    for i, it in enumerate(ordered):
        by_sid_axis[(it["scenario_id"], it["axis_to_label"])].append(i)

    to_relocate = []  # list of indices to pop out (the later occurrences)
    for positions in by_sid_axis.values():
        if len(positions) < 2:
            continue
        for other in positions[1:]:
            to_relocate.append(other)

    # Pop in reverse index order so earlier indices remain valid.
    to_relocate.sort(reverse=True)
    relocated_by_key = defaultdict(list)
    for src_idx in to_relocate:
        item = ordered.pop(src_idx)
        key = (item["scenario_id"], item["axis_to_label"])
        relocated_by_key[key].append(item)

    # Re-insert each relocated row immediately after its scenario's first
    # occurrence within the same axis, in easy-first order inside the cluster.
    for key, extras in relocated_by_key.items():
        sid, axis = key
        first_idx = next(i for i, it in enumerate(ordered)
                         if it["scenario_id"] == sid and it["axis_to_label"] == axis)
        extras.sort(key=lambda it: STATE_RANK[it["primary_stratum"]["state"]])
        for k, extra in enumerate(extras):
            ordered.insert(first_idx + 1 + k, extra)

    return ordered


def assign_core(selected):
    """Each item → 3 distinct core annotators.

    Uses a balanced-greedy algorithm: for each item, pick the 3 annotators
    currently most behind schedule (lowest item-count so far), breaking ties
    deterministically by per-annotator hash. Guarantees:
      - Every item has 3 distinct coverers.
      - Every annotator ends with exactly ⌊n_items · 3 / 6⌋ = 67 items.
      - Pair co-occurrences stay near the theoretical average (~27 per pair),
        never 0 for any pair, unlike a fixed-offset rotation.
    Items are iterated in stratified order so each annotator's final list is
    balanced across (axis × state).
    """
    rng = random.Random(SEED)
    by_stratum = defaultdict(list)
    for it in selected:
        s = it["primary_stratum"]
        by_stratum[(s["axis"], s["state"])].append(it)
    ordered = []
    for key in sorted(by_stratum.keys()):
        group = by_stratum[key][:]
        rng.shuffle(group)
        ordered.extend(group)

    counts = {name: 0 for name in CORE}
    assignments = {name: [] for name in CORE}
    for it in ordered:
        # Sort by (count, per-item-random) ascending so ties break differently
        # each round. Using the outer rng keeps the whole assignment
        # deterministic across reruns.
        picked = sorted(CORE, key=lambda n: (counts[n], rng.random()))[:3]
        for a in picked:
            assignments[a].append(it["row_id"])
            counts[a] += 1
    return assignments


def assign_bonus(selected):
    """Each optional annotator gets an independent ~BONUS_SIZE stratified
    sample of selected items. These labels are 4th+ bonus votes — no
    coordination with core assignments."""
    by_stratum = defaultdict(list)
    for it in selected:
        s = it["primary_stratum"]
        by_stratum[(s["axis"], s["state"])].append(it)

    assignments = {}
    for i, name in enumerate(BONUS):
        rng = random.Random(SEED + 100 + i)
        total = sum(len(v) for v in by_stratum.values())
        picks = []
        for key, items in sorted(by_stratum.items()):
            take = round(BONUS_SIZE * len(items) / total)
            take = min(take, len(items))
            picks.extend(rng.sample(items, take))
        while len(picks) < BONUS_SIZE:
            rest = [it for it in selected if it["row_id"] not in {p["row_id"] for p in picks}]
            if not rest:
                break
            picks.append(rng.choice(rest))
        picks = picks[:BONUS_SIZE]
        assignments[name] = [p["row_id"] for p in picks]
    return assignments


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet", default="data/calibration_labeler_sheet.jsonl")
    parser.add_argument("--meta",  default="data/calibration_metadata.jsonl")
    parser.add_argument("--out",   default="data/final_human_review_data.json")
    args = parser.parse_args()

    root = Path(__file__).parent
    rows = load_rows(root / args.sheet, root / args.meta)
    print(f"Loaded {len(rows)} rows.")

    selected = select_items(rows)
    print(f"Selected {len(selected)} items:")
    state_cnt = Counter(it["primary_stratum"]["state"] for it in selected)
    for s, n in sorted(state_cnt.items()):
        print(f"  {s:<15} {n}")

    core_assignments = assign_core(selected)
    bonus_assignments = assign_bonus(selected)

    by_rid = {it["row_id"]: it for it in selected}
    ordered_assignments = {}
    for name, rids in {**core_assignments, **bonus_assignments}.items():
        items = [by_rid[r] for r in rids]
        ordered = order_items(items, SEED + zlib.crc32(name.encode('utf-8')))
        ordered_assignments[name] = [it["row_id"] for it in ordered]

    print("\nPer-annotator load:")
    for name in CORE + BONUS:
        rids = ordered_assignments[name]
        axis_counts = Counter(by_rid[r]["axis_to_label"] for r in rids)
        state_counts = Counter(by_rid[r]["primary_stratum"]["state"] for r in rids)
        pool = "core" if name in CORE else "bonus"
        print(f"  [{pool}] {name:<12} {len(rids):>3} items  "
              f"axes={dict(axis_counts)}  states={dict(state_counts)}")

    print("\nPer-item coverage (should all be exactly 3 for core):")
    cov = Counter()
    for name in CORE:
        for r in ordered_assignments[name]:
            cov[r] += 1
    cov_dist = Counter(cov.values())
    print(f"  core coverage histogram: {dict(cov_dist)}")

    bundle = {
        "meta": {
            "total_items": len(selected),
            "core_annotators": CORE,
            "bonus_annotators": BONUS,
            "bonus_size": BONUS_SIZE,
            "seed": SEED,
            "selection_schema": {
                "tie22":       "all",
                "two_one_one": "all",
                "unanimous":   "1 per cell (12 cells)",
                "majority":    "1 per cell (15 cells)",
            },
        },
        "items": {str(it["row_id"]): {
            k: v for k, v in it.items() if not k.startswith("_")
        } for it in selected},
        "assignments": ordered_assignments,
    }

    out_path = root / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2))
    print(f"\nWrote {out_path} ({out_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
