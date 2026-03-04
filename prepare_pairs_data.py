"""
Prepare paired scenario data for the annotation UI.

Converts accepted_pairs_clean.jsonl to the annotation format
expected by the pair_review task in index.html.

Usage:
    cd annotation
    python prepare_pairs_data.py /path/to/accepted_pairs_clean.jsonl
    python prepare_pairs_data.py /path/to/accepted_pairs_clean.jsonl --sample 30
"""

import argparse
import json
import random
from pathlib import Path


def format_interaction(text):
    """Clean up interaction text for display."""
    if not text:
        return ""
    return text.strip()


def main():
    parser = argparse.ArgumentParser(description="Prepare paired scenarios for annotation")
    parser.add_argument("input", type=Path, help="Path to accepted_pairs_clean.jsonl")
    parser.add_argument("-o", "--output", type=Path, default=Path("data/pair_review_samples.json"))
    parser.add_argument("--sample", type=int, default=None, help="Random sample N records")
    args = parser.parse_args()

    with open(args.input) as f:
        records = [json.loads(l) for l in f]

    if args.sample and args.sample < len(records):
        random.seed(42)
        records = random.sample(records, args.sample)

    samples = []
    for i, r in enumerate(records):
        sample = {
            "sample_id": i,
            "record_id": r["id"],
            "source": r.get("source", ""),
            "category": r.get("category", ""),
            "subcategory": r.get("subcategory", ""),
            "attack_type": r.get("attack_type", ""),
            "risk_severity_tag": r.get("risk_severity_tag"),
            "scenario_difficulty_tag": r.get("scenario_difficulty_tag"),
            "agent_profile": r.get("agent_profile", ""),
            "truncation_type": r.get("truncation_type", "at_trigger"),
            "truncation_step": r.get("truncation_step", ""),
            "execution_point_step": r.get("execution_point_step"),
            "original_total_steps": r.get("original_total_steps", ""),
            "version_a": {
                "scenario": format_interaction(r.get("version_a_scenario", "")),
                "full_scenario": format_interaction(r.get("version_a_full_scenario", "")),
                "ground_truth": r.get("version_a_ground_truth", ""),
            },
            "version_b": {
                "scenario": format_interaction(r.get("version_b_scenario", "")),
                "full_scenario": format_interaction(r.get("version_b_full_scenario", "")),
                "ground_truth": r.get("version_b_ground_truth", ""),
            },
            "what_changed": r.get("what_changed", ""),
            "why_classification_flipped": r.get("why_classification_flipped", ""),
        }
        samples.append(sample)

    output = {
        "metadata": {
            "source_file": str(args.input),
            "total_samples": len(samples),
            "sampled": args.sample is not None,
        },
        "samples": samples,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"  Prepared {len(samples)} samples → {args.output}")
    from collections import Counter
    cats = Counter(s["category"] for s in samples)
    print(f"  Categories: {dict(cats)}")
    sources = Counter(s["source"] for s in samples)
    print(f"  Sources: {dict(sources)}")


if __name__ == "__main__":
    main()
