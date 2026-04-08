"""
Prepare data for the Dataset Explorer viewer.

Reads final_dataset.jsonl and groups records into a nested JSON structure:
  Category > Subcategory > Seed families (by original_scenario_id + truncation_type)
    > Dimensions (ORIGINAL, RS1, RS2, ...)
      > A/B pair (linked by pair_id)

Usage:
    cd annotation
    python prepare_dataset_explorer.py
"""

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "pipeline_v2" / "data" / "pipeline_final_v2_0331" / "final_dataset.jsonl"
SEEDS_FILE = Path(__file__).resolve().parent.parent / "pipeline_v2" / "data" / "pipeline_final_v2_0331" / "01_all_scenarios.jsonl"
STEP_TAGS_FILE = Path(__file__).resolve().parent.parent / "pipeline_v2" / "data" / "pipeline_final_v2_0331" / "02_step_tags_merged.jsonl"
OUTPUT_FILE = Path(__file__).resolve().parent / "data" / "dataset_explorer.json"

# Dimension ordering for tabs
DIM_ORDER = [
    "ORIGINAL",
    "RS1_HARM_INTENSITY", "RS2_SCOPE_SCALE", "RS3_TARGET",
    "RS4_DEPENDENCY", "RS5_OVERSIGHT", "RS6_REVERSIBILITY",
    "SD1_AMBIGUITY", "SD2_PROVENANCE", "SD3_OBFUSCATION",
    "SD4_EMOTIONAL", "SD5_DISTRACTION",
]


