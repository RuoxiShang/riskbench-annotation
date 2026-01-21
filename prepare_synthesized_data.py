#!/usr/bin/env python3
"""
Prepare synthesized scenario data for the annotation UI viewer.

This script converts the oumi synthesis output into a format compatible
with the RiskBench annotation UI for easy viewing/review.

Usage:
    python prepare_synthesized_data.py <synthesized.jsonl>
    python prepare_synthesized_data.py <synthesized.jsonl> --name synth_batch1

Output:
    data/synthesized_samples.json
"""

import json
import argparse
from pathlib import Path


def load_synthesized(filepath: Path) -> list:
    """Load synthesized pairs from JSONL file."""
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def parse_variation(var_json_str: str) -> dict:
    """Parse a variation JSON string, handling potential errors."""
    if not var_json_str:
        return None
    try:
        return json.loads(var_json_str)
    except json.JSONDecodeError:
        return None


def format_contents(contents: list) -> str:
    """Format interaction contents into readable text."""
    lines = []
    for interaction in contents:
        for item in interaction:
            role = item.get('role', '?').upper()
            if role == 'USER':
                lines.append(f"**USER:** {item.get('content', '')}")
            elif role == 'AGENT':
                thought = item.get('thought', '')
                action = item.get('action', '')
                if thought:
                    lines.append(f"**AGENT (thought):** {thought}")
                if action:
                    lines.append(f"**AGENT (action):** {action}")
            elif role == 'ENVIRONMENT':
                content = item.get('content', '')
                lines.append(f"**ENV:** {content}")
            elif role == 'SYSTEM':
                lines.append(f"**SYSTEM:** {item.get('content', '')}")
    return '\n\n'.join(lines)


def format_sample_for_ui(pair: dict, sample_id: int) -> dict:
    """
    Format a synthesized pair for the annotation UI.
    
    Creates a sample that shows:
    - Original user request
    - Metadata (scenario, attack type)
    - All 4 variations with their expected responses
    """
    unsafe = pair.get('unsafe_full', {})
    safe = pair.get('safe_full', {})
    
    # Parse all variations
    variations = {}
    var_keys = [
        ('open_ended', 'open_ended_clean'),
        ('proposed_action', 'proposed_action_clean'),
        ('binary_choice', 'binary_choice_clean'),
        ('about_to_execute', 'about_to_execute_clean')
    ]
    
    for var_name, var_key in var_keys:
        var = parse_variation(pair.get(var_key, ''))
        if var:
            variations[var_name] = {
                'goal': var.get('goal', ''),
                'contents': format_contents(var.get('contents', [])),
                'expected_safe': var.get('expected_responses', {}).get('risk_0', ''),
                'expected_risky': var.get('expected_responses', {}).get('risk_1', ''),
                'risk_rationale': var.get('risk_rationale', ''),
                # Variation-specific fields
                'proposed_action': var.get('proposed_action', ''),
                'pending_action': var.get('pending_action', ''),
                'options': var.get('options', {}),
            }
    
    return {
        'sample_id': sample_id,
        'pair_id': pair.get('pair_id', sample_id),
        
        # User request (the key identifier)
        'user_content': pair.get('user_content', ''),
        
        # Metadata
        'scenario': unsafe.get('scenario', safe.get('scenario', '')),
        'attack_type': unsafe.get('attack_type', 'unknown'),
        'safe_id': safe.get('id', ''),
        'unsafe_id': unsafe.get('id', ''),
        
        # Risk descriptions from originals
        'safe_description': safe.get('risk_description', ''),
        'unsafe_description': unsafe.get('risk_description', ''),
        
        # All variations
        'variations': variations,
        'variation_count': len(variations),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Prepare synthesized data for annotation UI"
    )
    parser.add_argument("filepath", help="Path to synthesized JSONL file")
    parser.add_argument("--name", type=str, default="synthesized_samples",
                        help="Output filename (without .json)")
    args = parser.parse_args()
    
    current_dir = Path(__file__).parent.absolute()
    output_dir = current_dir / 'data'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("Synthesized Data Prep for UI")
    print("=" * 60)
    
    # Load data
    filepath = Path(args.filepath)
    if not filepath.exists():
        print(f"Error: {filepath} does not exist")
        return
    
    print(f"\nLoading: {filepath}")
    pairs = load_synthesized(filepath)
    print(f"Loaded {len(pairs)} pairs")
    
    # Format for UI
    samples = []
    for i, pair in enumerate(pairs):
        samples.append(format_sample_for_ui(pair, i))
    
    # Count variations
    total_variations = sum(s['variation_count'] for s in samples)
    
    # Create output structure
    output = {
        'metadata': {
            'source_file': str(filepath),
            'total_pairs': len(samples),
            'total_variations': total_variations,
            'data_type': 'synthesized_scenarios',
        },
        'samples': samples,
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
    print(f"Total pairs: {len(samples)}")
    print(f"Total variations: {total_variations}")
    
    # Attack type breakdown
    attack_types = {}
    scenarios = {}
    for s in samples:
        at = s.get('attack_type', 'unknown')
        sc = s.get('scenario', 'unknown') or 'unknown'
        attack_types[at] = attack_types.get(at, 0) + 1
        scenarios[sc] = scenarios.get(sc, 0) + 1
    
    print(f"\nBy Attack Type:")
    for at, count in sorted(attack_types.items()):
        print(f"  {at}: {count}")
    
    print(f"\nBy Scenario:")
    for sc, count in sorted(scenarios.items()):
        print(f"  {sc}: {count}")
    
    print("\n" + "=" * 60)
    print("Done! Data ready for UI viewing.")
    print("=" * 60)


if __name__ == '__main__':
    main()
