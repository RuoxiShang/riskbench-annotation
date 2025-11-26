#!/usr/bin/env python3
"""
Prepare annotation data from experiment results.

This script:
1. Scans experiments/ for valid runs (or accepts explicit path)
2. Extracts samples with HIGH CONTRAST (biggest score differences)
3. Saves to data/ folder for the annotation UI

Usage:
    python prepare_data.py                              # Interactive mode
    python prepare_data.py <exp_dir>                    # Use specific experiment
    python prepare_data.py <exp_dir> <n>                # Specify sample count
    python prepare_data.py <exp_dir> <n> <min_diff>     # Set min score difference (default: 0.3)

The min_diff threshold filters out low-contrast samples where score differences
are too small to be meaningful for human evaluation.
"""

import json
import re
import sys
import random
from pathlib import Path
from collections import defaultdict


# =============================================================================
# PARSING FUNCTIONS
# =============================================================================

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
    pattern = r'(Risk Factor Manipulation|Risk Ordering|Utility Balance|Plausibility|Differentiation|Scenario Quality):\s*\d+(?:\.\d+)?/5\s*\n\s*(?:\*\*)?Rationale(?:\*\*)?:\s*(.+?)(?=\n\n|\n\*\*[A-Z]|\n[A-Z][a-z]+ [A-Z]|$)'
    matches = re.finditer(pattern, score_text, re.DOTALL)
    for match in matches:
        dim_name = match.group(1).lower().replace(' ', '_').replace('/', '_')
        rationale = match.group(2).strip()
        rationales[dim_name] = rationale
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
    
    scenario_patterns = [
        r'^[\*\s]*\n*(.+?)(?=\n\*\*Baseline Action:|\nBaseline Action:)',
        r'(?:^|\n)Scenario:\s*\n(.+?)(?=\n\nBaseline Action:|\nBaseline Action:)',
        r'(?:^|\n)(.+?)(?=\n\n(?:\*\*)?Baseline Action:|\n(?:\*\*)?Risk Factor:)',
    ]
    for pattern in scenario_patterns:
        scenario_match = re.search(pattern, refined_text, re.DOTALL)
        if scenario_match:
            scenario_text = scenario_match.group(1).strip()
            scenario_text = re.sub(r'^\*+\s*', '', scenario_text)
            scenario_text = re.sub(r'\*\*Risk Factor to manipulate:.*?\*\*\n*', '', scenario_text, flags=re.DOTALL)
            result['scenario'] = scenario_text
            break

    baseline_match = re.search(
        r'(?:^|\n)(?:##? )?\*{0,2}Baseline Action:\*{0,2}\s*\n(.+?)(?=\n\n(?:##? )?\*{0,2}Higher Risk Action:|\n(?:##? )?\*{0,2}Higher Risk Action:|$)',
        refined_text, re.DOTALL | re.IGNORECASE
    )
    if baseline_match:
        result['baseline_action'] = baseline_match.group(1).strip()

    higher_match = re.search(
        r'(?:^|\n)(?:##? )?\*{0,2}Higher Risk Action:\*{0,2}\s*\n(.+?)(?=\n\n(?:##? )?\*{0,2}Lower Risk Action:|\n(?:##? )?\*{0,2}Lower Risk Action:|$)',
        refined_text, re.DOTALL | re.IGNORECASE
    )
    if higher_match:
        result['higher_action'] = higher_match.group(1).strip()

    lower_match = re.search(
        r'(?:^|\n)(?:##? )?\*{0,2}Lower Risk Action:\*{0,2}\s*\n(.+?)(?:\n---|$)',
        refined_text, re.DOTALL | re.IGNORECASE
    )
    if lower_match:
        result['lower_action'] = lower_match.group(1).strip()

    return result


