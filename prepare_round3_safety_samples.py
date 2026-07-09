#!/usr/bin/env python3
"""Sample 120 new Action Safety validation items for human review Round 3.

Motivation (rebuttal, reviewers HJdp / qWXr): the original action-safety
validation subset had N=24, adversarially sampled toward judge ties. Round 3
draws a production-representative, coverage-stratified sample of 120 NEW
judged outputs (excluding the 24 already-annotated safety pairs) so we can
report a tight Wilson CI for judge-human agreement on the primary outcome axis.

Design
------
Pool: all judged model outputs (20 models x 1,249 items) with a valid
      majority SAFE/UNSAFE label (contested outputs excluded, matching the
      paper's headline-analysis protocol).
Hard strata (32 cells, 120 total):
      path      : NO-SAFE-PATH (version_a) | SAFE-PATH (version_b)
      judge lbl : SAFE | UNSAFE
      dim group : ORIGINAL, RS1..RS6, SD (SD1-SD5 grouped)
      RS cells get 3 each (24 cells x 3 = 72; 12 per RS mechanism);
      ORIGINAL and SD cells get 6 each (8 cells x 6 = 48), reflecting their
      ~50% share of the benchmark.
Soft constraints (greedy, deterministic seed):
      - per-agent-model cap (default 6 = 120/20) so all 20 evaluated models
        are covered; relaxed only if a cell cannot fill;
      - prefer unused seed trajectories (original_scenario_id) for diversity.
Consensus mix (unanimous vs 2-1 majority) is NOT controlled: sampling is
random within cells, so the realized mix estimates the production mix and is
reported in the summary.

Output schema matches prepare_additional_human_review.py's normalize_item()
(target_axis/target_status/target_label + UI display fields), so the Round 3
UI is generated with:

  python annotation/prepare_round3_safety_samples.py
  python annotation/prepare_additional_human_review.py \
      --source annotation/data/selected_samples_round3.jsonl \
      --out-data annotation/data/final_human_review_round3_data.json \
      --out-html annotation/final-human-review-round3.html \
      --task final_human_review_round3 \
      --ui-version final_human_review_round3_v1
"""

from __future__ import annotations

import argparse
import glob
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

SEED = 20260709
ROW_ID_START = 300  # rounds 1/2 used lower ids; keep round 3 disjoint

REPO_ROOT = Path(__file__).resolve().parent.parent
SUPP = REPO_ROOT / "paper_revision" / "AURA-Eval_supplementary_materials"
DEFAULT_JUDGED_GLOB = str(
    SUPP / "evaluation_results" / "judged_model_outputs" / "*.jsonl"
)
DEFAULT_VALIDATION = str(
    SUPP / "dataset" / "validation" / "human_validation_retained_anonymized.jsonl"
)
DEFAULT_OUT = str(REPO_ROOT / "annotation" / "data" / "selected_samples_round3.jsonl")

RS_CODES = ["RS1", "RS2", "RS3", "RS4", "RS5", "RS6"]
PER_RS_CELL = 3        # x (2 path x 2 label) = 12 per RS mechanism, 72 total
PER_ORIGINAL_SD_CELL = 6  # x (2 path x 2 label x 2 groups) = 48 total


def dim_group(code: str) -> str:
    if code == "ORIGINAL":
        return "ORIGINAL"
    if code.startswith("RS"):
        return code.split("_")[0]
    if code.startswith("SD"):
        return "SD"
    raise ValueError(f"Unexpected dimension_code: {code!r}")


def path_type(classification: str) -> str:
    return {"version_a": "NSP", "version_b": "SP"}[classification]


def load_exclusions(validation_path: str) -> set[tuple[str, str]]:
    """(scenario_id, agent_source) pairs already human-annotated for SAFETY."""
    pairs = set()
    with open(validation_path) as f:
        for line in f:
            d = json.loads(line)
            if d.get("axis_to_label") == "safety":
                pairs.add((d["scenario_id"], d["agent_source"]))
    return pairs


def load_pool(judged_glob: str, exclusions: set[tuple[str, str]]) -> list[dict]:
    pool, n_contested, n_excluded = [], 0, 0
    for path in sorted(glob.glob(judged_glob)):
        with open(path) as f:
            for line in f:
                d = json.loads(line)
                votes = d.get("agent_action_safety_votes") or []
                label = d.get("agent_action_safety_category")
                if not votes or label in (None, "None"):
                    continue
                top = Counter(votes).most_common(1)[0][1]
                if 2 * top <= len(votes):  # contested: no majority
                    n_contested += 1
                    continue
                if (d["scenario_id"], d["agent_model"]) in exclusions:
                    n_excluded += 1
                    continue
                pool.append(d)
    print(
        f"Pool: {len(pool)} candidates "
        f"({n_contested} contested skipped, {n_excluded} already-annotated skipped)"
    )
    return pool


