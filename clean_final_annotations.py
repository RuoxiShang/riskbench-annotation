#!/usr/bin/env python3
"""Clean final human-review annotations for synthesis.

Inputs:
  - annotated_samples/*.json exports from final-human-review.html
  - annotated_samples/christina.csv Google Sheets export
  - data/final_human_review_data.json assignment/sample bundle

Outputs under annotated_samples/cleaned/:
  - annotations_long_clean.csv
  - annotations_wide_synthesis.csv
  - disagreement_items.csv
  - pairwise_agreement.csv
  - agreement_by_axis.csv
  - agreement_alpha_by_axis.csv
  - agreement_by_stratum.csv
  - annotation_summary.json
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
ANNOTATION_DIR = ROOT / "annotated_samples"
BUNDLE_PATH = ROOT / "data" / "final_human_review_data.json"
OUT_DIR = ANNOTATION_DIR / "cleaned"


MIN_DT = datetime.min.replace(tzinfo=timezone.utc)


def parse_ts(value: Any) -> datetime:
    text = str(value or "").strip().strip("\ufeff").strip().strip('"')
    if not text:
        return MIN_DT
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return MIN_DT
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(dt: datetime) -> str:
    if dt == MIN_DT:
        return ""
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def stratum_key_text(key: Any) -> str:
    if isinstance(key, list):
        return "/".join(str(x) for x in key)
    return "" if key is None else str(key)


@dataclass(frozen=True)
class Annotation:
    annotator: str
    row_id: str
    label: str
    confidence: int
    confidence_label: str
    notes: str
    completed: bool
    source_file: str
    source_type: str
    source_timestamp: datetime
    source_order: int

    def sort_key(self) -> tuple[datetime, int]:
        return (self.source_timestamp, self.source_order)


def is_complete(label: Any, confidence: Any, completed: Any = True) -> bool:
    completed_ok = completed is True or str(completed).lower() == "true" or str(completed).lower() == "yes"
    return completed_ok and bool(label) and str(confidence or "") != ""


def confidence_label(value: Any, existing: Any = "") -> str:
    if existing:
        return str(existing)
    return {"1": "Unsure", "2": "Leaning", "3": "Confident"}.get(str(value), "")


def read_json_exports() -> tuple[list[Annotation], dict[str, Any]]:
    annotations: list[Annotation] = []
    diagnostics: dict[str, Any] = {"json_files": {}}
    order = 0
    for path in sorted(ANNOTATION_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        annotator = data.get("annotator", "")
        exported_at = parse_ts(data.get("exported_at"))
        items = data.get("items", [])
        complete_count = 0
        placeholder_after_complete = 0
        for item in items:
            order += 1
            rid = str(item.get("row_id", ""))
            complete = is_complete(item.get("label"), item.get("confidence"), item.get("completed"))
            if complete:
                complete_count += 1
                annotations.append(
                    Annotation(
                        annotator=annotator,
                        row_id=rid,
                        label=str(item.get("label")),
                        confidence=int(item.get("confidence")),
                        confidence_label=confidence_label(item.get("confidence"), item.get("confidence_label")),
                        notes=str(item.get("notes") or ""),
                        completed=True,
                        source_file=str(path.relative_to(ROOT)),
                        source_type="json_export",
                        source_timestamp=exported_at,
                        source_order=order,
                    )
                )
            else:
                placeholder_after_complete += 1
        diagnostics["json_files"][str(path.relative_to(ROOT))] = {
            "annotator": annotator,
            "exported_at": iso(exported_at),
            "items": len(items),
            "completed_items": complete_count,
            "incomplete_placeholders": placeholder_after_complete,
        }
    return annotations, diagnostics


def read_csv_exports() -> tuple[list[Annotation], dict[str, Any]]:
    annotations: list[Annotation] = []
    diagnostics: dict[str, Any] = {"csv_files": {}}
    order = 0
    for path in sorted(ANNOTATION_DIR.glob("*.csv")):
        with path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        complete_count = 0
        for row in rows:
            order += 1
            if not is_complete(row.get("label"), row.get("confidence"), row.get("completed")):
                continue
            complete_count += 1
            ts = parse_ts(row.get("server_timestamp")) or parse_ts(row.get("timestamp"))
            if ts == MIN_DT:
                ts = parse_ts(row.get("timestamp"))
            annotations.append(
                Annotation(
                    annotator=str(row.get("annotator") or ""),
                    row_id=str(row.get("row_id") or ""),
                    label=str(row.get("label") or ""),
                    confidence=int(row.get("confidence")),
                    confidence_label=confidence_label(row.get("confidence"), row.get("confidence_label")),
                    notes=str(row.get("notes") or ""),
                    completed=True,
                    source_file=str(path.relative_to(ROOT)),
                    source_type="csv_event_log",
                    source_timestamp=ts,
                    source_order=order,
                )
            )
        diagnostics["csv_files"][str(path.relative_to(ROOT))] = {
            "rows": len(rows),
            "completed_rows": complete_count,
        }
    return annotations, diagnostics


def pick_latest_completed(annotations: list[Annotation]) -> tuple[dict[tuple[str, str], Annotation], dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Annotation]] = defaultdict(list)
    for ann in annotations:
        grouped[(ann.annotator, ann.row_id)].append(ann)

    latest: dict[tuple[str, str], Annotation] = {}
    duplicate_groups: dict[str, int] = {}
    conflicts: list[dict[str, Any]] = []
    for key, values in grouped.items():
        values = sorted(values, key=lambda a: a.sort_key())
        latest[key] = values[-1]
        if len(values) > 1:
            duplicate_groups[f"{key[0]}:{key[1]}"] = len(values)
            observed = {(a.label, a.confidence, a.notes) for a in values}
            if len(observed) > 1:
                conflicts.append(
                    {
                        "annotator": key[0],
                        "row_id": key[1],
                        "versions": [
                            {
                                "source_file": a.source_file,
                                "source_timestamp": iso(a.source_timestamp),
                                "label": a.label,
                                "confidence": a.confidence,
                                "notes": a.notes,
                            }
                            for a in values
                        ],
                    }
                )
    return latest, {
        "duplicate_completed_groups": duplicate_groups,
        "duplicate_completed_group_count": len(duplicate_groups),
        "conflicting_completed_duplicates": conflicts,
        "conflicting_completed_duplicate_count": len(conflicts),
    }


def label_counts_text(counter: Counter[str]) -> str:
    return ";".join(f"{label}:{counter[label]}" for label in sorted(counter))


def consensus(labels: list[str]) -> tuple[str, str, int, float | str]:
    counts = Counter(labels)
    if not counts:
        return "no_labels", "", 0, ""
    top_count = max(counts.values())
    top_labels = sorted(label for label, count in counts.items() if count == top_count)
    if len(labels) == 1:
        return "single_label", top_labels[0], top_count, 1.0
    if len(top_labels) > 1:
        return "tie", "/".join(top_labels), top_count, round(top_count / len(labels), 4)
    if top_count == len(labels):
        return "unanimous", top_labels[0], top_count, 1.0
    return "majority", top_labels[0], top_count, round(top_count / len(labels), 4)


def fleiss_kappa(rows: list[list[str]], categories: list[str]) -> float | None:
    if not rows:
        return None
    n = len(rows[0])
    if n < 2 or any(len(row) != n for row in rows):
        return None
    n_items = len(rows)
    cat_index = {cat: i for i, cat in enumerate(categories)}
    counts = []
    for row in rows:
        row_counts = [0] * len(categories)
        for label in row:
            row_counts[cat_index[label]] += 1
        counts.append(row_counts)
    p_j = [sum(row[j] for row in counts) / (n_items * n) for j in range(len(categories))]
    p_bar_e = sum(p * p for p in p_j)
    p_i = [(sum(c * c for c in row) - n) / (n * (n - 1)) for row in counts]
    p_bar = sum(p_i) / n_items
    denom = 1 - p_bar_e
    if abs(denom) < 1e-12:
        return None
    return round((p_bar - p_bar_e) / denom, 4)


def krippendorff_alpha_nominal(rows: list[list[str]]) -> float | None:
    """Nominal Krippendorff alpha for rows of labels.

    The implementation uses ordered-pair disagreement, so it supports rows with
    different numbers of completed annotations.
    """
    observed_num = 0
    observed_den = 0
    total_labels = 0
    totals: Counter[str] = Counter()
    for labels in rows:
        labels = [label for label in labels if label]
        m = len(labels)
        if m < 2:
            continue
        counts = Counter(labels)
        observed_num += sum(count * (m - count) for count in counts.values())
        observed_den += m * (m - 1)
        totals.update(labels)
        total_labels += m
    if not observed_den or total_labels < 2:
        return None
    observed = observed_num / observed_den
    expected_num = sum(count * (total_labels - count) for count in totals.values())
    expected = expected_num / (total_labels * (total_labels - 1))
    if abs(expected) < 1e-12:
        return 1.0 if abs(observed) < 1e-12 else None
    return round(1 - (observed / expected), 4)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    with BUNDLE_PATH.open(encoding="utf-8") as f:
        bundle = json.load(f)

    core = list(bundle["meta"]["core_annotators"])
    bonus = list(bundle["meta"]["bonus_annotators"])
    expected_by_annotator = {
        annotator: {str(rid) for rid in row_ids}
        for annotator, row_ids in bundle["assignments"].items()
    }
    expected_core = {
        (annotator, rid)
        for annotator in core
        for rid in expected_by_annotator.get(annotator, set())
    }
    item_by_rid = {str(rid): item for rid, item in bundle["items"].items()}

    json_annotations, json_diag = read_json_exports()
    csv_annotations, csv_diag = read_csv_exports()
    all_annotations = json_annotations + csv_annotations
    latest_all, dedupe_diag = pick_latest_completed(all_annotations)

    latest_core = {
        key: ann for key, ann in latest_all.items()
        if key in expected_core
    }
    unexpected = {
        f"{annotator}:{rid}": {
            "source_file": ann.source_file,
            "label": ann.label,
            "source_timestamp": iso(ann.source_timestamp),
        }
        for (annotator, rid), ann in latest_all.items()
        if (annotator, rid) not in expected_core
    }

    missing_by_annotator = {
        annotator: sorted(
            expected_by_annotator[annotator] - {
                rid for (ann, rid) in latest_core if ann == annotator
            },
            key=int,
        )
        for annotator in core
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    long_rows: list[dict[str, Any]] = []
    for annotator in core:
        for rid in sorted(expected_by_annotator[annotator], key=int):
            ann = latest_core.get((annotator, rid))
            item = item_by_rid[rid]
            stratum = item["primary_stratum"]
            if not ann:
                continue
            long_rows.append(
                {
                    "annotator": annotator,
                    "row_id": rid,
                    "scenario_id": item["scenario_id"],
                    "axis_to_label": item["axis_to_label"],
                    "allowed_values": item["allowed_values"],
                    "agent_source": item.get("agent_source", ""),
                    "stratum_state": stratum.get("state", ""),
                    "stratum_key": stratum_key_text(stratum.get("key")),
                    "label": ann.label,
                    "confidence": ann.confidence,
                    "confidence_label": ann.confidence_label,
                    "notes": ann.notes,
                    "source_file": ann.source_file,
                    "source_type": ann.source_type,
                    "source_timestamp": iso(ann.source_timestamp),
                }
            )

    long_fields = [
        "annotator", "row_id", "scenario_id", "axis_to_label", "allowed_values",
        "agent_source", "stratum_state", "stratum_key", "label", "confidence",
        "confidence_label", "notes", "source_file", "source_type", "source_timestamp",
    ]
    write_csv(OUT_DIR / "annotations_long_clean.csv", long_rows, long_fields)

    wide_rows: list[dict[str, Any]] = []
    compact_wide_rows: list[dict[str, Any]] = []
    disagreement_rows: list[dict[str, Any]] = []
    labels_by_row: dict[str, list[str]] = {}

    for rid in sorted(item_by_rid, key=int):
        item = item_by_rid[rid]
        stratum = item["primary_stratum"]
        expected_annotators = [ann for ann in core if rid in expected_by_annotator[ann]]
        anns = [latest_core.get((annotator, rid)) for annotator in expected_annotators]
        labels = [ann.label for ann in anns if ann]
        labels_by_row[rid] = labels
        counts = Counter(labels)
        status, label, count, share = consensus(labels)
        avg_conf = round(sum(ann.confidence for ann in anns if ann) / len(labels), 3) if labels else ""
        row = {
            "row_id": rid,
            "scenario_id": item["scenario_id"],
            "axis_to_label": item["axis_to_label"],
            "allowed_values": item["allowed_values"],
            "agent_source": item.get("agent_source", ""),
            "stratum_state": stratum.get("state", ""),
            "stratum_key": stratum_key_text(stratum.get("key")),
            "expected_core_annotators": ";".join(expected_annotators),
            "submitted_count": len(labels),
            "missing_core_annotators": ";".join(
                annotator for annotator, ann in zip(expected_annotators, anns) if ann is None
            ),
            "label_counts": label_counts_text(counts),
            "human_consensus_status": status,
            "human_consensus_label": label,
            "human_consensus_count": count,
            "human_consensus_share": share,
            "avg_confidence": avg_conf,
            "scenario_context": item.get("scenario_context", ""),
            "agent_thought": item.get("agent_thought", ""),
            "agent_action": item.get("agent_action", ""),
            "ground_truth_rationale": item.get("ground_truth_rationale", ""),
        }
        for annotator in core:
            ann = latest_core.get((annotator, rid))
            row[f"{annotator}_label"] = ann.label if ann else ""
            row[f"{annotator}_confidence"] = ann.confidence if ann else ""
            row[f"{annotator}_confidence_label"] = ann.confidence_label if ann else ""
            row[f"{annotator}_notes"] = ann.notes if ann else ""
        wide_rows.append(row)

        compact_row = {
            k: row[k]
            for k in [
                "row_id", "scenario_id", "axis_to_label", "allowed_values", "agent_source",
                "stratum_state", "stratum_key", "submitted_count", "label_counts",
                "human_consensus_status", "human_consensus_label",
                "human_consensus_count", "human_consensus_share", "avg_confidence",
            ]
        }
        for slot, annotator in enumerate(expected_annotators, start=1):
            ann = latest_core.get((annotator, rid))
            compact_row[f"annotator_{slot}_name"] = annotator
            compact_row[f"annotator_{slot}_label"] = ann.label if ann else ""
            compact_row[f"annotator_{slot}_confidence"] = ann.confidence if ann else ""
            compact_row[f"annotator_{slot}_confidence_label"] = ann.confidence_label if ann else ""
            # The UI field is called notes; expose it as rationale for synthesis.
            compact_row[f"annotator_{slot}_rationale"] = ann.notes if ann else ""
        compact_row["scenario_context"] = item.get("scenario_context", "")
        compact_row["agent_thought"] = item.get("agent_thought", "")
        compact_row["agent_action"] = item.get("agent_action", "")
        compact_row["ground_truth_rationale"] = item.get("ground_truth_rationale", "")
        compact_wide_rows.append(compact_row)

        if status != "unanimous":
            disagreement_rows.append(row)

    wide_fields = [
        "row_id", "scenario_id", "axis_to_label", "allowed_values", "agent_source",
        "stratum_state", "stratum_key", "expected_core_annotators", "submitted_count",
        "missing_core_annotators", "label_counts", "human_consensus_status",
        "human_consensus_label", "human_consensus_count", "human_consensus_share",
        "avg_confidence",
    ]
    for annotator in core:
        wide_fields += [
            f"{annotator}_label", f"{annotator}_confidence",
            f"{annotator}_confidence_label", f"{annotator}_notes",
        ]
    wide_fields += ["scenario_context", "agent_thought", "agent_action", "ground_truth_rationale"]
    write_csv(OUT_DIR / "annotations_wide_synthesis.csv", wide_rows, wide_fields)

    compact_fields = [
        "row_id", "scenario_id", "axis_to_label", "allowed_values", "agent_source",
        "stratum_state", "stratum_key", "submitted_count", "label_counts",
        "human_consensus_status", "human_consensus_label",
        "human_consensus_count", "human_consensus_share", "avg_confidence",
    ]
    for slot in range(1, 4):
        compact_fields += [
            f"annotator_{slot}_name",
            f"annotator_{slot}_label",
            f"annotator_{slot}_confidence",
            f"annotator_{slot}_confidence_label",
            f"annotator_{slot}_rationale",
        ]
    compact_fields += ["scenario_context", "agent_thought", "agent_action", "ground_truth_rationale"]
    write_csv(OUT_DIR / "annotations_wide_compact.csv", compact_wide_rows, compact_fields)
    write_csv(OUT_DIR / "disagreement_items.csv", disagreement_rows, wide_fields)

    def stat_rows(group_key: str) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in wide_rows:
            grouped[str(row[group_key])].append(row)
        rows: list[dict[str, Any]] = []
        for key, group in sorted(grouped.items()):
            n = len(group)
            unanimous = sum(1 for row in group if row["human_consensus_status"] == "unanimous")
            majority = sum(1 for row in group if row["human_consensus_status"] == "majority")
            tie = sum(1 for row in group if row["human_consensus_status"] == "tie")
            rows.append(
                {
                    group_key: key,
                    "items": n,
                    "unanimous": unanimous,
                    "majority": majority,
                    "tie": tie,
                    "disagreement_items": n - unanimous,
                    "disagreement_rate": round((n - unanimous) / n, 4) if n else "",
                    "avg_confidence": round(
                        sum(float(row["avg_confidence"]) for row in group if row["avg_confidence"] != "") /
                        sum(1 for row in group if row["avg_confidence"] != ""),
                        3,
                    ),
                }
            )
        return rows

    def stat_rows_multi(group_keys: list[str]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
        for row in wide_rows:
            grouped[tuple(str(row[k]) for k in group_keys)].append(row)
        rows: list[dict[str, Any]] = []
        for key, group in sorted(grouped.items()):
            n = len(group)
            unanimous = sum(1 for row in group if row["human_consensus_status"] == "unanimous")
            majority = sum(1 for row in group if row["human_consensus_status"] == "majority")
            tie = sum(1 for row in group if row["human_consensus_status"] == "tie")
            out = {k: v for k, v in zip(group_keys, key)}
            out.update(
                {
                    "items": n,
                    "unanimous": unanimous,
                    "majority": majority,
                    "tie": tie,
                    "disagreement_items": n - unanimous,
                    "disagreement_rate": round((n - unanimous) / n, 4) if n else "",
                    "avg_confidence": round(
                        sum(float(row["avg_confidence"]) for row in group if row["avg_confidence"] != "") /
                        sum(1 for row in group if row["avg_confidence"] != ""),
                        3,
                    ),
                }
            )
            rows.append(out)
        rows.sort(key=lambda r: (-float(r["disagreement_rate"]), -int(r["items"]), tuple(str(r[k]) for k in group_keys)))
        return rows

    axis_rows = stat_rows("axis_to_label")
    stratum_rows = stat_rows("stratum_state")
    stratum_cell_rows = stat_rows_multi(["axis_to_label", "stratum_state", "stratum_key"])
    agent_source_rows = stat_rows("agent_source")
    write_csv(
        OUT_DIR / "agreement_by_axis.csv",
        axis_rows,
        ["axis_to_label", "items", "unanimous", "majority", "tie", "disagreement_items", "disagreement_rate", "avg_confidence"],
    )
    write_csv(
        OUT_DIR / "agreement_by_stratum.csv",
        stratum_rows,
        ["stratum_state", "items", "unanimous", "majority", "tie", "disagreement_items", "disagreement_rate", "avg_confidence"],
    )
    write_csv(
        OUT_DIR / "agreement_by_stratum_cell.csv",
        stratum_cell_rows,
        ["axis_to_label", "stratum_state", "stratum_key", "items", "unanimous", "majority", "tie", "disagreement_items", "disagreement_rate", "avg_confidence"],
    )
    write_csv(
        OUT_DIR / "agreement_by_agent_source.csv",
        agent_source_rows,
        ["agent_source", "items", "unanimous", "majority", "tie", "disagreement_items", "disagreement_rate", "avg_confidence"],
    )

    pair_rows: list[dict[str, Any]] = []
    for i, a in enumerate(core):
        for b in core[i + 1:]:
            shared = sorted(expected_by_annotator[a] & expected_by_annotator[b], key=int)
            available = [
                rid for rid in shared
                if (a, rid) in latest_core and (b, rid) in latest_core
            ]
            same = sum(1 for rid in available if latest_core[(a, rid)].label == latest_core[(b, rid)].label)
            pair_rows.append(
                {
                    "annotator_a": a,
                    "annotator_b": b,
                    "overlap_items": len(shared),
                    "completed_overlap": len(available),
                    "same_label": same,
                    "different_label": len(available) - same,
                    "agreement_rate": round(same / len(available), 4) if available else "",
                }
            )
    write_csv(
        OUT_DIR / "pairwise_agreement.csv",
        pair_rows,
        ["annotator_a", "annotator_b", "overlap_items", "completed_overlap", "same_label", "different_label", "agreement_rate"],
    )

    kappa_by_axis: dict[str, float | None] = {}
    alpha_by_axis: dict[str, float | None] = {}
    for axis in sorted({item["axis_to_label"] for item in item_by_rid.values()}):
        axis_label_rows = [
            labels_by_row[rid]
            for rid, item in item_by_rid.items()
            if item["axis_to_label"] == axis and len(labels_by_row[rid]) == 3
        ]
        categories = sorted({label for labels in axis_label_rows for label in labels})
        kappa_by_axis[axis] = fleiss_kappa(axis_label_rows, categories)
        alpha_by_axis[axis] = krippendorff_alpha_nominal(axis_label_rows)

    alpha_overall_rows = [
        [f"{item_by_rid[rid]['axis_to_label']}:{label}" for label in labels]
        for rid, labels in labels_by_row.items()
    ]
    alpha_overall = krippendorff_alpha_nominal(alpha_overall_rows)
    alpha_rows = [
        {
            "axis_to_label": axis,
            "items": sum(1 for rid, item in item_by_rid.items() if item["axis_to_label"] == axis and len(labels_by_row[rid]) == 3),
            "krippendorff_alpha_nominal": alpha_by_axis[axis],
            "fleiss_kappa": kappa_by_axis[axis],
        }
        for axis in sorted(alpha_by_axis)
    ]
    write_csv(
        OUT_DIR / "agreement_alpha_by_axis.csv",
        alpha_rows,
        ["axis_to_label", "items", "krippendorff_alpha_nominal", "fleiss_kappa"],
    )

    completion_by_annotator = {
        annotator: {
            "expected": len(expected_by_annotator[annotator]),
            "completed": len(expected_by_annotator[annotator]) - len(missing_by_annotator[annotator]),
            "missing": len(missing_by_annotator[annotator]),
            "missing_row_ids": missing_by_annotator[annotator],
        }
        for annotator in core
    }

    summary = {
        "input_files": {
            **json_diag,
            **csv_diag,
        },
        "expected_core_annotations": len(expected_core),
        "clean_core_annotations": len(latest_core),
        "completion_by_annotator": completion_by_annotator,
        "optional_bonus_annotators_not_in_clean_core": bonus,
        "dedupe": dedupe_diag,
        "unexpected_completed_annotations_excluded": unexpected,
        "consensus_status_counts": dict(Counter(row["human_consensus_status"] for row in wide_rows)),
        "agreement_by_axis": axis_rows,
        "agreement_by_stratum": stratum_rows,
        "agreement_by_stratum_cell": stratum_cell_rows,
        "agreement_by_agent_source": agent_source_rows,
        "pairwise_agreement": pair_rows,
        "fleiss_kappa_by_axis": kappa_by_axis,
        "krippendorff_alpha_nominal_by_axis": alpha_by_axis,
        "krippendorff_alpha_nominal_overall_axis_prefixed": alpha_overall,
        "outputs": {
            "long": str((OUT_DIR / "annotations_long_clean.csv").relative_to(ROOT)),
            "wide": str((OUT_DIR / "annotations_wide_synthesis.csv").relative_to(ROOT)),
            "wide_compact": str((OUT_DIR / "annotations_wide_compact.csv").relative_to(ROOT)),
            "disagreements": str((OUT_DIR / "disagreement_items.csv").relative_to(ROOT)),
            "pairwise": str((OUT_DIR / "pairwise_agreement.csv").relative_to(ROOT)),
            "axis": str((OUT_DIR / "agreement_by_axis.csv").relative_to(ROOT)),
            "stratum": str((OUT_DIR / "agreement_by_stratum.csv").relative_to(ROOT)),
            "stratum_cell": str((OUT_DIR / "agreement_by_stratum_cell.csv").relative_to(ROOT)),
            "agent_source": str((OUT_DIR / "agreement_by_agent_source.csv").relative_to(ROOT)),
            "alpha_by_axis": str((OUT_DIR / "agreement_alpha_by_axis.csv").relative_to(ROOT)),
        },
    }

    with (OUT_DIR / "annotation_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # Hard verification: all core assignments should be represented exactly once.
    if len(latest_core) != len(expected_core):
        raise SystemExit(f"Expected {len(expected_core)} core annotations, got {len(latest_core)}")
    missing_total = sum(len(v) for v in missing_by_annotator.values())
    if missing_total:
        raise SystemExit(f"Missing {missing_total} core annotations")
    # Conflicting completed duplicates are revision history. The requested
    # policy is to keep the final entry, so we record them in the summary
    # rather than failing the run.

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
