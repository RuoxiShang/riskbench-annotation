#!/usr/bin/env python3
"""
Sample matched pairs for human evaluation.

This script finds:
1. C2 vs C4 pairs with greatest score differences (after refinement)
2. Before vs After refinement with greatest improvements (within each condition)

Each sample includes:
- Scenario + Actions (baseline, higher risk, lower risk)
- LLM judge scores (all 6 dimensions + overall)
- LLM judge rationales
- Metadata (condition, risk_factor, domain, risk_type, indices)

Usage:
    python sample_for_human_eval.py <exp_dir> <n_samples> <output_dir>

Example:
    python sample_for_human_eval.py ../../experiments/1119_1328_ablation_generation 10 ../../experiments/1119_1328_ablation_generation/human_eval_samples
"""

import json
import re
import sys
from pathlib import Path
from collections import defaultdict
import random

def parse_scores(score_text):
    """Parse judge scores from text format."""
    scores = {}
    patterns = {
        'risk_factor_manipulation': r'Risk Factor Manipulation:\s*(\d+(?:\.\d+)?)/5',
        'risk_ordering': r'Risk Ordering:\s*(\d+(?:\.\d+)?)/5',
        'utility_balance': r'Utility Balance:\s*(\d+(?:\.\d+)?)/5',
        'plausibility': r'Plausibility:\s*(\d+(?:\.\d+)?)/5',
        'differentiation': r'Differentiation:\s*(\d+(?:\.\d+)?)/5',
        'scenario_quality': r'Scenario Quality:\s*(\d+(?:\.\d+)?)/5',
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, score_text)
        if match:
            scores[key] = float(match.group(1))

    return scores

def extract_rationales(score_text):
    """Extract rationale text for each dimension."""
    rationales = {}

    # Pattern to match dimension and its rationale
    pattern = r'(Risk Factor Manipulation|Risk Ordering|Utility Balance|Plausibility|Differentiation|Scenario Quality):\s*\d+(?:\.\d+)?/5\s*\n\s*(?:\*\*)?Rationale(?:\*\*)?:\s*(.+?)(?=\n\n|\n\*\*[A-Z]|\n[A-Z][a-z]+ [A-Z]|$)'

    matches = re.finditer(pattern, score_text, re.DOTALL)
    for match in matches:
        dim_name = match.group(1).lower().replace(' ', '_').replace('/', '_')
        rationale = match.group(2).strip()
        rationales[dim_name] = rationale

    # Try to extract overall summary
    overall_pattern = r'(?:Overall Quality|Summary):\s*\d+(?:\.\d+)?/\d+\s*\n\s*(?:\*\*)?(?:Summary|Rationale)(?:\*\*)?:\s*(.+?)(?=\n\n|\*\*|$)'
    overall_match = re.search(overall_pattern, score_text, re.DOTALL)
    if overall_match:
        rationales['overall_quality'] = overall_match.group(1).strip()

    return rationales

def compute_overall(scores):
    """Compute overall as average of sub-dimensions."""
    dimensions = ['risk_factor_manipulation', 'risk_ordering', 'utility_balance',
                  'plausibility', 'differentiation', 'scenario_quality']
    available = [scores[d] for d in dimensions if d in scores]
    return sum(available) / len(available) if available else 0.0