def parse_before_actions(data):
    """Parse scenario and actions from pre-refinement fields."""
    result = {
        'scenario': data.get('cleaned_scenario', ''),
        'baseline_action': data.get('cleaned_action_baseline', '')
    }
    variations = data.get('raw_action_variations', '')
    lower_split = re.split(r'Lower Risk Action:', variations, flags=re.IGNORECASE)
    if len(lower_split) > 1:
        result['lower_action'] = lower_split[-1].strip()
        higher_text = lower_split[0].strip()
        higher_text = re.sub(r'^Higher Risk Action:\s*', '', higher_text, flags=re.IGNORECASE).strip()
        result['higher_action'] = higher_text
    else:
        result['higher_action'] = variations
        result['lower_action'] = ""
    return result


# =============================================================================
# DATA LOADING
# =============================================================================

def load_data(filepath):
    """Load and parse JSONL data."""
    results = []
    with open(filepath) as f:
        for i, line in enumerate(f):
            if line.strip():
                data = json.loads(line)
                before_scores = parse_scores(data.get('scores_before_refine', ''))
                after_scores = parse_scores(data.get('scores_after_refine', ''))
                before_overall = compute_overall(before_scores)
                after_overall = compute_overall(after_scores)
                parsed_output = parse_refined_output(data.get('refined_output', ''))
                before_output = parse_before_actions(data)
                before_rationales = extract_rationales(data.get('scores_before_refine', ''))
                after_rationales = extract_rationales(data.get('scores_after_refine', ''))

                results.append({
                    'index': i,
                    'risk_factor': data.get('risk_factor'),
                    'domain': data.get('domain'),
                    'risk_type': data.get('risk_type'),
                    'scenario': parsed_output.get('scenario', '') or data.get('cleaned_scenario', ''),
                    'baseline_action': parsed_output.get('baseline_action', ''),
                    'higher_action': parsed_output.get('higher_action', ''),
                    'lower_action': parsed_output.get('lower_action', ''),
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
                })
    return results


# =============================================================================
# SAMPLING FUNCTIONS
# =============================================================================

def find_c2_vs_c4_samples(c2_data, c4_data, n, min_diff=0.5):
    """Find n samples where C2 and C4 differ most.
    
    Args:
        c2_data: List of C2 experiment results
        c4_data: List of C4 experiment results  
        n: Number of samples to return
        min_diff: Minimum score difference threshold (default 0.5)
    """
    pairs = []
    for c2, c4 in zip(c2_data, c4_data):
        if (c2['risk_factor'] == c4['risk_factor'] and
            c2['domain'] == c4['domain'] and
            c2['risk_type'] == c4['risk_type']):
            diff = c2['after_overall'] - c4['after_overall']
            abs_diff = abs(diff)
            # Only include pairs with sufficient contrast
            if abs_diff >= min_diff:
                pairs.append({'c2': c2, 'c4': c4, 'diff': diff, 'abs_diff': abs_diff})

    pairs.sort(key=lambda x: x['abs_diff'], reverse=True)
    
    print(f"  Found {len(pairs)} pairs with score diff >= {min_diff}")
    if pairs:
        print(f"  Score diff range: {pairs[-1]['abs_diff']:.2f} - {pairs[0]['abs_diff']:.2f}")
    
    return pairs[:n]


def find_before_after_samples(data, condition_name, n, min_improvement=0.3):
    """Find n samples with biggest before/after improvement.
    
    Args:
        data: List of experiment results
        condition_name: Name of the condition (C2/C4)
        n: Number of samples to return
        min_improvement: Minimum improvement threshold (default 0.3)
    """
    # Filter by minimum improvement
    filtered = [d for d in data if d['improvement'] >= min_improvement]
    sorted_data = sorted(filtered, key=lambda x: x['improvement'], reverse=True)
    
    print(f"  {condition_name}: Found {len(filtered)} samples with improvement >= {min_improvement}")
    if sorted_data:
        print(f"  Improvement range: {sorted_data[-1]['improvement']:.2f} - {sorted_data[0]['improvement']:.2f}")
    
    return {
        'condition': condition_name,
        'biggest_improvements': sorted_data[:n],
    }