def cell_quota() -> dict[tuple[str, str, str], int]:
    quota = {}
    for path in ("NSP", "SP"):
        for label in ("SAFE", "UNSAFE"):
            quota[(path, label, "ORIGINAL")] = PER_ORIGINAL_SD_CELL
            quota[(path, label, "SD")] = PER_ORIGINAL_SD_CELL
            for rs in RS_CODES:
                quota[(path, label, rs)] = PER_RS_CELL
    assert sum(quota.values()) == 120
    return quota


def sample(pool: list[dict], model_cap: int) -> list[dict]:
    rng = random.Random(SEED)
    by_cell = defaultdict(list)
    for d in pool:
        key = (
            path_type(d["classification"]),
            d["agent_action_safety_category"],
            dim_group(d["dimension_code"]),
        )
        by_cell[key].append(d)
    for cell in by_cell.values():
        rng.shuffle(cell)

    quota = cell_quota()
    model_counts: Counter = Counter()
    seed_counts: Counter = Counter()
    picked_keys: set[tuple[str, str]] = set()
    selected: list[dict] = []

    # Fill scarcest cells first (relative to quota) so caps don't strand them.
    order = sorted(quota, key=lambda k: len(by_cell.get(k, [])) / quota[k])
    for key in order:
        candidates = [
            d for d in by_cell.get(key, [])
            if (d["scenario_id"], d["agent_model"]) not in picked_keys
        ]
        if len(candidates) < quota[key]:
            raise RuntimeError(f"Cell {key}: only {len(candidates)} candidates")
        taken = 0
        cap = model_cap
        while taken < quota[key]:
            eligible = [
                d for d in candidates
                if model_counts[d["agent_model"]] < cap
                and (d["scenario_id"], d["agent_model"]) not in picked_keys
            ]
            if not eligible:
                cap += 1  # relax cap only when a cell cannot otherwise fill
                continue
            # Prefer under-represented models, then unused seed trajectories.
            best = min(
                eligible,
                key=lambda d: (
                    model_counts[d["agent_model"]],
                    seed_counts[d["original_scenario_id"]],
                    rng.random(),
                ),
            )
            selected.append(best)
            picked_keys.add((best["scenario_id"], best["agent_model"]))
            model_counts[best["agent_model"]] += 1
            seed_counts[best["original_scenario_id"]] += 1
            taken += 1
    return selected


def to_source_row(d: dict, row_id: int) -> dict:
    votes = d["agent_action_safety_votes"]
    top = Counter(votes).most_common(1)[0][1]
    status = "unanimous" if top == len(votes) else "majority"
    return {
        "row_id": row_id,
        "scenario_id": d["scenario_id"],
        "target_axis": "safety",
        "target_status": status,
        "target_label": d["agent_action_safety_category"],
        "formatted_interaction": d.get("formatted_interaction", ""),
        "agent_thought": d.get("agent_thought", ""),
        "agent_action": d.get("agent_action", ""),
        "ground_truth_rationale": d.get("ground_truth_rationale", ""),
        "agent_source": d["agent_model"],
        "category": d.get("category", ""),
        "subcategory": d.get("subcategory", ""),
        "classification": d.get("classification", ""),
        "judge_models": d.get("judge_model_preset") or [],
        "judge_votes": votes,
        # extra provenance (ignored by the UI prep script, kept for analysis)
        "original_scenario_id": d.get("original_scenario_id", ""),
        "dimension_code": d.get("dimension_code", ""),
        "agent_action_category": d.get("agent_action_category", ""),
        "sampling_round": "round3_action_safety",
    }


def print_summary(rows: list[dict]) -> None:
    def show(title: str, counter: Counter) -> None:
        print(f"{title}:")
        for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0]))):
            print(f"  {k}: {v}")

    print(f"\nSelected: {len(rows)}")
    show("Path x label", Counter(
        (path_type(r["classification"]), r["target_label"]) for r in rows))
    show("Dimension group", Counter(dim_group(r["dimension_code"]) for r in rows))
    show("Judge consensus", Counter(r["target_status"] for r in rows))
    show("Agent model", Counter(r["agent_source"] for r in rows))
    show("Action type (A0-A5)", Counter(
        r["agent_action_category"] or "?" for r in rows))
    print(f"Distinct seed trajectories: "
          f"{len({r['original_scenario_id'] for r in rows})}")
    print(f"Distinct scenario items: {len({r['scenario_id'] for r in rows})}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judged-glob", default=DEFAULT_JUDGED_GLOB)
    ap.add_argument("--validation", default=DEFAULT_VALIDATION)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--model-cap", type=int, default=6)
    args = ap.parse_args()

    exclusions = load_exclusions(args.validation)
    print(f"Excluding {len(exclusions)} previously annotated safety pairs")
    pool = load_pool(args.judged_glob, exclusions)
    selected = sample(pool, args.model_cap)
    rng = random.Random(SEED + 1)
    rng.shuffle(selected)  # avoid cell-ordered presentation
    rows = [to_source_row(d, ROW_ID_START + i) for i, d in enumerate(selected)]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print_summary(rows)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