def parse_refined_output(refined_text):
    """Parse scenario and actions from refined output."""
    result = {}

    # Parse scenario (more flexible patterns)
    # Handle cases where refined_output starts with ** or Scenario:
    scenario_patterns = [
        r'^[\*\s]*\n*(.+?)(?=\n\*\*Baseline Action:|\nBaseline Action:)',  # Starts with ** or whitespace
        r'(?:^|\n)Scenario:\s*\n(.+?)(?=\n\nBaseline Action:|\nBaseline Action:)',
        r'(?:^|\n)(.+?)(?=\n\n(?:\*\*)?Baseline Action:|\n(?:\*\*)?Risk Factor:)',
    ]

    for pattern in scenario_patterns:
        scenario_match = re.search(pattern, refined_text, re.DOTALL)
        if scenario_match:
            scenario_text = scenario_match.group(1).strip()
            # Clean up risk factor line and leading **
            scenario_text = re.sub(r'^\*+\s*', '', scenario_text)
            scenario_text = re.sub(r'\*\*Risk Factor to manipulate:.*?\*\*\n*', '', scenario_text, flags=re.DOTALL)
            result['scenario'] = scenario_text
            break

    # Parse baseline action
    baseline_match = re.search(
        r'(?:^|\n)(?:##? )?\*{0,2}Baseline Action:\*{0,2}\s*\n(.+?)(?=\n\n(?:##? )?\*{0,2}Higher Risk Action:|\n(?:##? )?\*{0,2}Higher Risk Action:|$)',
        refined_text, re.DOTALL | re.IGNORECASE
    )
    if baseline_match:
        result['baseline_action'] = baseline_match.group(1).strip()

    # Parse higher risk action
    higher_match = re.search(
        r'(?:^|\n)(?:##? )?\*{0,2}Higher Risk Action:\*{0,2}\s*\n(.+?)(?=\n\n(?:##? )?\*{0,2}Lower Risk Action:|\n(?:##? )?\*{0,2}Lower Risk Action:|$)',
        refined_text, re.DOTALL | re.IGNORECASE
    )
    if higher_match:
        result['higher_action'] = higher_match.group(1).strip()

    # Parse lower risk action
    lower_match = re.search(
        r'(?:^|\n)(?:##? )?\*{0,2}Lower Risk Action:\*{0,2}\s*\n(.+?)(?:\n---|$)',
        refined_text, re.DOTALL | re.IGNORECASE
    )
    if lower_match:
        result['lower_action'] = lower_match.group(1).strip()

    return result

def parse_before_actions(data):
    """Parse scenario and actions from pre-refinement fields."""
    result = {}
    result['scenario'] = data.get('cleaned_scenario', '')
    result['baseline_action'] = data.get('cleaned_action_baseline', '')
    
    variations = data.get('raw_action_variations', '')
    
    # Simple heuristic parsing for variations
    # Usually "Higher Risk Action" (implicit or explicit) then "Lower Risk Action:"
    
    lower_split = re.split(r'Lower Risk Action:', variations, flags=re.IGNORECASE)
    
    if len(lower_split) > 1:
        # Last part is likely Lower
        result['lower_action'] = lower_split[-1].strip()
        # First part(s) is Higher
        higher_text = lower_split[0].strip()
        # Clean up "Higher Risk Action:" label if present
        higher_text = re.sub(r'^Higher Risk Action:\s*', '', higher_text, flags=re.IGNORECASE).strip()
        result['higher_action'] = higher_text
    else:
        # Fallback: Put everything in higher (unlikely to be correct but safe)
        result['higher_action'] = variations
        result['lower_action'] = ""
        
    return result

def load_data(filepath):
    """Load and parse JSONL data."""
    results = []
    with open(filepath) as f:
        for i, line in enumerate(f):
            if line.strip():
                data = json.loads(line)

                # Parse scores
                before_scores = parse_scores(data.get('scores_before_refine', ''))
                after_scores = parse_scores(data.get('scores_after_refine', ''))

                # Compute overall
                before_overall = compute_overall(before_scores)
                after_overall = compute_overall(after_scores)

                # Parse refined output (AFTER)
                parsed_output = parse_refined_output(data.get('refined_output', ''))
                
                # Parse raw output (BEFORE)
                before_output = parse_before_actions(data)

                # Extract rationales
                before_rationales = extract_rationales(data.get('scores_before_refine', ''))
                after_rationales = extract_rationales(data.get('scores_after_refine', ''))

                results.append({
                    'index': i,
                    'risk_factor': data.get('risk_factor'),
                    'domain': data.get('domain'),
                    'risk_type': data.get('risk_type'),
                    
                    # AFTER data
                    'scenario': parsed_output.get('scenario', '') or data.get('cleaned_scenario', ''),
                    'baseline_action': parsed_output.get('baseline_action', ''),
                    'higher_action': parsed_output.get('higher_action', ''),
                    'lower_action': parsed_output.get('lower_action', ''),
                    
                    # BEFORE data
                    'before_scenario': before_output.get('scenario', ''),
                    'before_baseline': before_output.get('baseline_action', ''),
                    'before_higher': before_output.get('higher_action', ''),
                    'before_lower': before_output.get('lower_action', ''),

                    'before_scores': before_scores,
                    'before_overall': before_overall,
                    'before_rationales': before_rationales,
                    'after_scores': after_scores,
                    'after_overall': after_overall,
                    'after_rationales': after_rationales,
                    'improvement': after_overall - before_overall,
                    'raw_data': data  # Keep for reference
                })

    return results

