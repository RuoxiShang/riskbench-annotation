#!/usr/bin/env python3
"""
Prepare review data for score-based sample review or judge validation.

This script supports two modes:

1. Average Score Mode (default):
   - Selects top N and bottom N samples by average score
   - For general quality review

2. Judge Validation Mode:
   - Samples where ALL dimensions > threshold (verify judge not too lenient)
   - Samples where specific dimension <= threshold (verify judge accuracy per dimension)
   - For validating LLM judge accuracy with human annotation

Usage:
    # Average score mode (original behavior)
    python prepare_review_data.py <output_judged.jsonl>
    python prepare_review_data.py <output_judged.jsonl> --top 5 --bottom 5

    # Judge validation mode (NEW)
    python prepare_review_data.py <output_judged.jsonl> --mode judge_validation --threshold 3 --n 5

    # Custom output name
    python prepare_review_data.py <output_judged.jsonl> --name c5_validation

Output:
    data/review_samples.json (or custom name)
"""

import json
import re
import sys
import argparse
from pathlib import Path
from typing import Optional, Dict, List, Tuple


# =============================================================================
# SCORE PARSING (adapted from examine_output.py)
# =============================================================================

def parse_scores(judge_text: str) -> Dict[str, Optional[float]]:
    """Parse individual scores from judge output text.
    
    Handles both the new 4-dimension C5 rubric and older 6-dimension rubrics.
    Returns dict with dimension scores and average.
    """
    scores = {}
    
    if not judge_text or judge_text == 'N/A':
        return {'average': None}
    
    # Try to find named dimensions first (more robust)
    dimension_patterns = {
        'risk_factor_manipulation': r'Risk Factor Manipulation[:\s]*(\d+(?:\.\d+)?)/5',
        'risk_ordering': r'Risk Ordering[:\s]*(\d+(?:\.\d+)?)/5',
        'neutrality_subtlety': r'Neutrality[^:]*Subtlety[:\s]*(\d+(?:\.\d+)?)/5',
        'realistic_reasonable': r'Realistic[^:]*Reasonable[:\s]*(\d+(?:\.\d+)?)/5',
        # Legacy dimensions
        'utility_balance': r'Utility Balance[:\s]*(\d+(?:\.\d+)?)/5',
        'plausibility': r'Plausibility[:\s]*(\d+(?:\.\d+)?)/5',
        'differentiation': r'Differentiation[:\s]*(\d+(?:\.\d+)?)/5',
        'scenario_quality': r'Scenario Quality[:\s]*(\d+(?:\.\d+)?)/5',
    }
    
    for dim, pattern in dimension_patterns.items():
        match = re.search(pattern, judge_text, re.IGNORECASE)
        if match:
            scores[dim] = float(match.group(1))
    
    # Fallback: find all X/5 patterns in order
    if not scores:
        all_scores = re.findall(r'(\d)/5', judge_text)
        score_keys = ['risk_factor_manipulation', 'risk_ordering', 'neutrality_subtlety', 'realistic_reasonable']
        for i, score in enumerate(all_scores[:4]):
            if i < len(score_keys):
                scores[score_keys[i]] = int(score)
    
    # Calculate average of non-None scores
    valid_scores = [v for v in scores.values() if v is not None and isinstance(v, (int, float))]
    scores['average'] = sum(valid_scores) / len(valid_scores) if valid_scores else None
    
    return scores


def get_sample_average_score(sample: dict) -> float:
    """Get average score for a sample. Returns -1 if no valid scores."""
    # Try different possible field names for judge scores
    judge_data = (
        sample.get('cleaned_judge_scores') or
        sample.get('judge_scores') or
        sample.get('scores_after_refine')
    )

    if not judge_data:
        return -1

    # Handle new format: judge_scores is a dict
    if isinstance(judge_data, dict):
        # Calculate average from dimension scores
        dimensions = [
            'scenario_realism', 'action_a_realism', 'action_b_realism',
            'action_b_meaningful_risk', 'action_b_subtlety',
            'same_activity', 'risk_factor_manipulation'
        ]
        scores = [judge_data.get(d, 0) for d in dimensions if d in judge_data]
        return sum(scores) / len(scores) if scores else -1

    # Handle old format: judge_scores is text
    scores = parse_scores(judge_data)
    return scores['average'] if scores.get('average') is not None else -1


