#!/usr/bin/env python3
"""
Assign annotators to samples to ensure balanced workload.

This script updates a samples JSON file (e.g., c6_samples.json or batch_*.json)
by adding an 'assigned_annotators' field to each sample.

Usage:
    python assign_tasks.py <samples.json> --overlap 2
    python assign_tasks.py data/c6_samples.json --overlap 3 --annotators data/annotators.json

"""

import json
import argparse
import random
from pathlib import Path
from itertools import cycle

def load_json(filepath):
    with open(filepath, 'r') as f:
        return json.load(f)

def save_json(data, filepath):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description="Assign annotators to samples")
    parser.add_argument("filepath", help="Path to samples JSON file")
    parser.add_argument("--annotators", default="data/annotators.json", help="Path to annotators list")
    parser.add_argument("--overlap", type=int, default=2, help="Number of annotators per sample")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for assignment")
    parser.add_argument("--shuffle-annotators", action="store_true", help="Shuffle annotators order before assignment")
    
    args = parser.parse_args()
    
    # Load inputs
    samples_path = Path(args.filepath)
    annotators_path = Path(args.filepath).parent / Path(args.annotators).name if not Path(args.annotators).exists() else Path(args.annotators)
    
    if not samples_path.exists():
        print(f"Error: Samples file {samples_path} not found")
        return
        
    if not annotators_path.exists():
        # Fallback to absolute path check or relative to script
        script_dir = Path(__file__).parent.absolute()
        annotators_path = script_dir / 'data' / 'annotators.json'
        
    if not annotators_path.exists():
        print(f"Error: Annotators file {annotators_path} not found")
        return

    print(f"Loading samples from {samples_path}")
    data = load_json(samples_path)
    
    print(f"Loading annotators from {annotators_path}")
    annotators = load_json(annotators_path)
    print(f"Found {len(annotators)} annotators: {', '.join(annotators)}")
    
    # Handle different data structures
    # Structure A: List of samples (batch_*.json)
    # Structure B: Dict with 'samples' key (c6_samples.json)
    if isinstance(data, list):
        samples = data
    elif isinstance(data, dict) and 'samples' in data:
        samples = data['samples']
    else:
        print("Error: Unknown data format. Expected list or dict with 'samples' key.")
        return

    # Randomization
    random.seed(args.seed)
    if args.shuffle_annotators:
        random.shuffle(annotators)
    
    # Assignment Logic
    # We want to distribute assignments as evenly as possible.
    # We iterate through samples and assign 'overlap' annotators to each.
    # We use a cycle iterator for annotators to ensure even distribution.
    
    annotator_cycle = cycle(annotators)
    
    # Track stats
    counts = {name: 0 for name in annotators}
    
    for sample in samples:
        assigned = []
        for _ in range(args.overlap):
            person = next(annotator_cycle)
            assigned.append(person)
            counts[person] += 1
        
        sample['assigned_annotators'] = assigned
        
    # Save back
    save_json(data, samples_path)
    
    print(f"\n✅ Assignments complete! Updated {len(samples)} samples.")
    print("\nWorkload distribution:")
    for name, count in counts.items():
        print(f"  {name}: {count} samples")
        
    print(f"\nSaved to: {samples_path}")

if __name__ == "__main__":
    main()