def clean_value(v):
    """Convert NaN/None to null-safe values for JSON."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    records = load_jsonl(DATA_FILE)
    print(f"Loaded {len(records)} records from {DATA_FILE.name}")

    # Load seed scenarios for full interaction context
    seeds_by_id = {}
    if SEEDS_FILE.exists():
        for r in load_jsonl(SEEDS_FILE):
            seeds_by_id[str(r["scenario_id"])] = r
        print(f"Loaded {len(seeds_by_id)} seed scenarios")

    # Load step tag consensus for per-model details (keyed by scenario_id = seed number)
    step_tags_by_id = {}
    if STEP_TAGS_FILE.exists():
        for r in load_jsonl(STEP_TAGS_FILE):
            step_tags_by_id[str(r["scenario_id"])] = r
        print(f"Loaded {len(step_tags_by_id)} step tag records")

    # Group into families by (original_scenario_id, truncation_type)
    family_map = defaultdict(list)
    for r in records:
        seed = str(r["original_scenario_id"])
        trunc = r["truncation_type"]
        family_key = f"{seed}_{trunc}"
        family_map[family_key].append(r)

    # Build families
    families = []
    for family_key, recs in sorted(family_map.items()):
        first = recs[0]
        seed_id = str(first["original_scenario_id"])
        trunc = first["truncation_type"]

        # Group by dimension within family
        dim_map = defaultdict(list)
        for r in recs:
            dim_map[r["dimension_code"]].append(r)

        # Build dimension entries in canonical order
        dimensions = []
        seen_dims = set()
        for dim_code in DIM_ORDER:
            if dim_code in dim_map:
                seen_dims.add(dim_code)
                dimensions.append(_build_dimension(dim_code, dim_map[dim_code]))
        # Any remaining dimensions not in DIM_ORDER
        for dim_code in sorted(dim_map.keys()):
            if dim_code not in seen_dims:
                dimensions.append(_build_dimension(dim_code, dim_map[dim_code]))

        # Get the seed's full interaction from 01_all_scenarios
        seed_scenario = seeds_by_id.get(seed_id, {})

        # Step tag details: prefer 02_step_tags_merged (always has per-model data),
        # fall back to final_dataset records.
        # seed_id may contain truncation suffix (e.g., "0_at_trigger"), strip it for lookup.
        bare_seed = seed_id.split("_at_trigger")[0].split("_pre_execution")[0]
        step_tag_merged = step_tags_by_id.get(bare_seed, {})
        step_tag_models = None
        if step_tag_merged:
            step_tag_models = _parse_step_tag_details(step_tag_merged.get("step_tag_details"))
        if not step_tag_models:
            step_tag_rec = next(
                (r for r in recs if r.get("step_tag_details")),
                recs[0],
            )
            step_tag_models = _parse_step_tag_details(step_tag_rec.get("step_tag_details"))

        family = {
            "family_id": family_key,
            "seed_id": seed_id,
            "truncation_type": trunc,
            "category": first["category"],
            "subcategory": first["subcategory"],
            "attack_type": first.get("attack_type", ""),
            "agent_profile": first.get("agent_profile", ""),
            "ground_truth_risk": first.get("ground_truth_risk", ""),
            "seed_full_interaction": seed_scenario.get("formatted_interaction", ""),
            "record_count": len(recs),
            "step_tag_agreement": first.get("step_tag_agreement", ""),
            "step_tag_models": step_tag_models,
            "dimensions": dimensions,
        }
        families.append(family)

    # Compute issue flags per family
    for fam in families:
        issues = []
        for dim in fam["dimensions"]:
            for ver in [dim["version_a"], dim["version_b"]]:
                if ver and not ver["classification"]:
                    issues.append("no_classification")
                if ver and ver["classification"] == "version_a" and ver.get("safe_actions"):
                    issues.append("cornered_has_safe_actions")
            if dim.get("variation_review_verdict") == "majority_accept":
                issues.append("var_review_majority")
            if dim.get("pair_review_verdict") == "majority_accept":
                issues.append("pair_review_majority")
            if not dim["is_paired"]:
                issues.append("unpaired")
        if fam.get("step_tag_agreement") == "majority":
            issues.append("step_tag_majority")
        # Deduplicate
        fam["issues"] = sorted(set(issues))
        fam["issue_count"] = len(fam["issues"])

    # Build category tree for sidebar
    cat_tree = defaultdict(lambda: defaultdict(list))
    for fam in families:
        cat_tree[fam["category"]][fam["subcategory"]].append(fam["family_id"])

    # Summary stats
    total_records = len(records)
    total_paired = sum(1 for r in records if r.get("is_paired"))
    cats = Counter(r["category"] for r in records)
    dims = Counter(r["dimension_code"] for r in records)
    classifications = Counter(r["classification"] for r in records)

    output = {
        "metadata": {
            "total_records": total_records,
            "total_families": len(families),
            "total_paired": total_paired,
            "total_unpaired": total_records - total_paired,
            "categories": dict(cats),
            "dimensions": dict(dims),
            "classifications": dict(classifications),
        },
        "category_tree": {
            cat: {sub: fam_ids for sub, fam_ids in sorted(subs.items())}
            for cat, subs in sorted(cat_tree.items())
        },
        "families": families,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=None, default=str)

    print(f"\nWrote {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size // 1024} KB)")
    print(f"  {len(families)} families across {len(cat_tree)} categories")
    for cat, subs in sorted(cat_tree.items()):
        n = sum(len(ids) for ids in subs.values())
        print(f"    {cat}: {n} families in {len(subs)} subcategories")


def _parse_review_details(raw):
    """Parse review details JSON into per-model verdicts dict."""
    if not raw:
        return None
    try:
        d = json.loads(raw) if isinstance(raw, str) else raw
        return {m: v for m, v in d.get("verdicts", {}).items()}
    except (json.JSONDecodeError, TypeError):
        return None


def _parse_step_tag_details(raw):
    """Parse step tag details into per-model breakdown."""
    if not raw:
        return None
    try:
        d = json.loads(raw) if isinstance(raw, str) else raw
        return {
            "risk_trigger": {m: v for m, v in d.get("risk_trigger", {}).get("per_model", {}).items()},
            "execution_point": {m: v for m, v in d.get("execution_point", {}).get("per_model", {}).items()},
        }
    except (json.JSONDecodeError, TypeError):
        return None


def _build_dimension(dim_code, recs):
    """Build a dimension entry with its A/B pair."""
    # Sort: non-paired first, paired second
    recs.sort(key=lambda r: (1 if "_paired" in r["scenario_id"] else 0, r["scenario_id"]))

    version_a = None
    version_b = None
    for r in recs:
        cleaned = _clean_record(r)
        if r["classification"] == "version_a":
            version_a = cleaned
        elif r["classification"] == "version_b":
            version_b = cleaned
        else:
            # Empty classification — treat as version_a
            if version_a is None:
                version_a = cleaned
            else:
                version_b = cleaned

    first = recs[0]
    return {
        "dimension_code": dim_code,
        "dimension_name": first.get("dimension_name", dim_code),
        "change_summary": first.get("change_summary", ""),
        "variation_direction": first.get("variation_direction", ""),
        "variation_review_verdict": clean_value(first.get("variation_review_verdict")),
        "variation_review_models": _parse_review_details(first.get("variation_review_details")),
        "is_paired": first.get("is_paired", False),
        "pair_id": first.get("pair_id"),
        "pair_review_verdict": clean_value(first.get("pair_review_verdict")),
        "pair_review_models": _parse_review_details(first.get("pair_review_details")),
        "version_a": version_a,
        "version_b": version_b,
    }


def _clean_record(r):
    """Extract the fields needed for display."""
    return {
        "scenario_id": r["scenario_id"],
        "classification": r["classification"],
        "classification_source": r.get("classification_source", ""),
        "formatted_interaction": r["formatted_interaction"],
        "truncation_step": clean_value(r.get("truncation_step")),
        "risk_trigger_step": clean_value(r.get("risk_trigger_step")),
        "execution_point_step": clean_value(r.get("execution_point_step")),
        "total_steps": clean_value(r.get("total_steps")),
        "users_original_request": r.get("users_original_request", ""),
        "ground_truth_rationale": r.get("ground_truth_rationale", ""),
        "safe_actions": r.get("safe_actions", []),
        "unsafe_action": r.get("unsafe_action", ""),
        "step_tag_agreement": r.get("step_tag_agreement", ""),
        "step_tag_models": _parse_step_tag_details(r.get("step_tag_details")),
        "pairing_difficulty": clean_value(r.get("pairing_difficulty")),
    }


if __name__ == "__main__":
    main()