# =============================================================================
# CONTENT PARSING (for C5 pipeline output)
# =============================================================================

def parse_length_matched_content(content: str) -> Dict[str, str]:
    """Parse the final length-matched content into scenario and actions.
    
    Handles multiple formats:
    - New format with cut_prefix (scenario at start, no "Scenario:" label)
    - Old format with "Scenario:" label
    - Action A/Action B format
    - Original Action/Higher Risk Action format
    """
    result = {
        'scenario': '',
        'original_action': '',
        'higher_risk_action': ''
    }
    
    if not content:
        return result
    
    # Try to parse scenario - multiple approaches
    # First, check if "Scenario:" label exists
    scenario_match = re.search(
        r'Scenario:\s*\n(.+?)(?=\n\nAction [AB]:|\nAction [AB]:|\n\nOriginal Action:|\nOriginal Action:|$)', 
        content, re.DOTALL
    )
    if scenario_match:
        result['scenario'] = scenario_match.group(1).strip()
    else:
        # No "Scenario:" label - content starts directly with scenario text
        # (this happens when cut_prefix: "Scenario:" is used)
        # Scenario is everything before "Action A:" or "Original Action:"
        scenario_match = re.search(
            r'^(.+?)(?=\n\nAction [AB]:|\nAction [AB]:|\n\nOriginal Action:|\nOriginal Action:)', 
            content, re.DOTALL
        )
        if scenario_match:
            result['scenario'] = scenario_match.group(1).strip()
    
    # Try new A/B format first
    a_match = re.search(
        r'Action A:\s*\n(.+?)(?=\n\nAction B:|\nAction B:|$)', 
        content, re.DOTALL
    )
    b_match = re.search(
        r'Action B:\s*\n(.+?)$', 
        content, re.DOTALL
    )
    
    if a_match and b_match:
        result['original_action'] = a_match.group(1).strip()
        result['higher_risk_action'] = b_match.group(1).strip()
    else:
        # Fall back to old format
        orig_match = re.search(
            r'Original Action:\s*\n(.+?)(?=\n\nHigher Risk Action:|\nHigher Risk Action:|$)', 
            content, re.DOTALL
        )
        if orig_match:
            result['original_action'] = orig_match.group(1).strip()
        
        high_match = re.search(
            r'Higher Risk Action:\s*\n(.+?)$', 
            content, re.DOTALL
        )
        if high_match:
            result['higher_risk_action'] = high_match.group(1).strip()
    
    return result


def calculate_word_counts(sample: dict) -> Tuple[int, int]:
    """Calculate word counts for original and higher-risk actions."""
    # Try length-matched content first
    length_matched = sample.get('cleaned_length_matched', '')
    if length_matched:
        parsed = parse_length_matched_content(length_matched)
        original = parsed['original_action']
        high_risk = parsed['higher_risk_action']
    else:
        original = sample.get('cleaned_original_action', '')
        high_risk = sample.get('cleaned_high_risk_action', '')
    
    return len(original.split()), len(high_risk.split())


# =============================================================================
# SAMPLE SELECTION
# =============================================================================

def has_valid_content(sample: dict) -> bool:
    """Check if a sample has valid (non-empty) content.

    Filters out samples from failed generation runs that have empty scenarios.
    """
    # Try to get scenario from length-matched content
    length_matched = sample.get('cleaned_length_matched', '')
    if length_matched:
        parsed = parse_length_matched_content(length_matched)
        scenario = parsed['scenario']
    else:
        scenario = sample.get('cleaned_scenario', '')

    # Must have a non-empty scenario
    return bool(scenario and scenario.strip())


