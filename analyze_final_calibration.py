#!/usr/bin/env python3
"""Analyze final human calibration for paper/reporting numbers.

Inputs:
  - annotated_samples/cleaned/annotations_wide_synthesis.csv
  - annotated_samples/calibrated/final_calibrated_review_2026-05-03.json

Outputs under annotated_samples/calibrated/analysis/:
  - final_calibration_summary.json
  - agreement_before_after_overall.csv
  - agreement_before_after_by_axis.csv
  - final_label_distribution.csv
  - dropped_rows.csv
  - final_scenario_labels_all.csv
  - final_scenario_labels_retained.csv
  - final_calibration_anomalies.csv
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
WIDE_PATH = ROOT / "annotated_samples" / "cleaned" / "annotations_wide_synthesis.csv"
FINAL_PATH = ROOT / "annotated_samples" / "calibrated" / "final_calibrated_review_2026-05-03.json"
OUT_DIR = ROOT / "annotated_samples" / "calibrated" / "analysis"


COUNT_SEP_RE = re.compile(r"\s*(?:;|·)\s*")


def parse_counts(text: Any) -> Counter[str]:
    counts: Counter[str] = Counter()
    for part in COUNT_SEP_RE.split(str(text or "").strip()):
        if not part or ":" not in part:
            continue
        label, count = part.split(":", 1)
        label = label.strip()
        try:
            counts[label] += int(float(count.strip()))
        except ValueError:
            continue
    return counts


def consensus_from_counts(counts: Counter[str]) -> tuple[str, str, int, float | str]:
    total = sum(counts.values())
    if total == 0:
        return "no_labels", "", 0, ""
    top_count = max(counts.values())
    top_labels = sorted(label for label, count in counts.items() if count == top_count)
    if len(top_labels) > 1:
        return "tie", "/".join(top_labels), top_count, round(top_count / total, 4)
    if top_count == total:
        return "unanimous", top_labels[0], top_count, 1.0
    return "majority", top_labels[0], top_count, round(top_count / total, 4)


def fleiss_kappa_from_counts(rows: list[Counter[str]]) -> float | None:
    rows = [row for row in rows if sum(row.values()) >= 2]
    if not rows:
        return None
    n = sum(rows[0].values())
    if n < 2 or any(sum(row.values()) != n for row in rows):
        return None
    categories = sorted({label for row in rows for label in row})
    n_items = len(rows)
    p_j = {
        label: sum(row.get(label, 0) for row in rows) / (n_items * n)
        for label in categories
    }
    p_bar_e = sum(p * p for p in p_j.values())
    p_i = [
        (sum(count * count for count in row.values()) - n) / (n * (n - 1))
        for row in rows
    ]
    p_bar = sum(p_i) / n_items
    denom = 1 - p_bar_e
    if abs(denom) < 1e-12:
        return None
    return round((p_bar - p_bar_e) / denom, 4)


def krippendorff_alpha_nominal_from_counts(rows: list[Counter[str]]) -> float | None:
    observed_num = 0
    observed_den = 0
    total_labels = 0
    totals: Counter[str] = Counter()
    for row in rows:
        m = sum(row.values())
        if m < 2:
            continue
        observed_num += sum(count * (m - count) for count in row.values())
        observed_den += m * (m - 1)
        totals.update(row)
        total_labels += m
    if not observed_den or total_labels < 2:
        return None
    observed = observed_num / observed_den
    expected_num = sum(count * (total_labels - count) for count in totals.values())
    expected = expected_num / (total_labels * (total_labels - 1))
    if abs(expected) < 1e-12:
        return 1.0 if abs(observed) < 1e-12 else None
    return round(1 - (observed / expected), 4)


def prefix_counts(axis: str, counts: Counter[str]) -> Counter[str]:
    return Counter({f"{axis}:{label}": count for label, count in counts.items()})


def summarize_agreement(rows: list[dict[str, Any]], count_key: str, axis: str | None = None) -> dict[str, Any]:
    selected = [row for row in rows if axis is None or row["axis_to_label"] == axis]
    count_rows = [parse_counts(row[count_key]) for row in selected]
    statuses = [consensus_from_counts(counts)[0] for counts in count_rows]
    n = len(selected)
    unanimous = statuses.count("unanimous")
    majority = statuses.count("majority")
    tie = statuses.count("tie")
    metric_rows = count_rows if axis else [
        prefix_counts(row["axis_to_label"], counts)
        for row, counts in zip(selected, count_rows)
    ]
    total_label_counts: Counter[str] = Counter()
    for row, counts in zip(selected, count_rows):
        for label, count in counts.items():
            total_label_counts[f"{row['axis_to_label']}:{label}"] += count
    return {
        "items": n,
        "unanimous": unanimous,
        "majority": majority,
        "tie": tie,
        "disagreement_items": n - unanimous,
        "disagreement_rate": round((n - unanimous) / n, 4) if n else "",
        "krippendorff_alpha_nominal": krippendorff_alpha_nominal_from_counts(metric_rows),
        "fleiss_kappa": fleiss_kappa_from_counts(metric_rows),
        "label_counts": ";".join(f"{label}:{total_label_counts[label]}" for label in sorted(total_label_counts)),
    }


def is_drop(row: dict[str, Any]) -> bool:
    return str(row.get("dropped", "")).lower() in {"yes", "true", "1"}


def final_decision(row: dict[str, Any]) -> str:
    return "DROP" if is_drop(row) else str(row.get("calibrated_label") or "")


def label_in_set(label: str, label_set_text: Any) -> bool:
    return label in str(label_set_text or "").split("/")


def assigned_annotations(wide_row: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for annotator in ["Anna", "Orfeas", "Yu", "Christina", "Ani", "Rico"]:
        label = wide_row.get(f"{annotator}_label", "")
        if not label:
            continue
        out.append(
            {
                "annotator": annotator,
                "label": label,
                "confidence": wide_row.get(f"{annotator}_confidence", ""),
                "confidence_label": wide_row.get(f"{annotator}_confidence_label", ""),
                "notes": wide_row.get(f"{annotator}_notes", ""),
            }
        )
    return out


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    with WIDE_PATH.open(newline="", encoding="utf-8") as f:
        wide_rows = list(csv.DictReader(f))
    with FINAL_PATH.open(encoding="utf-8") as f:
        final_data = json.load(f)

    final_rows = final_data["rows"]
    final_by_rid = {str(row["row_id"]): row for row in final_rows}
    if len(final_by_rid) != len(final_rows):
        raise SystemExit("Duplicate row_id values in final calibrated rows")
    missing_from_final = sorted(
        set(row["row_id"] for row in wide_rows) - set(final_by_rid),
        key=int,
    )
    if missing_from_final:
        raise SystemExit(f"Rows missing from final calibrated file: {missing_from_final}")
    undecided = [
        row["row_id"] for row in final_rows
        if not row.get("calibrated_label") and not is_drop(row)
    ]
    if undecided:
        raise SystemExit(f"Final calibrated rows without label/drop decision: {undecided}")

    # Use final rows for both original and refined stages because the frozen
    # file captures the exact post-review correction state.
    axes = sorted({row["axis_to_label"] for row in final_rows})
    overall_rows: list[dict[str, Any]] = []
    by_axis_rows: list[dict[str, Any]] = []
    for stage, count_key in [
        ("before_calibration_original_human", "human_label_counts"),
        ("after_annotator_correction_refined_human", "refined_human_label_counts"),
    ]:
        summary = summarize_agreement(final_rows, count_key)
        overall_rows.append({"stage": stage, **summary})
        for axis in axes:
            by_axis_rows.append({"axis_to_label": axis, "stage": stage, **summarize_agreement(final_rows, count_key, axis)})

    retained_rows = [row for row in final_rows if not is_drop(row)]
    retained_overall_rows: list[dict[str, Any]] = []
    for stage, count_key in [
        ("before_calibration_original_human_retained_only", "human_label_counts"),
        ("after_annotator_correction_refined_human_retained_only", "refined_human_label_counts"),
    ]:
        retained_overall_rows.append({"stage": stage, **summarize_agreement(retained_rows, count_key)})

    final_label_counter = Counter(
        (row["axis_to_label"], final_decision(row))
        for row in final_rows
    )
    final_label_rows = [
        {"axis_to_label": axis, "final_label": label, "count": count}
        for (axis, label), count in sorted(final_label_counter.items())
    ]

    wide_by_rid = {row["row_id"]: row for row in wide_rows}
    final_dataset_rows: list[dict[str, Any]] = []
    for row in sorted(final_rows, key=lambda r: int(r["row_id"])):
        wide = wide_by_rid[str(row["row_id"])]
        annotations = assigned_annotations(wide)
        dataset_row: dict[str, Any] = {
            "row_id": row["row_id"],
            "scenario_id": row["scenario_id"],
            "axis_to_label": row["axis_to_label"],
            "final_label": row.get("calibrated_label", ""),
            "dropped": "yes" if is_drop(row) else "no",
            "final_decision": final_decision(row),
            "calibrated_rationale": row.get("calibrated_rationale", ""),
            "issue_tags": row.get("issue_tags", ""),
            "updated_at": row.get("updated_at", ""),
            "agent_source": wide.get("agent_source", ""),
            "stratum_state": wide.get("stratum_state", ""),
            "stratum_key": wide.get("stratum_key", ""),
            "human_consensus_status": row.get("human_consensus_status", ""),
            "human_consensus_label": row.get("human_consensus_label", ""),
            "human_label_counts": row.get("human_label_counts", ""),
            "refined_human_consensus_status": row.get("refined_human_consensus_status", ""),
            "refined_human_consensus_label": row.get("refined_human_consensus_label", ""),
            "refined_human_label_counts": row.get("refined_human_label_counts", ""),
            "corrected_annotation_count": row.get("corrected_annotation_count", ""),
            "judge_vote_status": row.get("judge_vote_status", ""),
            "judge_plurality_label": row.get("judge_plurality_label", ""),
            "judge_label_counts": row.get("judge_label_counts", ""),
            "scenario_context": wide.get("scenario_context", ""),
            "agent_thought": wide.get("agent_thought", ""),
            "agent_action": wide.get("agent_action", ""),
            "ground_truth_rationale": wide.get("ground_truth_rationale", ""),
        }
        for idx in range(3):
            prefix = f"annotator_{idx + 1}"
            ann = annotations[idx] if idx < len(annotations) else {}
            dataset_row[f"{prefix}_name"] = ann.get("annotator", "")
            dataset_row[f"{prefix}_label"] = ann.get("label", "")
            dataset_row[f"{prefix}_confidence"] = ann.get("confidence", "")
            dataset_row[f"{prefix}_confidence_label"] = ann.get("confidence_label", "")
            dataset_row[f"{prefix}_notes"] = ann.get("notes", "")
        final_dataset_rows.append(dataset_row)

    dropped_rows = [
        {
            "row_id": row["row_id"],
            "scenario_id": row["scenario_id"],
            "axis_to_label": row["axis_to_label"],
            "human_consensus_label": row["human_consensus_label"],
            "refined_human_consensus_label": row["refined_human_consensus_label"],
            "judge_plurality_label": row["judge_plurality_label"],
            "calibrated_rationale": row.get("calibrated_rationale", ""),
            "issue_tags": row.get("issue_tags", ""),
        }
        for row in final_rows
        if is_drop(row)
    ]

    anomaly_rows: list[dict[str, Any]] = []
    for row in final_rows:
        decision = final_decision(row)
        rationale = str(row.get("calibrated_rationale", "") or "").strip()
        anomaly_types: list[str] = []
        if is_drop(row):
            anomaly_types.append("dropped")
        else:
            if row.get("calibrated_label") != row.get("refined_human_consensus_label"):
                anomaly_types.append("final_differs_from_refined_human")
            if row.get("calibrated_label") != row.get("judge_plurality_label"):
                anomaly_types.append("final_differs_from_judge_plurality_exact")
            if not label_in_set(str(row.get("calibrated_label", "")), row.get("judge_plurality_label", "")):
                anomaly_types.append("final_outside_judge_plurality_set")
            if str(row.get("refined_human_consensus_status")) == "tie":
                anomaly_types.append("refined_human_tie")
            if str(row.get("judge_vote_status")) == "tie":
                anomaly_types.append("judge_tie")
        if anomaly_types:
            anomaly_rows.append(
                {
                    "row_id": row["row_id"],
                    "scenario_id": row["scenario_id"],
                    "axis_to_label": row["axis_to_label"],
                    "anomaly_types": ";".join(anomaly_types),
                    "final_decision": decision,
                    "human_consensus_status": row.get("human_consensus_status", ""),
                    "human_consensus_label": row.get("human_consensus_label", ""),
                    "refined_human_consensus_status": row.get("refined_human_consensus_status", ""),
                    "refined_human_consensus_label": row.get("refined_human_consensus_label", ""),
                    "judge_vote_status": row.get("judge_vote_status", ""),
                    "judge_plurality_label": row.get("judge_plurality_label", ""),
                    "calibrated_rationale": rationale,
                    "issue_tags": row.get("issue_tags", ""),
                }
            )

    final_vs_sources = {
        "retained_items": len(retained_rows),
        "final_matches_refined_human_consensus": sum(
            row.get("calibrated_label") == row.get("refined_human_consensus_label")
            for row in retained_rows
        ),
        "final_matches_judge_plurality_exact": sum(
            row.get("calibrated_label") == row.get("judge_plurality_label")
            for row in retained_rows
        ),
        "final_label_in_judge_plurality_set": sum(
            row.get("calibrated_label") in str(row.get("judge_plurality_label", "")).split("/")
            for row in retained_rows
        ),
    }
    if retained_rows:
        final_vs_sources["final_matches_refined_human_consensus_rate"] = round(
            final_vs_sources["final_matches_refined_human_consensus"] / len(retained_rows), 4
        )
        final_vs_sources["final_matches_judge_plurality_exact_rate"] = round(
            final_vs_sources["final_matches_judge_plurality_exact"] / len(retained_rows), 4
        )
        final_vs_sources["final_label_in_judge_plurality_set_rate"] = round(
            final_vs_sources["final_label_in_judge_plurality_set"] / len(retained_rows), 4
        )

    corrected_annotation_count = sum(int(row.get("corrected_annotation_count") or 0) for row in final_rows)
    corrected_item_count = sum(int(row.get("corrected_annotation_count") or 0) > 0 for row in final_rows)
    summary = {
        "inputs": {
            "cleaned_human_annotations": str(WIDE_PATH.relative_to(ROOT)),
            "final_calibrated": str(FINAL_PATH.relative_to(ROOT)),
        },
        "total_reviewed_items": len(final_rows),
        "retained_items": len(retained_rows),
        "dropped_items": len(dropped_rows),
        "corrected_annotation_count": corrected_annotation_count,
        "corrected_item_count": corrected_item_count,
        "agreement_overall": overall_rows,
        "agreement_overall_retained_only": retained_overall_rows,
        "agreement_by_axis": by_axis_rows,
        "final_label_distribution": final_label_rows,
        "dropped_rows": dropped_rows,
        "anomaly_counts": dict(Counter(
            anomaly_type
            for row in anomaly_rows
            for anomaly_type in row["anomaly_types"].split(";")
        )),
        "anomalies": anomaly_rows,
        "final_vs_sources": final_vs_sources,
        "frozen_summary": final_data.get("summary", {}),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(
        OUT_DIR / "agreement_before_after_overall.csv",
        overall_rows + retained_overall_rows,
        [
            "stage", "items", "unanimous", "majority", "tie",
            "disagreement_items", "disagreement_rate",
            "krippendorff_alpha_nominal", "fleiss_kappa", "label_counts",
        ],
    )
    write_csv(
        OUT_DIR / "agreement_before_after_by_axis.csv",
        by_axis_rows,
        [
            "axis_to_label", "stage", "items", "unanimous", "majority", "tie",
            "disagreement_items", "disagreement_rate",
            "krippendorff_alpha_nominal", "fleiss_kappa", "label_counts",
        ],
    )
    write_csv(
        OUT_DIR / "final_label_distribution.csv",
        final_label_rows,
        ["axis_to_label", "final_label", "count"],
    )
    write_csv(
        OUT_DIR / "dropped_rows.csv",
        dropped_rows,
        [
            "row_id", "scenario_id", "axis_to_label", "human_consensus_label",
            "refined_human_consensus_label", "judge_plurality_label",
            "calibrated_rationale", "issue_tags",
        ],
    )
    write_csv(
        OUT_DIR / "final_calibration_anomalies.csv",
        anomaly_rows,
        [
            "row_id", "scenario_id", "axis_to_label", "anomaly_types",
            "final_decision", "human_consensus_status", "human_consensus_label",
            "refined_human_consensus_status", "refined_human_consensus_label",
            "judge_vote_status", "judge_plurality_label", "calibrated_rationale",
            "issue_tags",
        ],
    )
    with (OUT_DIR / "final_calibration_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    final_dataset_fields = [
        "row_id", "scenario_id", "axis_to_label", "final_label", "dropped",
        "final_decision", "calibrated_rationale", "issue_tags", "updated_at",
        "agent_source", "stratum_state", "stratum_key",
        "human_consensus_status", "human_consensus_label", "human_label_counts",
        "refined_human_consensus_status", "refined_human_consensus_label",
        "refined_human_label_counts", "corrected_annotation_count",
        "judge_vote_status", "judge_plurality_label", "judge_label_counts",
    ]
    for idx in range(1, 4):
        final_dataset_fields += [
            f"annotator_{idx}_name",
            f"annotator_{idx}_label",
            f"annotator_{idx}_confidence",
            f"annotator_{idx}_confidence_label",
            f"annotator_{idx}_notes",
        ]
    final_dataset_fields += [
        "scenario_context", "agent_thought", "agent_action", "ground_truth_rationale",
    ]
    write_csv(
        OUT_DIR / "final_scenario_labels_all.csv",
        final_dataset_rows,
        final_dataset_fields,
    )
    write_csv(
        OUT_DIR / "final_scenario_labels_retained.csv",
        [row for row in final_dataset_rows if row["dropped"] != "yes"],
        final_dataset_fields,
    )

    print(json.dumps({
        "outputs": {
            "summary": str((OUT_DIR / "final_calibration_summary.json").relative_to(ROOT)),
            "overall": str((OUT_DIR / "agreement_before_after_overall.csv").relative_to(ROOT)),
            "by_axis": str((OUT_DIR / "agreement_before_after_by_axis.csv").relative_to(ROOT)),
            "final_labels": str((OUT_DIR / "final_label_distribution.csv").relative_to(ROOT)),
            "drops": str((OUT_DIR / "dropped_rows.csv").relative_to(ROOT)),
            "anomalies": str((OUT_DIR / "final_calibration_anomalies.csv").relative_to(ROOT)),
            "scenario_labels_all": str((OUT_DIR / "final_scenario_labels_all.csv").relative_to(ROOT)),
            "scenario_labels_retained": str((OUT_DIR / "final_scenario_labels_retained.csv").relative_to(ROOT)),
        },
        "headline": {
            "total_reviewed_items": summary["total_reviewed_items"],
            "retained_items": summary["retained_items"],
            "dropped_items": summary["dropped_items"],
            "corrected_annotation_count": corrected_annotation_count,
            "corrected_item_count": corrected_item_count,
            "anomaly_counts": summary["anomaly_counts"],
            "agreement_overall": overall_rows,
            "final_vs_sources": final_vs_sources,
        },
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
