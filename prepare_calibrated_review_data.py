#!/usr/bin/env python3
"""Prepare completed human annotations + judge assessments for calibration UI."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
WIDE_CSV = ROOT / "annotated_samples" / "cleaned" / "annotations_wide_synthesis.csv"
METADATA = ROOT / "data" / "calibration_metadata.jsonl"
NO_CONSENSUS = ROOT / "data" / "no_consensus_review.json"
OUT = ROOT / "data" / "calibrated_review_data.js"

CORE_ANNOTATORS = ["Anna", "Orfeas", "Yu", "Christina", "Ani", "Rico"]
AXIS_FIELDS = {
    "detection": {
        "label": "detection_level",
        "explanation": "detection_explanation",
        "votes": "agent_thought_detection_votes",
        "explanations": "agent_thought_detection_explanations",
        "judge_consensus": "agent_thought_detection_level",
        "unanimous": "agent_thought_detection_unanimous",
    },
    "action": {
        "label": "action_category",
        "explanation": "action_explanation",
        "votes": "agent_action_votes",
        "explanations": "agent_action_explanations",
        "judge_consensus": "agent_action_category",
        "unanimous": "agent_action_unanimous",
    },
    "safety": {
        "label": "safety_category",
        "explanation": "safety_explanation",
        "votes": "agent_action_safety_votes",
        "explanations": "agent_action_safety_explanations",
        "judge_consensus": "agent_action_safety_category",
        "unanimous": "agent_action_safety_unanimous",
    },
}


def read_jsonl(path: Path) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            out[int(row["row_id"])] = row
    return out


def parse_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for part in (text or "").split(";"):
        if not part or ":" not in part:
            continue
        label, count = part.rsplit(":", 1)
        counts[label] = int(count)
    return counts


def parse_float(value: Any) -> float | str:
    if value in ("", None):
        return ""
    return float(value)


def parse_int(value: Any) -> int | str:
    if value in ("", None):
        return ""
    return int(value)


def judge_vote_summary(labels: list[str]) -> dict[str, Any]:
    counts = Counter(labels)
    if not counts:
        return {
            "counts": {},
            "status": "no_votes",
            "label": "",
            "count": 0,
            "share": "",
        }
    top_count = max(counts.values())
    top = sorted(label for label, count in counts.items() if count == top_count)
    if len(top) > 1:
        status = "tie"
        label = "/".join(top)
    elif top_count == len(labels):
        status = "unanimous"
        label = top[0]
    else:
        status = "majority"
        label = top[0]
    return {
        "counts": dict(sorted(counts.items())),
        "status": status,
        "label": label,
        "count": top_count,
        "share": round(top_count / len(labels), 4),
    }


def axis_summary(meta: dict[str, Any], axis: str) -> dict[str, Any]:
    fields = AXIS_FIELDS[axis]
    votes = [
        str(v) for v in (meta.get(fields["votes"], []) or [])
        if v not in (None, "")
    ]
    return {
        "votes": votes,
        "explanations": list(meta.get(fields["explanations"], []) or []),
        "label": meta.get(fields["judge_consensus"], ""),
        "unanimous": bool(meta.get(fields["unanimous"], False)),
        "vote_summary": judge_vote_summary(votes),
    }


def no_consensus_by_scenario() -> dict[str, list[dict[str, Any]]]:
    if not NO_CONSENSUS.exists():
        return {}
    data = json.load(NO_CONSENSUS.open(encoding="utf-8"))
    by_sid: dict[str, list[dict[str, Any]]] = {}
    for row in data:
        by_sid.setdefault(row.get("scenario_id", ""), []).append(
            {
                "classification": row.get("classification", ""),
                "category": row.get("category", ""),
                "subcategory": row.get("subcategory", ""),
                "dimension_code": row.get("dimension_code", ""),
                "issues": row.get("issues", []),
                "action_votes": row.get("action_votes", []),
                "safety_votes": row.get("safety_votes", []),
                "detection_votes": row.get("detection_votes", []),
            }
        )
    return by_sid


def main() -> None:
    metadata = read_jsonl(METADATA)
    no_consensus = no_consensus_by_scenario()

    items: list[dict[str, Any]] = []
    with WIDE_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rid = int(row["row_id"])
            meta = metadata[rid]
            axis = row["axis_to_label"]
            human = []
            for name in CORE_ANNOTATORS:
                label = row.get(f"{name}_label", "")
                if not label:
                    continue
                human.append(
                    {
                        "annotator": name,
                        "label": label,
                        "confidence": parse_int(row.get(f"{name}_confidence")),
                        "confidence_label": row.get(f"{name}_confidence_label", ""),
                        "notes": row.get(f"{name}_notes", ""),
                    }
                )

            per_judge = []
            for judge in meta.get("per_judge_breakdown", []):
                per_judge.append(
                    {
                        "model": judge.get("model", ""),
                        "detection": {
                            "label": judge.get("detection_level", ""),
                            "explanation": judge.get("detection_explanation", ""),
                        },
                        "action": {
                            "label": judge.get("action_category", ""),
                            "explanation": judge.get("action_explanation", ""),
                        },
                        "safety": {
                            "label": judge.get("safety_category", ""),
                            "explanation": judge.get("safety_explanation", ""),
                        },
                    }
                )

            judge = {
                "models": meta.get("judge_model_preset", []),
                "target_axis": axis,
                "target": axis_summary(meta, axis),
                "axes": {
                    "detection": axis_summary(meta, "detection"),
                    "action": axis_summary(meta, "action"),
                    "safety": axis_summary(meta, "safety"),
                },
                "per_judge": per_judge,
            }

            target_vote_summary = judge["target"]["vote_summary"]
            human_label = row.get("human_consensus_label", "")
            items.append(
                {
                    "row_id": rid,
                    "scenario_id": row["scenario_id"],
                    "axis_to_label": axis,
                    "allowed_values": [x.strip() for x in row["allowed_values"].split("|")],
                    "agent_source": row["agent_source"],
                    "stratum_state": row["stratum_state"],
                    "stratum_key": row["stratum_key"],
                    "category": meta.get("category", ""),
                    "subcategory": meta.get("subcategory", ""),
                    "classification": meta.get("classification", ""),
                    "scenario_type": meta.get("scenario_type", ""),
                    "dimension_code": meta.get("dimension_code", ""),
                    "dimension_name": meta.get("dimension_name", ""),
                    "pairing_difficulty": meta.get("pairing_difficulty", ""),
                    "human": {
                        "annotations": human,
                        "label_counts": parse_counts(row["label_counts"]),
                        "consensus_status": row["human_consensus_status"],
                        "consensus_label": human_label,
                        "consensus_count": parse_int(row["human_consensus_count"]),
                        "consensus_share": parse_float(row["human_consensus_share"]),
                        "avg_confidence": parse_float(row["avg_confidence"]),
                    },
                    "judge": judge,
                    "comparison": {
                        "human_consensus_in_judge_votes": human_label in target_vote_summary["counts"],
                        "human_consensus_matches_judge_plurality": bool(human_label) and human_label == target_vote_summary["label"],
                        "judge_vote_status": target_vote_summary["status"],
                        "judge_plurality_label": target_vote_summary["label"],
                    },
                    "no_consensus_review": no_consensus.get(row["scenario_id"], []),
                    "scenario_context": row["scenario_context"],
                    "agent_thought": row["agent_thought"],
                    "agent_action": row["agent_action"],
                    "ground_truth_rationale": row["ground_truth_rationale"],
                    "safe_actions": meta.get("safe_actions", []),
                    "unsafe_action": meta.get("unsafe_action", ""),
                }
            )

    meta_out = {
        "source": str(WIDE_CSV.relative_to(ROOT)),
        "metadata_source": str(METADATA.relative_to(ROOT)),
        "total_items": len(items),
        "axis_counts": dict(sorted(Counter(item["axis_to_label"] for item in items).items())),
        "human_consensus_counts": dict(sorted(Counter(item["human"]["consensus_status"] for item in items).items())),
        "judge_target_vote_counts": dict(sorted(Counter(item["comparison"]["judge_vote_status"] for item in items).items())),
    }
    payload = {"meta": meta_out, "items": items}
    OUT.write_text(
        "window.CALIBRATED_REVIEW_DATA = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    print(json.dumps(meta_out, indent=2))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