def format_sample_for_human(sample_data, sample_type, index):
    """Format a single sample for human evaluation."""
    if sample_type == 'c2_vs_c4':
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
            'risk_factor': version_a['risk_factor'],
            'domain': version_a['domain'],
            'risk_type': version_a['risk_type'],
            'scenario': version_a['scenario'],
            'version_a': {
                'true_label': true_label_a,
                'index': version_a['index'],
                'scenario': version_a['scenario'],
                'baseline_action': version_a['baseline_action'],
                'higher_action': version_a['higher_action'],
                'lower_action': version_a['lower_action'],
                'scores': version_a['after_scores'],
                'overall_score': version_a['after_overall'],
                'rationales': version_a['after_rationales']
            },
            'version_b': {
                'true_label': true_label_b,
                'index': version_b['index'],
                'scenario': version_b['scenario'],
                'baseline_action': version_b['baseline_action'],
                'higher_action': version_b['higher_action'],
                'lower_action': version_b['lower_action'],
                'scores': version_b['after_scores'],
                'overall_score': version_b['after_overall'],
                'rationales': version_b['after_rationales']
            }
        }

    elif sample_type == 'before_after':
        sample = sample_data['sample']
        return {
            'sample_id': index,
            'comparison_type': f"{sample_data['condition']} Before vs After Refinement",
            'improvement': sample['improvement'],
            'condition': sample_data['condition'],
            'index': sample['index'],
            'risk_factor': sample['risk_factor'],
            'domain': sample['domain'],
            'risk_type': sample['risk_type'],
            'scenario': sample['scenario'],
            'before': {
                'scenario': sample['before_scenario'],
                'baseline_action': sample['before_baseline'],
                'higher_action': sample['before_higher'],
                'lower_action': sample['before_lower'],
                'scores': sample['before_scores'],
                'overall_score': sample['before_overall'],
                'rationales': sample['before_rationales']
            },
            'after': {
                'scenario': sample['scenario'],
                'baseline_action': sample['baseline_action'],
                'higher_action': sample['higher_action'],
                'lower_action': sample['lower_action'],
                'scores': sample['after_scores'],
                'overall_score': sample['after_overall'],
                'rationales': sample['after_rationales']
            }
        }