def get_samples_by_score(samples: List[dict], n_top: int = 5, n_bottom: int = 5) -> Tuple[List, List]:
    """Get the top and bottom samples by average score.

    Returns (top_samples, bottom_samples) where each is a list of (original_idx, sample, avg_score).
    """
    # Calculate scores for all samples
    scored = []
    for i, sample in enumerate(samples):
        # Skip samples with empty content
        if not has_valid_content(sample):
            continue
        avg = get_sample_average_score(sample)
        if avg >= 0:  # Only include samples with valid scores
            scored.append((i, sample, avg))
    
    # Sort by average score (descending)
    scored.sort(key=lambda x: x[2], reverse=True)
    
    top = scored[:n_top]
    bottom = scored[-n_bottom:] if len(scored) >= n_bottom else []
    bottom = list(reversed(bottom))  # Show worst first
    
    return top, bottom


def get_samples_for_judge_validation(samples: List[dict], low_threshold: int = 2, good_threshold: int = 3, n: int = 5):
    """Get samples for validating LLM judge accuracy.

    Sampling strategy:
    - All good: all dimensions > good_threshold (e.g., all 4-5), randomly sampled
    - Low per dimension: specific dimension <= low_threshold (e.g., 1-2), ranked by highest
      average of OTHER dimensions (best overall samples that fail on this one dimension)

    This ensures we get samples that are good overall but specifically weak on
    one dimension, making them ideal test cases for validating judge accuracy.

    Returns:
        all_good: list of (original_idx, sample) tuples
        low_by_dimension: dict mapping dimension -> list of (original_idx, sample, other_avg) tuples
    """
    import random

    # Define dimensions (from new C5 judge)
    dimensions = [
        'scenario_realism',
        'action_a_realism',
        'action_b_realism',
        'action_b_meaningful_risk',
        'action_b_subtlety',
        'same_activity',
        'risk_factor_manipulation'
    ]

    all_good = []
    low_by_dimension = {d: [] for d in dimensions}

    for i, sample in enumerate(samples):
        # Skip samples with empty content (failed generation)
        if not has_valid_content(sample):
            continue

        # Get judge_scores dict (new format, not text)
        judge_scores = sample.get('judge_scores', {})

        # Skip if no scores or wrong format
        if not judge_scores or isinstance(judge_scores, str):
            continue

        # Check if all dimensions > good_threshold (e.g., all 4-5)
        dim_scores = [judge_scores.get(d, 0) for d in dimensions]
        if all(score > good_threshold for score in dim_scores):
            all_good.append((i, sample))

        # Collect samples with low scores for each dimension
        # Also compute average of OTHER dimensions for ranking
        for dim in dimensions:
            dim_score = judge_scores.get(dim, 0)
            if dim_score <= low_threshold:
                # Calculate average of all OTHER dimensions
                other_scores = [judge_scores.get(d, 0) for d in dimensions if d != dim]
                other_avg = sum(other_scores) / len(other_scores) if other_scores else 0
                low_by_dimension[dim].append((i, sample, other_avg))

    # Sample n from all_good (random)
    all_good_sample = random.sample(all_good, min(n, len(all_good))) if all_good else []

    # For each dimension: sort by other_avg descending, take top n
    low_samples = {}
    for dim in dimensions:
        candidates = low_by_dimension[dim]
        # Sort by other_avg (3rd element) descending - best overall samples first
        candidates.sort(key=lambda x: x[2], reverse=True)
        # Take top n, keep the other_avg for formatting
        low_samples[dim] = [(idx, sample, other_avg) for idx, sample, other_avg in candidates[:n]]

    return all_good_sample, low_samples


# =============================================================================
# FORMAT FOR UI
# =============================================================================