def find_c2_vs_c4_samples(c2_data, c4_data, n):
    """Find n samples where C2 and C4 differ most (after refinement)."""

    # Create matched pairs
    pairs = []
    for c2, c4 in zip(c2_data, c4_data):
        # Verify they match
        if (c2['risk_factor'] == c4['risk_factor'] and
            c2['domain'] == c4['domain'] and
            c2['risk_type'] == c4['risk_type']):

            diff = c2['after_overall'] - c4['after_overall']
            pairs.append({
                'c2': c2,
                'c4': c4,
                'diff': diff,
                'abs_diff': abs(diff)
            })

    # Sort by absolute difference
    pairs.sort(key=lambda x: x['abs_diff'], reverse=True)

    # Get top n with biggest differences
    top_n_diff = pairs[:n]

    # Also get n samples with smallest differences (for calibration)
    pairs_sorted_by_abs = sorted(pairs, key=lambda x: x['abs_diff'])
    top_n_similar = pairs_sorted_by_abs[:n]

    return {
        'biggest_differences': top_n_diff,
        'most_similar': top_n_similar
    }

def find_before_after_samples(data, condition_name, n):
    """Find n samples with biggest before/after improvement."""

    # Sort by improvement
    sorted_data = sorted(data, key=lambda x: x['improvement'], reverse=True)

    return {
        'condition': condition_name,
        'biggest_improvements': sorted_data[:n],
        'biggest_declines': sorted_data[-n:] if len(sorted_data) >= n else []
    }

def format_sample_for_human(sample_data, sample_type, index):
    """Format a single sample for human evaluation."""

    if sample_type == 'c2_vs_c4':
        # Randomize which is A and which is B
        if random.random() < 0.5:
            version_a, version_b = sample_data['c2'], sample_data['c4']
            true_label_a, true_label_b = 'C2', 'C4'
        else:
            version_a, version_b = sample_data['c4'], sample_data['c2']
            true_label_a, true_label_b = 'C4', 'C2'

        return {
            'sample_id': index,
            'comparison_type': 'C2 vs C4 (after refinement)',
            'score_difference': sample_data['diff'],
            'abs_score_difference': sample_data['abs_diff'],

            # Metadata (common to both)
            'risk_factor': version_a['risk_factor'],
            'domain': version_a['domain'],
            'risk_type': version_a['risk_type'],
            'scenario': version_a['scenario'],

            # Version A (blind)
            'version_a': {
                'true_label': true_label_a,  # Hidden from human evaluators
                'index': version_a['index'],
                'baseline_action': version_a['baseline_action'],
                'higher_action': version_a['higher_action'],
                'lower_action': version_a['lower_action'],
                'scores': version_a['after_scores'],
                'overall_score': version_a['after_overall'],
                'rationales': version_a['after_rationales']
            },

            # Version B (blind)
            'version_b': {
                'true_label': true_label_b,  # Hidden from human evaluators
                'index': version_b['index'],
                'baseline_action': version_b['baseline_action'],
                'higher_action': version_b['higher_action'],
                'lower_action': version_b['lower_action'],
                'scores': version_b['after_scores'],
                'overall_score': version_b['after_overall'],
                'rationales': version_b['after_rationales']
            }
        }

    elif sample_type == 'before_after':
        return {
            'sample_id': index,
            'comparison_type': f"{sample_data['condition']} Before vs After Refinement",
            'improvement': sample_data['sample']['improvement'],

            # Metadata
            'condition': sample_data['condition'],
            'index': sample_data['sample']['index'],
            'risk_factor': sample_data['sample']['risk_factor'],
            'domain': sample_data['sample']['domain'],
            'risk_type': sample_data['sample']['risk_type'],
            'scenario': sample_data['sample']['scenario'], # Default to After scenario for context, but Before has its own

            # Before refinement
            'before': {
                'scenario': sample_data['sample']['before_scenario'],
                'baseline_action': sample_data['sample']['before_baseline'],
                'higher_action': sample_data['sample']['before_higher'],
                'lower_action': sample_data['sample']['before_lower'],
                'scores': sample_data['sample']['before_scores'],
                'overall_score': sample_data['sample']['before_overall'],
                'rationales': sample_data['sample']['before_rationales']
            },

            # After refinement
            'after': {
                'scenario': sample_data['sample']['scenario'],
                'baseline_action': sample_data['sample']['baseline_action'],
                'higher_action': sample_data['sample']['higher_action'],
                'lower_action': sample_data['sample']['lower_action'],
                'scores': sample_data['sample']['after_scores'],
                'overall_score': sample_data['sample']['after_overall'],
                'rationales': sample_data['sample']['after_rationales']
            }
        }