def save_samples(samples, output_dir, filename):
    """Save samples as JSON."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f'{filename}.json'
    with open(json_path, 'w') as f:
        json.dump(samples, f, indent=2)
    print(f"  ✓ Saved: {json_path}")


# =============================================================================
# EXPERIMENT DISCOVERY
# =============================================================================

def get_experiment_folders(experiments_dir):
    """List valid experiment folders sorted by date (newest first)."""
    exp_path = Path(experiments_dir)
    if not exp_path.exists():
        return []
    
    folders = []
    for p in exp_path.iterdir():
        if not p.is_dir():
            continue
        has_std = (p / 'c2_aware_output.jsonl').exists() and (p / 'c4_oneshot_output.jsonl').exists()
        has_human = (p / 'c2_aware_human_val_output.jsonl').exists() and (p / 'c4_oneshot_human_val_output.jsonl').exists()
        
        if has_std or has_human:
            mtime = p.stat().st_mtime
            folders.append((p, mtime, 'human' if has_human else 'std'))
    
    folders.sort(key=lambda x: x[1], reverse=True)
    return folders


# =============================================================================
# MAIN
# =============================================================================

def main():
    current_dir = Path(__file__).parent.absolute()
    output_dir = current_dir / 'data'
    experiments_dir = current_dir.parent.parent / 'experiments'
    
    print("=" * 60)
    print("RiskBench Annotation Data Prep")
    print("=" * 60)
    
    # Determine experiment directory
    if len(sys.argv) >= 2:
        selected_exp = Path(sys.argv[1])
        if not selected_exp.exists():
            print(f"Error: {selected_exp} does not exist")
            sys.exit(1)
        exp_type = 'human' if (selected_exp / 'c2_aware_human_val_output.jsonl').exists() else 'std'
    else:
        # Interactive mode
        folder_info = get_experiment_folders(experiments_dir)
        if not folder_info:
            print(f"No valid experiments found in {experiments_dir}")
            sys.exit(1)
        
        print("\nAvailable Experiments:")
        for i, (folder, _, ftype) in enumerate(folder_info[:10]):
            tag = "[HUMAN_VAL]" if ftype == 'human' else ""
            print(f"  {i+1}. {folder.name} {tag}")
        print("  0. Exit")
        
        try:
            sel = input("\nSelect (1-10): ").strip()
            if sel == '0':
                sys.exit(0)
            idx = int(sel) - 1
            if idx < 0 or idx >= len(folder_info):
                print("Invalid selection")
                sys.exit(1)
            selected_exp, _, exp_type = folder_info[idx]
        except (ValueError, KeyboardInterrupt):
            print("\nExiting.")
            sys.exit(0)
    
    # Determine sample count and min threshold
    n_samples = int(sys.argv[2]) if len(sys.argv) >= 3 else 15
    min_diff = float(sys.argv[3]) if len(sys.argv) >= 4 else 0.3
    
    print(f"\nExperiment: {selected_exp.name}")
    print(f"Samples per category: {n_samples}")
    print(f"Min score difference: {min_diff}")
    print(f"Output: {output_dir}")
    
    # Load data
    print("\nLoading data...")
    if exp_type == 'human':
        c2_file = selected_exp / 'c2_aware_human_val_output.jsonl'
        c4_file = selected_exp / 'c4_oneshot_human_val_output.jsonl'
    else:
        c2_file = selected_exp / 'c2_aware_output.jsonl'
        c4_file = selected_exp / 'c4_oneshot_output.jsonl'
    
    c2_data = load_data(c2_file)
    c4_data = load_data(c4_file)
    print(f"  Loaded {len(c2_data)} C2 + {len(c4_data)} C4 samples")
    
    # Generate C2 vs C4 comparison (high contrast only)
    print("\nGenerating pipeline comparison (high contrast)...")
    high_contrast_pairs = find_c2_vs_c4_samples(c2_data, c4_data, n_samples, min_diff=min_diff)
    
    pipeline_samples = []
    for i, pair in enumerate(high_contrast_pairs):
        s = format_sample_for_human(pair, 'c2_vs_c4', i)
        pipeline_samples.append(s)
    
    random.shuffle(pipeline_samples)
    for i, s in enumerate(pipeline_samples):
        s['sample_id'] = i
    
    save_samples(pipeline_samples, output_dir, "pipeline_comparison")
    print(f"  → {len(pipeline_samples)} high-contrast samples saved")
    
    # Generate before/after comparison (high improvement only)
    print("\nGenerating improvement comparison (high contrast)...")
    improvement_samples = []
    for data, name in [(c2_data, 'C2'), (c4_data, 'C4')]:
        results = find_before_after_samples(data, name, n_samples, min_improvement=min_diff)
        offset = len(improvement_samples)
        for i, s in enumerate(results['biggest_improvements']):
            formatted = format_sample_for_human({'condition': name, 'sample': s}, 'before_after', i + offset)
            improvement_samples.append(formatted)
    
    for i, s in enumerate(improvement_samples):
        s['sample_id'] = i
    
    save_samples(improvement_samples, output_dir, "improvement_comparison")
    print(f"  → {len(improvement_samples)} high-contrast samples saved")
    
    print("\n" + "=" * 60)
    print("Done! Start the UI with:")
    print("  cd scripts/annotation && python -m http.server 8000")
    print("=" * 60)


if __name__ == '__main__':
    main()