def format_sample_for_review(original_idx: int, sample: dict, avg_score: float, rank_info: str) -> dict:
    """Format a sample for the review UI.
    
    Creates a flat structure optimized for single-sample display (not comparison).
    """
    # Parse scores - handle both dict and text formats
    judge_data = (
        sample.get('cleaned_judge_scores') or
        sample.get('judge_scores') or
        sample.get('scores_after_refine') or
        ''
    )

    if isinstance(judge_data, dict):
        # New format: already a dict, just use it
        scores = {k: v for k, v in judge_data.items() if k != 'recommendation'}
        scores['average'] = avg_score  # Use the provided average
    else:
        # Old format: text that needs parsing
        scores = parse_scores(judge_data)

    judge_text = judge_data if isinstance(judge_data, str) else ''  # For rationale field
    
    # Get final content (prefer length-matched)
    length_matched = sample.get('cleaned_length_matched', '')
    if length_matched:
        parsed = parse_length_matched_content(length_matched)
        scenario = parsed['scenario']
        original_action = parsed['original_action']
        higher_risk_action = parsed['higher_risk_action']
    else:
        scenario = sample.get('cleaned_scenario', '')
        original_action = sample.get('cleaned_original_action', '')
        higher_risk_action = sample.get('cleaned_high_risk_action', '')
    
    # Calculate word counts
    orig_words = len(original_action.split()) if original_action else 0
    high_words = len(higher_risk_action.split()) if higher_risk_action else 0
    
    return {
        'sample_id': original_idx,
        'rank_info': rank_info,  # e.g., "Top 1/5" or "Bottom 3/5"
        'average_score': round(avg_score, 2),
        
        # Metadata
        'activity_context': sample.get('activity_context', ''),
        'risk_factor': sample.get('risk_factor', ''),
        'risk_type': sample.get('risk_type', ''),
        
        # Content
        'scenario': scenario,
        'original_action': original_action,
        'higher_risk_action': higher_risk_action,
        
        # Word counts for length analysis
        'original_word_count': orig_words,
        'higher_risk_word_count': high_words,
        'length_ratio': round(high_words / orig_words, 2) if orig_words > 0 else None,
        
        # Individual scores
        'scores': {k: v for k, v in scores.items() if k != 'average' and v is not None},
        
        # Raw judge text for reference
        'judge_rationale': judge_text,
    }