def save_samples(samples, output_dir, filename_prefix):
    """Save samples in multiple formats."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save as JSON
    json_path = output_dir / f'{filename_prefix}.json'
    with open(json_path, 'w') as f:
        json.dump(samples, f, indent=2)

    print(f"✓ Saved JSON: {json_path}")

    # Save as human-readable Markdown
    md_path = output_dir / f'{filename_prefix}.md'
    with open(md_path, 'w') as f:
        f.write(f"# Human Evaluation Samples: {filename_prefix}\n\n")
        f.write(f"Total samples: {len(samples)}\n\n")

        for i, sample in enumerate(samples, 1):
            f.write(f"\n{'='*80}\n")
            f.write(f"## Sample {i}\n")
            f.write(f"{'='*80}\n\n")

            f.write(f"**Comparison Type:** {sample['comparison_type']}\n\n")
            f.write(f"**Metadata:**\n")
            f.write(f"- Risk Factor: {sample['risk_factor']}\n")
            f.write(f"- Domain: {sample['domain']}\n")
            f.write(f"- Risk Type: {sample['risk_type']}\n\n")

            f.write(f"### Scenario\n\n{sample['scenario']}\n\n")

            if 'version_a' in sample:
                # C2 vs C4 comparison
                f.write(f"**Score Difference:** {sample['score_difference']:+.2f} (|Δ| = {sample['abs_score_difference']:.2f})\n\n")

                for version_key, version_label in [('version_a', 'Version A'), ('version_b', 'Version B')]:
                    version = sample[version_key]
                    f.write(f"### {version_label}\n\n")
                    f.write(f"**LLM Overall Score:** {version['overall_score']:.2f}/5\n\n")
                    f.write(f"**Baseline Action:**\n{version['baseline_action']}\n\n")
                    f.write(f"**Higher Risk Action:**\n{version['higher_action']}\n\n")
                    f.write(f"**Lower Risk Action:**\n{version['lower_action']}\n\n")

                    f.write(f"**LLM Dimension Scores:**\n")
                    for dim, score in version['scores'].items():
                        f.write(f"- {dim.replace('_', ' ').title()}: {score:.2f}/5\n")

                    f.write(f"\n**LLM Rationales:**\n")
                    for dim, rationale in version['rationales'].items():
                        f.write(f"- **{dim.replace('_', ' ').title()}:** {rationale}\n")
                    f.write("\n")

            else:
                # Before vs After comparison
                f.write(f"**Improvement:** {sample['improvement']:+.2f}\n\n")
                f.write(f"**Condition:** {sample['condition']}\n\n")

                for timing_key, timing_label in [('before', 'Before Refinement'), ('after', 'After Refinement')]:
                    timing = sample[timing_key]
                    f.write(f"### {timing_label}\n\n")
                    f.write(f"**LLM Overall Score:** {timing['overall_score']:.2f}/5\n\n")
                    
                    f.write(f"**Scenario (if different):**\n{timing.get('scenario', '')}\n\n")
                    f.write(f"**Baseline Action:**\n{timing.get('baseline_action', '')}\n\n")
                    f.write(f"**Higher Risk Action:**\n{timing.get('higher_action', '')}\n\n")
                    f.write(f"**Lower Risk Action:**\n{timing.get('lower_action', '')}\n\n")

                    f.write(f"**LLM Dimension Scores:**\n")
                    for dim, score in timing['scores'].items():
                        f.write(f"- {dim.replace('_', ' ').title()}: {score:.2f}/5\n")

                    f.write(f"\n**LLM Rationales:**\n")
                    for dim, rationale in timing['rationales'].items():
                        f.write(f"- **{dim.replace('_', ' ').title()}:** {rationale}\n")
                    f.write("\n")

    print(f"✓ Saved Markdown: {md_path}")

def main():
    if len(sys.argv) < 4:
        print("Usage: python sample_for_human_eval.py <exp_dir> <n_samples> <output_dir>")
        print("Example: python sample_for_human_eval.py ../../experiments/1119_1328_ablation_generation 10 ../../experiments/1119_1328_ablation_generation/human_eval")
        sys.exit(1)

    exp_dir = Path(sys.argv[1])
    n = int(sys.argv[2])
    output_dir = Path(sys.argv[3])

    print(f"Loading data from: {exp_dir}")
    print(f"Sampling {n} examples per category")
    print(f"Output directory: {output_dir}\n")

    # Load data
    c2_data = load_data(exp_dir / 'c2_aware_output.jsonl')
    c4_data = load_data(exp_dir / 'c4_oneshot_output.jsonl')

    print(f"Loaded {len(c2_data)} C2 samples")
    print(f"Loaded {len(c4_data)} C4 samples\n")

    # 1. Find C2 vs C4 samples with biggest differences
    print("=" * 70)
    print("1. C2 vs C4 Comparisons (After Refinement)")
    print("=" * 70)

    c2_vs_c4 = find_c2_vs_c4_samples(c2_data, c4_data, n)

    print(f"\nBiggest differences (top {n}):")
    for i, pair in enumerate(c2_vs_c4['biggest_differences'][:5], 1):
        print(f"  {i}. Δ={pair['diff']:+.2f} | C2={pair['c2']['after_overall']:.2f} C4={pair['c4']['after_overall']:.2f} | {pair['c2']['risk_factor']}")

    print(f"\nMost similar (top {n}):")
    for i, pair in enumerate(c2_vs_c4['most_similar'][:5], 1):
        print(f"  {i}. Δ={pair['diff']:+.2f} | C2={pair['c2']['after_overall']:.2f} C4={pair['c4']['after_overall']:.2f} | {pair['c2']['risk_factor']}")

    # Format for human eval
    c2_vs_c4_samples = []
    for i, pair in enumerate(c2_vs_c4['biggest_differences']):
        c2_vs_c4_samples.append(format_sample_for_human(pair, 'c2_vs_c4', i))

    save_samples(c2_vs_c4_samples, output_dir, f'c2_vs_c4_biggest_diff_n{n}')

    c2_vs_c4_similar_samples = []
    for i, pair in enumerate(c2_vs_c4['most_similar']):
        c2_vs_c4_similar_samples.append(format_sample_for_human(pair, 'c2_vs_c4', i))

    save_samples(c2_vs_c4_similar_samples, output_dir, f'c2_vs_c4_most_similar_n{n}')

    # 2. Find before/after samples with biggest improvements
    print("\n" + "=" * 70)
    print("2. Before vs After Refinement Comparisons")
    print("=" * 70)

    for condition_data, condition_name in [(c2_data, 'C2'), (c4_data, 'C4')]:
        print(f"\n{condition_name}:")
        before_after = find_before_after_samples(condition_data, condition_name, n)

        print(f"\nBiggest improvements (top {n}):")
        for i, sample in enumerate(before_after['biggest_improvements'][:5], 1):
            print(f"  {i}. Δ={sample['improvement']:+.2f} | Before={sample['before_overall']:.2f} After={sample['after_overall']:.2f} | {sample['risk_factor']}")

        # Format for human eval
        improvement_samples = []
        for i, sample in enumerate(before_after['biggest_improvements']):
            improvement_samples.append(format_sample_for_human(
                {'condition': condition_name, 'sample': sample},
                'before_after',
                i
            ))

        save_samples(improvement_samples, output_dir, f'{condition_name.lower()}_before_after_biggest_improvement_n{n}')

        if before_after['biggest_declines']:
            print(f"\nBiggest declines (bottom {n}):")
            for i, sample in enumerate(before_after['biggest_declines'][:5], 1):
                print(f"  {i}. Δ={sample['improvement']:+.2f} | Before={sample['before_overall']:.2f} After={sample['after_overall']:.2f} | {sample['risk_factor']}")

            decline_samples = []
            for i, sample in enumerate(before_after['biggest_declines']):
                decline_samples.append(format_sample_for_human(
                    {'condition': condition_name, 'sample': sample},
                    'before_after',
                    i
                ))

            save_samples(decline_samples, output_dir, f'{condition_name.lower()}_before_after_biggest_decline_n{n}')

    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"\nGenerated sample files in: {output_dir}")
    print(f"\nFiles created:")
    print(f"  - c2_vs_c4_biggest_diff_n{n}.json/.md")
    print(f"  - c2_vs_c4_most_similar_n{n}.json/.md")
    print(f"  - c2_before_after_biggest_improvement_n{n}.json/.md")
    print(f"  - c4_before_after_biggest_improvement_n{n}.json/.md")
    print(f"  - c2_before_after_biggest_decline_n{n}.json/.md (if any)")
    print(f"  - c4_before_after_biggest_decline_n{n}.json/.md (if any)")

if __name__ == '__main__':
    main()
