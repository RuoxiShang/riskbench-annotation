"""
Prepare family-based review data for the annotation UI.

Groups accepted pairs by seed scenario ID to create "families":
  - The R-Judge seed (from 01_all_scenarios.jsonl) with its full interaction & ground truth
  - The original pair (from accepted_pairs_clean.jsonl where source='original')
  - Dimension variations (from accepted_pairs_clean.jsonl where source='variation')

Additional fields (original_classification, risk_trigger_summary) come from accepted_pairs_raw.jsonl.

Usage:
    cd annotation
    python prepare_family_review.py
"""

import json
from pathlib import Path

# --- Configuration ---
SEEDS = ["9", "99", "111", "20", "145"]
ANNOTATORS = ["Anna", "Shang Hong", "Orfeas", "Yu", "Manos", "Chryssa", "Christina", "Rico"]

DATA_DIR = Path(__file__).resolve().parent.parent / "pipeline_v2" / "data" / "pipeline"
SCENARIOS_FILE = DATA_DIR / "01_all_scenarios.jsonl"
CLEAN_FILE = DATA_DIR / "export" / "accepted_pairs_clean.jsonl"
RAW_FILE = DATA_DIR / "export" / "accepted_pairs_raw.jsonl"
OUTPUT_FILE = Path(__file__).resolve().parent / "data" / "family_review_samples.json"


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    # Load sources
    scenarios = {str(r["scenario_id"]): r for r in load_jsonl(SCENARIOS_FILE)}
    clean_records = load_jsonl(CLEAN_FILE)
    raw_by_id = {str(r["record_id"]): r for r in load_jsonl(RAW_FILE)}

    # Separate originals and variations in clean
    originals_by_id = {}
    variations_by_seed = {}
    for r in clean_records:
        rid = str(r["id"])
        if r["source"] == "original":
            originals_by_id[rid] = r
        elif r["source"] == "variation":
            # Extract seed id: everything before the first '_'
            seed_id = rid.split("_")[0]
            variations_by_seed.setdefault(seed_id, []).append(r)

    families = []
    for seed_id in SEEDS:
        scenario = scenarios.get(seed_id)
        original = originals_by_id.get(seed_id)
        if not scenario or not original:
            print(f"  WARNING: seed {seed_id} missing scenario or original pair, skipping")
            continue

        # Build seed panel data
        seed_data = {
            "scenario_id": seed_id,
            "category": scenario["category"],
            "subcategory": scenario["subcategory"],
            "agent_profile": scenario.get("agent_profile", ""),
            "formatted_interaction": scenario["formatted_interaction"],
            "ground_truth_risk": scenario["ground_truth_risk"],
            "label": scenario.get("label"),
            "attack_type": original.get("attack_type", ""),
        }

        # Build original pair
        original_pair = _build_pair(original, raw_by_id, is_variation=False)

        # Build variation pairs
        var_list = variations_by_seed.get(seed_id, [])
        var_list.sort(key=lambda r: str(r["id"]))
        variation_pairs = [_build_pair(v, raw_by_id, is_variation=True) for v in var_list]

        family = {
            "family_id": seed_id,
            "seed": seed_data,
            "original_pair": original_pair,
            "variations": variation_pairs,
            "assigned_annotators": ANNOTATORS,
        }
        families.append(family)

    output = {
        "metadata": {
            "total_families": len(families),
            "seeds": SEEDS,
            "annotators": ANNOTATORS,
        },
        "families": families,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(families)} families to {OUTPUT_FILE}")
    for fam in families:
        n_var = len(fam["variations"])
        print(f"  seed {fam['family_id']}: {fam['seed']['category']}/{fam['seed']['subcategory']} — 1 original + {n_var} variations")


def _build_pair(record, raw_by_id, is_variation):
    rid = str(record["id"])
    raw = raw_by_id.get(rid, {})
    dimension = None
    if is_variation:
        parts = rid.split("_", 1)
        dimension = parts[1] if len(parts) > 1 else None

    return {
        "pair_id": rid,
        "source": record.get("source", ""),
        "dimension": dimension,
        "original_classification": raw.get("original_classification", ""),
        "risk_trigger_summary": raw.get("risk_trigger_summary", ""),
        "version_a_scenario": record.get("version_a_scenario", ""),
        "version_a_full_scenario": record.get("version_a_full_scenario", ""),
        "version_a_ground_truth": record.get("version_a_ground_truth", ""),
        "version_b_scenario": record.get("version_b_scenario", ""),
        "version_b_full_scenario": record.get("version_b_full_scenario", ""),
        "version_b_ground_truth": record.get("version_b_ground_truth", ""),
        "what_changed": record.get("what_changed", ""),
        "why_classification_flipped": record.get("why_classification_flipped", ""),
        "dimension_variation_description": record.get("dimension_variation_description", ""),
        "category": record.get("category", ""),
        "subcategory": record.get("subcategory", ""),
        "attack_type": record.get("attack_type", ""),
        "agent_profile": record.get("agent_profile", ""),
        "truncation_step": record.get("truncation_step"),
        "execution_point_step": record.get("execution_point_step"),
        "original_total_steps": record.get("original_total_steps"),
    }


if __name__ == "__main__":
    main()
