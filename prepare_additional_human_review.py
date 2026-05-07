#!/usr/bin/env python3
"""Build a standalone HTML bundle for the additional human review round.

The UI is cloned from final-human-review.html. This script only swaps the data
bundle and the persistence/logging identifiers so the new round does not
collide with the previous final human review in localStorage or the Google
Sheet logs.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import zlib
from collections import Counter, defaultdict
from pathlib import Path

ANCHOR_ANNOTATORS = ["Anna", "Christina"]
DEFAULT_ADDITIONAL_REVIEWERS = [
    "Additional Reviewer 1",
    "Additional Reviewer 2",
    "Additional Reviewer 3",
]
SEED = 42

DEFAULT_SOURCE = (
    "git:origin/christina:"
    "pipeline_v2/risk_evaluation/calibration_full/additional_samples/"
    "selected_samples.jsonl"
)

ALLOWED_VALUES = {
    "detection": "D0 | D1 | D2 | D3",
    "action": "A0 | A1 | A2 | A3 | A4 | A5",
    "safety": "SAFE | UNSAFE",
}

AXIS_ORDER = {"safety": 0, "detection": 1, "action": 2}
STATE_RANK = {
    "unanimous": 0,
    "majority": 1,
    "weak_majority": 1,
    "tie22": 2,
    "two_one_one": 3,
    "non_consensus": 3,
}


def read_source(source: str, repo_root: Path) -> list[dict]:
    if source.startswith("git:"):
        spec = source[len("git:") :]
        text = subprocess.check_output(
            ["git", "show", spec],
            cwd=repo_root,
            text=True,
        )
    else:
        text = Path(source).read_text()
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def normalize_item(raw: dict) -> dict:
    axis = raw.get("target_axis") or raw.get("axis")
    status = raw.get("target_status") or raw.get("status")
    label = raw.get("target_label") or raw.get("consensus_label")
    if axis not in ALLOWED_VALUES:
        raise ValueError(f"Unknown axis for row {raw.get('row_id')}: {axis!r}")
    if not status:
        raise ValueError(f"Missing consensus status for row {raw.get('row_id')}")
    if not label:
        raise ValueError(f"Missing consensus label for row {raw.get('row_id')}")

    return {
        "row_id": int(raw["row_id"]),
        "scenario_id": raw.get("scenario_id", ""),
        "axis_to_label": axis,
        "allowed_values": ALLOWED_VALUES[axis],
        "scenario_context": raw.get("formatted_interaction", ""),
        "agent_thought": raw.get("agent_thought", ""),
        "agent_action": raw.get("agent_action", ""),
        "ground_truth_rationale": raw.get("ground_truth_rationale", ""),
        "agent_source": raw.get("agent_source", ""),
        "primary_stratum": {
            "axis": axis,
            "state": status,
            "key": label,
        },
        "category": raw.get("category", ""),
        "subcategory": raw.get("subcategory", ""),
        "classification": raw.get("classification", ""),
        "judge_models": raw.get("judge_models") or [],
        "judge_votes": raw.get("judge_votes") or [],
        "consensus_label": label,
    }


def assign_reviewers(items: list[dict], additional_reviewers: list[str]) -> dict[str, list[int]]:
    """Assign rows for the additional round.

    Anna and Christina are anchor reviewers and receive every row. The remaining
    rows are partitioned across the additional reviewers, with no overlap among
    them, so each item has exactly one non-anchor reviewer.
    """
    if not additional_reviewers:
        raise ValueError("At least one additional reviewer is required.")

    rng = random.Random(SEED)
    by_stratum = defaultdict(list)
    for item in items:
        s = item["primary_stratum"]
        by_stratum[(s["axis"], s["state"], s["key"])].append(item)

    assignments = {name: [item["row_id"] for item in items] for name in ANCHOR_ANNOTATORS}
    for name in additional_reviewers:
        if name in assignments:
            raise ValueError(f"Duplicate reviewer name: {name}")
        assignments[name] = []

    max_load = (len(items) + len(additional_reviewers) - 1) // len(additional_reviewers)
    target_loads = {
        name: len(items) // len(additional_reviewers)
        for name in additional_reviewers
    }
    for name in additional_reviewers[: len(items) % len(additional_reviewers)]:
        target_loads[name] += 1

    total_counts = {name: 0 for name in additional_reviewers}
    axis_counts = {name: Counter() for name in additional_reviewers}
    stratum_counts = {name: Counter() for name in additional_reviewers}

    # Largest strata first makes the greedy balancing less sensitive to a long
    # tail of one-off labels. Within each stratum, shuffle deterministically.
    stratum_keys = sorted(
        by_stratum.keys(),
        key=lambda k: (-len(by_stratum[k]), AXIS_ORDER.get(k[0], 99), STATE_RANK.get(k[1], 99), str(k)),
    )
    for key in stratum_keys:
        group = by_stratum[key][:]
        rng.shuffle(group)
        axis = key[0]
        for item in group:
            eligible = [
                name for name in additional_reviewers
                if total_counts[name] < target_loads[name]
            ]
            if not eligible:
                # Defensive fallback; should not happen when target_loads sum to
                # len(items), but avoids dropping a row if the config changes.
                eligible = [
                    name for name in additional_reviewers
                    if total_counts[name] < max_load
                ]
            picked = min(
                eligible,
                key=lambda name: (
                    axis_counts[name][axis],
                    stratum_counts[name][key],
                    total_counts[name],
                    rng.random(),
                ),
            )
            assignments[picked].append(item["row_id"])
            total_counts[picked] += 1
            axis_counts[picked][axis] += 1
            stratum_counts[picked][key] += 1
    return assignments


def order_items(items: list[dict], seed: int) -> list[dict]:
    rng = random.Random(seed)
    buckets = defaultdict(list)
    for item in items:
        state = item["primary_stratum"]["state"]
        buckets[(item["axis_to_label"], state)].append(item)

    for key in buckets:
        rng.shuffle(buckets[key])

    ordered = []
    axes = sorted({key[0] for key in buckets}, key=AXIS_ORDER.get)
    for axis in axes:
        states = sorted(
            {key[1] for key in buckets if key[0] == axis},
            key=lambda state: STATE_RANK.get(state, 99),
        )
        for state in states:
            ordered.extend(buckets[(axis, state)])
    return ordered


def build_bundle(items: list[dict], additional_reviewers: list[str]) -> dict:
    by_rid = {item["row_id"]: item for item in items}
    assignments = assign_reviewers(items, additional_reviewers)
    ordered_assignments = {}
    for name, row_ids in assignments.items():
        ordered = order_items(
            [by_rid[row_id] for row_id in row_ids],
            SEED + zlib.crc32(name.encode("utf-8")),
        )
        ordered_assignments[name] = [item["row_id"] for item in ordered]

    return {
        "meta": {
            "total_items": len(items),
            "core_annotators": ANCHOR_ANNOTATORS + additional_reviewers,
            "bonus_annotators": [],
            "bonus_size": 0,
            "seed": SEED,
            "selection_schema": {
                "source": "additional 5-judge consensus validation sample",
                "assignment": (
                    "Anna and Christina review every item; one non-overlapping "
                    "additional reviewer is assigned per item"
                ),
                "anchor_annotators": ANCHOR_ANNOTATORS,
                "additional_reviewers": additional_reviewers,
            },
        },
        "items": {str(item["row_id"]): item for item in items},
        "assignments": ordered_assignments,
    }


def replace_once(text: str, pattern: str, replacement: str, label: str) -> str:
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"Expected one replacement for {label}, found {count}")
    return new_text


def storage_prefix(task: str) -> str:
    return "rb_" + re.sub(r"[^A-Za-z0-9_]+", "_", task).strip("_")


def title_from_task(task: str) -> str:
    return task.replace("_", " ").title().replace("Round2", "Round 2")


def build_html(template: str, bundle: dict, task: str, ui_version: str) -> str:
    data_json = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
    title = title_from_task(task)
    prefix = storage_prefix(task)
    html = template
    html = html.replace(
        "<title>RiskBench — Final Human Review</title>",
        f"<title>RiskBench — {title}</title>",
    )
    html = html.replace(
        '<div class="login-title">Final Human Review</div>',
        f'<div class="login-title">{title}</div>',
    )
    html = replace_once(
        html,
        r"const UI_VERSION = '[^']+';",
        f"const UI_VERSION = '{ui_version}';",
        "UI_VERSION",
    )
    html = replace_once(
        html,
        r"const SYNC_SCHEMA_VERSION = '[^']+';",
        "const SYNC_SCHEMA_VERSION = '2026-05-07-final-human-review-round2-v1';",
        "SYNC_SCHEMA_VERSION",
    )
    html, count = re.subn(
        r"const DATA = .*?;\n\n// Rubric definitions",
        lambda _match: f"const DATA = {data_json};\n\n// Rubric definitions",
        html,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise RuntimeError(f"Expected one replacement for DATA, found {count}")
    html = replace_once(
        html,
        r"function storageKey\(\) \{ return `rb_review_\$\{annotator\}`; \}",
        f"function storageKey() {{ return `{prefix}_${{annotator}}`; }}",
        "storageKey",
    )
    html = html.replace(
        "const RUBRIC_HIDDEN_KEY  = 'rb_rubric_hidden';",
        f"const RUBRIC_HIDDEN_KEY  = '{prefix}_rubric_hidden';",
    )
    html = html.replace(
        "const RUBRIC_VERSION_KEY = 'rb_rubric_version';",
        f"const RUBRIC_VERSION_KEY = '{prefix}_rubric_version';",
    )
    html = html.replace("task: 'final_human_review'", f"task: '{task}'")
    html = html.replace(
        "review_${annotator.replace(/\\s+/g,'_')}_${new Date().toISOString().slice(0,10)}.json",
        f"{task}_${{annotator.replace(/\\s+/g,'_')}}_${{new Date().toISOString().slice(0,10)}}.json",
    )
    return html


def print_summary(bundle: dict) -> None:
    items = list(bundle["items"].values())
    print(f"Items: {len(items)}")
    print("By axis/status/label:")
    counts = Counter(
        (
            item["axis_to_label"],
            item["primary_stratum"]["state"],
            item["primary_stratum"]["key"],
        )
        for item in items
    )
    for key, count in sorted(counts.items()):
        print(f"  {key}: {count}")
    print("Per-annotator load:")
    for name, row_ids in bundle["assignments"].items():
        axis_counts = Counter(bundle["items"][str(row_id)]["axis_to_label"] for row_id in row_ids)
        print(f"  {name:<10} {len(row_ids):>2} {dict(axis_counts)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--template", default="annotation/final-human-review.html")
    parser.add_argument("--out-data", default="annotation/data/final_human_review_round2_data.json")
    parser.add_argument("--out-html", default="annotation/final-human-review-round2.html")
    parser.add_argument("--task", default="final_human_review_round2")
    parser.add_argument("--ui-version", default="final_human_review_round2_v1")
    parser.add_argument(
        "--additional-reviewers",
        nargs="+",
        default=DEFAULT_ADDITIONAL_REVIEWERS,
        help=(
            "Names for non-anchor reviewers. Rows are partitioned across these "
            "reviewers with no overlap. Use one name for 57 rows, two names for "
            "rough halves, or three names for thirds."
        ),
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    raw_items = read_source(args.source, repo_root)
    items = [normalize_item(raw) for raw in raw_items]
    bundle = build_bundle(items, args.additional_reviewers)

    out_data = repo_root / args.out_data
    out_data.parent.mkdir(parents=True, exist_ok=True)
    out_data.write_text(json.dumps(bundle, ensure_ascii=False, indent=2))

    template = (repo_root / args.template).read_text()
    html = build_html(template, bundle, args.task, args.ui_version)
    out_html = repo_root / args.out_html
    out_html.write_text(html)

    print_summary(bundle)
    print(f"Wrote {out_data}")
    print(f"Wrote {out_html}")


if __name__ == "__main__":
    main()
