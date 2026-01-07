#!/usr/bin/env python3
"""
Review annotations from CSV alongside the actual scenario content.

Usage:
    python review_annotations.py                    # Review all annotations
    python review_annotations.py --annotator Anna  # Filter by annotator
    python review_annotations.py --sample 5        # Show specific sample
"""

import csv
import json
import argparse
from pathlib import Path


def load_annotations(csv_path: Path) -> list:
    """Load annotations from CSV."""
    annotations = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            annotations.append(row)
    return annotations


def load_samples(json_path: Path) -> dict:
    """Load samples from JSON, indexed by sample_id."""
    with open(json_path) as f:
        data = json.load(f)
    return {s['sample_id']: s for s in data.get('samples', [])}


def print_divider(char='─', width=80):
    print(char * width)


def print_annotation(annotation: dict, sample: dict):
    """Print a single annotation with its sample content."""
    
    print_divider('═')
    print(f"📋 SAMPLE #{annotation.get('sample_id', '?')}  |  Annotator: {annotation.get('annotator', '?')}")
    print_divider('─')
    
    # Metadata
    print(f"🏷️  Activity: {sample.get('activity_context', 'N/A')}")
    print(f"    Harm Type: {sample.get('risk_type', 'N/A')}")
    print(f"    Risk Mechanism: {sample.get('risk_factor', 'N/A')}")
    print()
    
    # Scenario
    print("📖 SCENARIO:")
    scenario = sample.get('scenario', 'N/A')
    # Clean up any leading asterisks
    scenario = scenario.lstrip('* \n')
    print(f"   {scenario}")
    print()
    
    # Action
    print("🎯 ACTION:")
    action = sample.get('action', 'N/A')
    print(f"   {action}")
    print()
    
    # Risk (intended)
    print("⚠️  INTENDED RISK:")
    risk = sample.get('risk_description', 'N/A')
    print(f"   {risk}")
    print()
    
    # Annotation ratings
    print_divider('─')
    print("📊 ANNOTATION:")
    
    consequence = annotation.get('consequence', 'N/A')
    probability = annotation.get('probability', 'N/A')
    verdict = annotation.get('verdict', 'N/A')
    
    # Color-code verdict
    verdict_display = verdict.upper()
    if verdict == 'keep':
        verdict_display = f"✅ {verdict_display}"
    elif verdict == 'discard':
        verdict_display = f"❌ {verdict_display}"
    else:
        verdict_display = f"⚠️  {verdict_display}"
    
    print(f"   Consequence: {consequence.upper() if consequence else 'N/A'}")
    print(f"   Probability: {probability.upper() if probability else 'N/A'}")
    print(f"   Verdict: {verdict_display}")
    
    harm_correct = annotation.get('harm_type_correct', 'N/A')
    mechanism_correct = annotation.get('risk_mechanism_correct', 'N/A')
    print(f"   Harm Type Correct: {'✓' if harm_correct == 'TRUE' else '✗' if harm_correct == 'FALSE' else harm_correct}")
    print(f"   Risk Mechanism Correct: {'✓' if mechanism_correct == 'TRUE' else '✗' if mechanism_correct == 'FALSE' else mechanism_correct}")
    
    # Notes
    notes = annotation.get('notes', '').strip()
    if notes:
        print()
        print("💬 NOTES:")
        # Wrap notes nicely
        for line in notes.split('\n'):
            print(f"   {line.strip()}")
    
    print()


def main():
    parser = argparse.ArgumentParser(description="Review annotations with scenario content")
    parser.add_argument("--csv", type=str, default="output/riskbench-annotation - All.csv",
                        help="Path to annotations CSV")
    parser.add_argument("--samples", type=str, default="data/c6_samples.json",
                        help="Path to samples JSON")
    parser.add_argument("--annotator", type=str, help="Filter by annotator name")
    parser.add_argument("--sample", type=int, help="Show specific sample ID only")
    parser.add_argument("--verdict", type=str, choices=['keep', 'borderline', 'discard'],
                        help="Filter by verdict")
    args = parser.parse_args()
    
    # Resolve paths relative to script location
    script_dir = Path(__file__).parent
    csv_path = script_dir / args.csv
    samples_path = script_dir / args.samples
    
    if not csv_path.exists():
        print(f"❌ CSV not found: {csv_path}")
        return
    
    if not samples_path.exists():
        print(f"❌ Samples JSON not found: {samples_path}")
        return
    
    # Load data
    annotations = load_annotations(csv_path)
    samples = load_samples(samples_path)
    
    # Apply filters
    if args.annotator:
        annotations = [a for a in annotations if a.get('annotator') == args.annotator]
    
    if args.sample is not None:
        annotations = [a for a in annotations if a.get('sample_id') == str(args.sample)]
    
    if args.verdict:
        annotations = [a for a in annotations if a.get('verdict') == args.verdict]
    
    if not annotations:
        print("No annotations found matching the filters.")
        return
    
    # Print header
    print()
    print(f"Found {len(annotations)} annotation(s)")
    if args.annotator:
        print(f"Filtered by annotator: {args.annotator}")
    if args.sample is not None:
        print(f"Filtered by sample: {args.sample}")
    if args.verdict:
        print(f"Filtered by verdict: {args.verdict}")
    print()
    
    # Print each annotation
    for annotation in annotations:
        sample_id = int(annotation.get('sample_id', -1))
        sample = samples.get(sample_id, {})
        
        if not sample:
            print(f"⚠️  Sample {sample_id} not found in samples JSON")
            continue
        
        print_annotation(annotation, sample)
    
    # Summary
    print_divider('═')
    print("📈 SUMMARY")
    print_divider('─')
    
    verdicts = {}
    annotators = {}
    for a in annotations:
        v = a.get('verdict', 'unknown')
        verdicts[v] = verdicts.get(v, 0) + 1
        ann = a.get('annotator', 'unknown')
        annotators[ann] = annotators.get(ann, 0) + 1
    
    print("By Verdict:")
    for v, count in sorted(verdicts.items()):
        icon = '✅' if v == 'keep' else '❌' if v == 'discard' else '⚠️'
        print(f"   {icon} {v}: {count}")
    
    print("By Annotator:")
    for ann, count in sorted(annotators.items()):
        print(f"   {ann}: {count}")
    
    print()


if __name__ == '__main__':
    main()
