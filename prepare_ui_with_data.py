#!/usr/bin/env python3
"""
Process experiment results into annotation batches.

This script:
1. Scans the experiments/ directory for recent runs.
2. Allows the user to select a run.
3. Extracts relevant samples (biggest diffs, etc.) using logic from scripts/ablation.
4. Saves the processed batches to scripts/annotation/data/.

Usage:
    python prepare_ui_with_data.py
"""

import sys
import os
import json
from pathlib import Path
import datetime

# Add scripts/ablation to path so we can import the logic
current_dir = Path(__file__).parent.absolute()
ablation_dir = current_dir.parent / 'ablation'
sys.path.append(str(ablation_dir))

try:
    from sample_for_human_eval import (
        load_data, 
        find_c2_vs_c4_samples, 
        find_before_after_samples, 
        format_sample_for_human,
        save_samples
    )
except ImportError as e:
    print(f"Error importing from sample_for_human_eval.py: {e}")
    print(f"Please make sure {ablation_dir} exists and contains sample_for_human_eval.py")
    sys.exit(1)

def get_experiment_folders(experiments_dir):
    """List valid experiment folders sorted by date (newest first)."""
    exp_path = Path(experiments_dir)
    if not exp_path.exists():
        return []
    
    folders = []
    for p in exp_path.iterdir():
        if p.is_dir() and (p / 'c2_aware_output.jsonl').exists() and (p / 'c4_oneshot_output.jsonl').exists():
            # Try to parse timestamp from name (MMDD_HHMM...) or use mtime
            try:
                # Assuming format MMDD_HHMM...
                # We'll just use modification time for sorting reliability
                mtime = p.stat().st_mtime
                folders.append((p, mtime))
            except Exception:
                pass
                
    # Sort by mtime descending
    folders.sort(key=lambda x: x[1], reverse=True)
    return [f[0] for f in folders]

def main():
    print("="*60)
    print("RiskBench Annotation Data Processor")
    print("="*60)
    
    # 1. Find experiments
    experiments_dir = current_dir.parent.parent / 'experiments'
    print(f"Scanning {experiments_dir} for experiment runs...")
    
    folders = get_experiment_folders(experiments_dir)
    
    if not folders:
        print("No valid experiment folders found (must contain c2_aware_output.jsonl and c4_oneshot_output.jsonl)")
        sys.exit(1)
        
    # 2. Interactive Selection
    print("\nAvailable Experiments:")
    for i, folder in enumerate(folders[:10]):  # Show top 10
        # Format timestamp from folder name if possible
        name = folder.name
        print(f"  {i+1}. {name}")
        
    print("\n  0. Exit")
    
    try:
        selection = input("\nSelect an experiment (1-10): ").strip()
        if selection == '0':
            sys.exit(0)
        idx = int(selection) - 1
        if idx < 0 or idx >= len(folders):
            print("Invalid selection.")
            sys.exit(1)
            
        selected_exp = folders[idx]
    except ValueError:
        print("Invalid input.")
        sys.exit(1)
        
    print(f"\nSelected: {selected_exp.name}")
    
    # 3. Configuration
    try:
        n_samples = input("How many samples per category? (default: 15): ").strip()
        n_samples = int(n_samples) if n_samples else 15
    except ValueError:
        print("Invalid number, using default 15.")
        n_samples = 15

    # 4. Output Setup
    output_dir = current_dir / 'data'
    output_dir.mkdir(exist_ok=True)
    print(f"\nOutput directory: {output_dir}")
    
    # 5. Processing
    print("\nLoading data...")
    c2_data = load_data(selected_exp / 'c2_aware_output.jsonl')
    c4_data = load_data(selected_exp / 'c4_oneshot_output.jsonl')
    print(f"Loaded {len(c2_data)} C2 samples and {len(c4_data)} C4 samples.")
    
    # --- C2 vs C4 ---
    print("\nGenerating C2 vs C4 comparison batches...")
    c2_vs_c4 = find_c2_vs_c4_samples(c2_data, c4_data, n_samples)
    
    # Combine Diff and Similar into one list for "Pipeline Comparison" task
    # We shuffle them so the annotator doesn't know which is which type
    import random
    pipeline_samples = []
    
    # Add Biggest Diff samples
    for i, pair in enumerate(c2_vs_c4['biggest_differences']):
        s = format_sample_for_human(pair, 'c2_vs_c4', i)
        s['sub_task'] = 'difference' # Add metadata
        pipeline_samples.append(s)
        
    # Add Calibration samples
    # Offset IDs to avoid collision
    offset = len(pipeline_samples)
    for i, pair in enumerate(c2_vs_c4['most_similar']):
        s = format_sample_for_human(pair, 'c2_vs_c4', i + offset)
        s['sub_task'] = 'calibration'
        pipeline_samples.append(s)
    
    random.shuffle(pipeline_samples)
    
    # Re-index after shuffle
    for i, s in enumerate(pipeline_samples):
        s['sample_id'] = i
        
    pipeline_filename = "pipeline_comparison.json"
    # Note: save_samples adds .json extension
    save_samples(pipeline_samples, output_dir, "pipeline_comparison") 
    print(f"  -> Generated {pipeline_filename} (Combined Diff + Similar, n={len(pipeline_samples)})")

    
    # --- Before vs After ---
    print("\nGenerating Before/After batches...")
    improvement_samples = []
    
    for data, name in [(c2_data, 'C2'), (c4_data, 'C4')]:
        results = find_before_after_samples(data, name, n_samples)
        
        # Improvements
        # Offset IDs
        offset = len(improvement_samples)
        for i, s in enumerate(results['biggest_improvements']):
            formatted = format_sample_for_human({'condition': name, 'sample': s}, 'before_after', i + offset)
            improvement_samples.append(formatted)
            
    # Re-index
    for i, s in enumerate(improvement_samples):
        s['sample_id'] = i
        
    improvement_filename = "improvement_comparison.json"
    save_samples(improvement_samples, output_dir, "improvement_comparison")
    print(f"  -> Generated {improvement_filename} (Combined C2+C4 Improvements, n={len(improvement_samples)})")
    
    print("\n" + "="*60)
    print("Done! Data files updated in scripts/annotation/data/")
    print("The UI will now auto-load these files.")
    print("="*60)

if __name__ == '__main__':
    main()
