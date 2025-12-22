#!/usr/bin/env python3
"""
Prepare C6 scenario data for human quality assessment annotation.

This script:
1. Reads C6 output.jsonl (scenario + action pairs for risk detection)
2. Parses cleaned_refined_output to extract Scenario, Action, and Risk
3. Optionally samples N items
4. Formats for the annotation UI
5. Outputs to data/c6_samples.json

Usage:
    python prepare_c6_data.py <output.jsonl>
    python prepare_c6_data.py <output.jsonl> --sample 50
    python prepare_c6_data.py <output.jsonl> --name c6_batch1

Output:
    data/c6_samples.json
"""

import json
import argparse
import random
import re
from pathlib import Path


def load_samples(filepath: Path) -> list:
    """Load samples from JSONL file."""
    samples = []
    with open(filepath) as f:
        for i, line in enumerate(f):
            if line.strip():
                data = json.loads(line)
                data['original_index'] = i
                samples.append(data)
    return samples


def parse_refined_output(refined_text: str) -> tuple:
    """
    Parse the refined output to extract scenario, action, and risk.

    Format:
        [Scenario text]

        Action:
        [Action text]

        Risk:
        [Risk text]
    """
    if not refined_text:
        return '', '', ''

    # Normalize newlines
    refined_text = refined_text.replace('\r\n', '\n')

    # flexible splitting pattern
    # We look for "\nAction:" or "\n\nAction:" or "**Action:**" case insensitive
    # Handle optional markdown bolding (one or two asterisks)
    action_split = re.split(r'\n+\*{0,2}Action:\*{0,2}\s*\n*', refined_text, flags=re.IGNORECASE)
    
    if len(action_split) < 2:
        # Fallback: try splitting without requiring newlines before if it's at the start of a line
        action_split = re.split(r'(?:^|\n)\*{0,2}Action:\*{0,2}\s*', refined_text, flags=re.IGNORECASE)

    if len(action_split) < 2:
        # Fallback: return the whole text as scenario if no Action marker
        return refined_text.strip(), '', ''

    scenario = action_split[0].strip()
    # Join the rest in case "Action:" appears multiple times (unlikely but safe)
    remaining = "\n".join(action_split[1:])

    # Split action and risk
    # We look for "\nRisk:" or "\n\nRisk:" or "**Risk:**" case insensitive
    risk_split = re.split(r'\n+\*{0,2}Risk:\*{0,2}\s*\n*', remaining, flags=re.IGNORECASE)
    
    if len(risk_split) < 2:
        # Fallback: try splitting without requiring newlines
        risk_split = re.split(r'(?:^|\n)\*{0,2}Risk:\*{0,2}\s*', remaining, flags=re.IGNORECASE)
    
    if len(risk_split) < 2:
        # Fallback: action only
        return scenario, remaining.strip(), ''

    action = risk_split[0].strip()
    risk = "\n".join(risk_split[1:]).strip()

    return scenario, action, risk


def format_sample_for_annotation(sample: dict, sample_id: int) -> dict:
    """Format a single sample for the annotation UI."""

    # Parse the refined output to extract scenario, action, and risk
    refined = sample.get('cleaned_refined_output', '')
    
    # Also get the AI review (optional context)
    ai_review = sample.get('cleaned_review') or sample.get('ai_review', '')

    if refined:
        scenario, action, risk = parse_refined_output(refined)
    else:
        # Fallback to original versions if no refined output
        scenario = sample.get('cleaned_scenario', '')
        action = sample.get('cleaned_action', '')
        risk = sample.get('cleaned_risk', '')

    return {
        'sample_id': sample_id,
        'original_index': sample.get('original_index', sample_id),

        # Metadata for display and filtering
        'activity_context': sample.get('activity_context', ''),
        'risk_factor': sample.get('risk_factor', ''),
        'risk_type': sample.get('risk_type', ''),

        # Content to annotate
        'scenario': scenario,
        'action': action,
        'risk_description': risk,

        # Keep original refined output for reference
        'refined_output': refined,

        # AI self-critique (useful context, maybe show after annotation)
        'ai_review': ai_review,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Prepare C6 data for human quality assessment"
    )
    parser.add_argument("filepath", help="Path to C6 output JSONL file")
    parser.add_argument("--sample", type=int, default=0,
                        help="Number of samples to randomly select (0 = all)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for sampling")
    parser.add_argument("--name", type=str, default="c6_samples",
                        help="Output filename (without .json)")
    args = parser.parse_args()

    current_dir = Path(__file__).parent.absolute()
    output_dir = current_dir / 'data'
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("C6 Quality Assessment Data Prep")
    print("=" * 60)

    # Load samples
    filepath = Path(args.filepath)
    if not filepath.exists():
        print(f"Error: {filepath} does not exist")
        return

    print(f"\nLoading: {filepath}")
    samples = load_samples(filepath)
    print(f"Loaded {len(samples)} samples")

    # Sample if requested
    if args.sample > 0 and args.sample < len(samples):
        random.seed(args.seed)
        samples = random.sample(samples, args.sample)
        print(f"Randomly sampled {len(samples)} items (seed={args.seed})")

    # Format for annotation
    formatted = []
    for i, sample in enumerate(samples):
        formatted.append(format_sample_for_annotation(sample, i))

    # Create output structure
    output = {
        'metadata': {
            'source_file': str(filepath),
            'total_samples': len(formatted),
            'sampled': args.sample > 0,
            'seed': args.seed if args.sample > 0 else None,
        },
        'samples': formatted,
    }

    # Save
    output_path = output_dir / f'{args.name}.json'
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved: {output_path}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total samples: {len(formatted)}")

    # Show distribution of risk factors and types
    risk_factors = {}
    risk_types = {}
    for s in formatted:
        rf = s.get('risk_factor', 'unknown')
        rt = s.get('risk_type', 'unknown')
        risk_factors[rf] = risk_factors.get(rf, 0) + 1
        risk_types[rt] = risk_types.get(rt, 0) + 1

    print(f"\nRisk Factors:")
    for rf, count in sorted(risk_factors.items(), key=lambda x: -x[1]):
        print(f"  {rf}: {count}")

    print(f"\nRisk Types:")
    for rt, count in sorted(risk_types.items(), key=lambda x: -x[1]):
        print(f"  {rt}: {count}")

    print("\n" + "=" * 60)
    print("Done! The data is ready for annotation.")
    print("=" * 60)


if __name__ == '__main__':
    main()