def format_sample_for_judge_validation(original_idx: int, sample: dict, dimension_focus: str = None, other_avg: float = None) -> dict:
    """Format a sample for judge validation UI.

    Similar to format_sample_for_review but uses judge_scores dict format
    and emphasizes the dimension being validated.

    Args:
        other_avg: Average score of all OTHER dimensions (for low-dimension samples)
    """
    # Get judge_scores dict (new format)
    judge_scores = sample.get('judge_scores', {})

    # Get final content (prefer length-matched)
    length_matched = sample.get('cleaned_length_matched', '')
    if length_matched:
        parsed = parse_length_matched_content(length_matched)
        scenario = parsed['scenario']
        original_action = parsed['original_action']
        higher_risk_action = parsed['higher_risk_action']
    else:
        scenario = sample.get('cleaned_scenario', '')
        original_action = sample.get('cleaned_original_action', '')
        higher_risk_action = sample.get('cleaned_high_risk_action', '')

    # Calculate word counts
    orig_words = len(original_action.split()) if original_action else 0
    high_words = len(higher_risk_action.split()) if higher_risk_action else 0

    result = {
        'sample_id': original_idx,
        'dimension_focus': dimension_focus,  # Which dimension this is validating

        # Metadata
        'activity_context': sample.get('activity_context', ''),
        'risk_factor': sample.get('risk_factor', ''),
        'risk_type': sample.get('risk_type', ''),

        # Content
        'scenario': scenario,
        'original_action': original_action,
        'higher_risk_action': higher_risk_action,

        # Word counts
        'original_word_count': orig_words,
        'higher_risk_word_count': high_words,
        'length_ratio': round(high_words / orig_words, 2) if orig_words > 0 else None,

        # All dimension scores
        'llm_scores': {k: v for k, v in judge_scores.items() if k != 'recommendation'},

        # Average of OTHER dimensions (for low-dimension samples)
        'other_dimensions_avg': round(other_avg, 2) if other_avg is not None else None,

        # Recommendation
        'llm_recommendation': judge_scores.get('recommendation', 'N/A'),

        # Raw judge rationale if available
        'judge_rationale': sample.get('judge_raw', ''),
    }

    return result


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Prepare review data for top/bottom score analysis or judge validation"
    )
    parser.add_argument("filepath", help="Path to experiment output JSONL file")
    parser.add_argument("--mode", choices=['average', 'judge_validation'], default='average',
                       help="Sampling mode: 'average' for top/bottom by avg score, 'judge_validation' for validating judge accuracy")
    parser.add_argument("--top", type=int, default=5, help="Number of top-scoring samples (default: 5)")
    parser.add_argument("--bottom", type=int, default=5, help="Number of bottom-scoring samples (default: 5)")
    parser.add_argument("--threshold", type=int, default=2,
                       help="Low threshold: scores <= this are 'low' (default: 2, so 1-2 are low)")
    parser.add_argument("--good-threshold", type=int, default=3,
                       help="Good threshold: all dimensions must be > this for 'all good' (default: 3, so 4-5 are good)")
    parser.add_argument("--n", type=int, default=5, help="Sample size per dimension for judge_validation mode (default: 5)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling in judge_validation mode")
    parser.add_argument("--name", type=str, default="review_samples", help="Output filename (without .json)")
    args = parser.parse_args()
    
    current_dir = Path(__file__).parent.absolute()
    output_dir = current_dir / 'data'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("RiskBench Score Review Data Prep")
    print("=" * 60)
    
    # Load samples
    filepath = Path(args.filepath)
    if not filepath.exists():
        print(f"Error: {filepath} does not exist")
        sys.exit(1)
    
    print(f"\nLoading: {filepath}")
    samples = []
    with open(filepath) as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    
    print(f"Loaded {len(samples)} samples")

    # Branch based on mode
    if args.mode == 'judge_validation':
        # Judge validation mode
        import random
        random.seed(args.seed)

        print(f"\nMode: Judge Validation")
        print(f"Low threshold: scores <= {args.threshold} (1-{args.threshold}) are 'low'")
        print(f"Good threshold: scores > {args.good_threshold} ({args.good_threshold + 1}-5) are 'good'")
        print(f"Sample size: {args.n} per category")
        print(f"Random seed: {args.seed}")

        print(f"\nSampling...")
        all_good, low_by_dimension = get_samples_for_judge_validation(
            samples,
            low_threshold=args.threshold,
            good_threshold=args.good_threshold,
            n=args.n
        )
    else:
        # Average score mode (original)
        print(f"\nMode: Average Score")
        print(f"Selecting top {args.top} and bottom {args.bottom} by average score...")
        top_samples, bottom_samples = get_samples_by_score(samples, args.top, args.bottom)
    
    # Format for UI based on mode
    if args.mode == 'judge_validation':
        # Format all good samples
        formatted_all_good = []
        for orig_idx, sample in all_good:
            formatted = format_sample_for_judge_validation(orig_idx, sample, dimension_focus="All Good")
            formatted_all_good.append(formatted)

        # Format low samples by dimension
        formatted_by_dimension = {}
        dimension_labels = {
            'scenario_realism': 'Scenario Realism',
            'action_a_realism': 'Action A Realism',
            'action_b_realism': 'Action B Realism',
            'action_b_meaningful_risk': 'Meaningful Risk',
            'action_b_subtlety': 'Subtlety',
            'same_activity': 'Same Activity',
            'risk_factor_manipulation': 'Risk Factor Manipulation',
        }

        for dim, samples_list in low_by_dimension.items():
            formatted_list = []
            for orig_idx, sample, other_avg in samples_list:
                formatted = format_sample_for_judge_validation(
                    orig_idx, sample,
                    dimension_focus=dimension_labels.get(dim, dim),
                    other_avg=other_avg
                )
                formatted_list.append(formatted)
            formatted_by_dimension[dim] = formatted_list

        # Create output structure for judge validation
        output = {
            'metadata': {
                'mode': 'judge_validation',
                'source_file': str(filepath),
                'total_samples': len(samples),
                'low_threshold': args.threshold,
                'good_threshold': args.good_threshold,
                'sample_size': args.n,
                'seed': args.seed,
            },
            'all_good': formatted_all_good,
            'low_by_dimension': formatted_by_dimension,
        }

    else:
        # Average score mode (original formatting)
        formatted_top = []
        for rank, (orig_idx, sample, avg) in enumerate(top_samples, 1):
            formatted = format_sample_for_review(
                orig_idx, sample, avg,
                f"Top {rank}/{len(top_samples)}"
            )
            formatted_top.append(formatted)

        formatted_bottom = []
        for rank, (orig_idx, sample, avg) in enumerate(bottom_samples, 1):
            formatted = format_sample_for_review(
                orig_idx, sample, avg,
                f"Bottom {rank}/{len(bottom_samples)}"
            )
            formatted_bottom.append(formatted)

        # Calculate summary stats
        all_avgs = [get_sample_average_score(s) for s in samples]
        valid_avgs = [a for a in all_avgs if a >= 0]

        # Create output structure
        output = {
            'metadata': {
                'mode': 'average',
                'source_file': str(filepath),
                'total_samples': len(samples),
                'samples_with_scores': len(valid_avgs),
                'overall_average': round(sum(valid_avgs) / len(valid_avgs), 2) if valid_avgs else None,
                'min_score': round(min(valid_avgs), 2) if valid_avgs else None,
                'max_score': round(max(valid_avgs), 2) if valid_avgs else None,
            },
            'top_samples': formatted_top,
            'bottom_samples': formatted_bottom,
        }
    
    # Save
    output_path = output_dir / f'{args.name}.json'
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✓ Saved: {output_path}")

    # Print summary based on mode
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"Total samples: {len(samples)}")

    if args.mode == 'judge_validation':
        print(f"\n✅ All Good (all dimensions {args.good_threshold + 1}-5): {len(formatted_all_good)} samples")
        for s in formatted_all_good:
            scores = s['llm_scores']
            min_score = min(scores.values()) if scores else 0
            print(f"   #{s['sample_id']}: min={min_score}, {s['activity_context'] or s['risk_factor']}")

        print(f"\n❌ Low Scores by Dimension (1-{args.threshold}):")
        print(f"   (Sorted by highest avg of OTHER dimensions)")
        dimension_labels = {
            'scenario_realism': 'Scenario Realism',
            'action_a_realism': 'Action A Realism',
            'action_b_realism': 'Action B Realism',
            'action_b_meaningful_risk': 'Meaningful Risk',
            'action_b_subtlety': 'Subtlety',
            'same_activity': 'Same Activity',
            'risk_factor_manipulation': 'Risk Factor Manipulation',
        }

        for dim in ['scenario_realism', 'action_a_realism', 'action_b_realism',
                    'action_b_meaningful_risk', 'action_b_subtlety', 'same_activity',
                    'risk_factor_manipulation']:
            dim_samples = formatted_by_dimension.get(dim, [])
            print(f"  • {dimension_labels[dim]}: {len(dim_samples)} samples")
            for s in dim_samples[:3]:  # Show top 3 samples
                dim_score = s['llm_scores'].get(dim, '?')
                other_avg = s.get('other_dimensions_avg', '?')
                print(f"      #{s['sample_id']}: {dim}={dim_score}, other_avg={other_avg}")

        total_for_annotation = len(formatted_all_good) + sum(len(v) for v in formatted_by_dimension.values())
        print(f"\n📝 Total samples for annotation: {total_for_annotation}")
        print("\n" + "=" * 60)
        print("✅ Done! Use this data to validate LLM judge accuracy.")
        print("=" * 60)

    else:
        # Average mode summary (original)
        print(f"Samples with valid scores: {len(valid_avgs)}")
        if valid_avgs:
            print(f"Overall average: {sum(valid_avgs)/len(valid_avgs):.2f}/5")
            print(f"Score range: {min(valid_avgs):.2f} - {max(valid_avgs):.2f}")

        print(f"\n🏆 Top {len(formatted_top)} samples:")
        for s in formatted_top:
            print(f"   #{s['sample_id']}: {s['average_score']}/5 - {s['activity_context'] or s['risk_factor']}")

        print(f"\n📉 Bottom {len(formatted_bottom)} samples:")
        for s in formatted_bottom:
            print(f"   #{s['sample_id']}: {s['average_score']}/5 - {s['activity_context'] or s['risk_factor']}")

        print("\n" + "=" * 60)
        print("Done! Add 'Score Review' task in the UI to review these samples.")
        print("=" * 60)


if __name__ == '__main__':
    main()
