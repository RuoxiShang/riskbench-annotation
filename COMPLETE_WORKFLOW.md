# 🎯 Complete Ablation Study Workflow

End-to-end guide for RiskBench ablation experiments and human evaluation.

---

## Phase 1: Generate Matched Ablation Data

### Step 1: Configure experiments with seed
```yaml
# configs/ablations/riskbench_c2_aware.yaml
# configs/ablations/riskbench_c4_oneshot.yaml
seed: 42  # Ensures matched pairs!
num_samples: 50
```

### Step 2: Run experiments
```bash
cd scripts/ablation
python run_ablation.py 50  # Generate 50 matched pairs
```

**Output**: 
- `experiments/MMDD_HHMM_ablation_generation/c2_aware_output.jsonl`
- `experiments/MMDD_HHMM_ablation_generation/c4_oneshot_output.jsonl`
- 50 perfectly matched (risk_factor × domain × risk_type) pairs

---

## Phase 2: Sample for Human Evaluation

### Step 3: Extract interesting samples
```bash
cd scripts/ablation

# Extract 15 samples per category
python sample_for_human_eval.py \
  ../../experiments/1119_1328_ablation_generation \
  15 \
  ../../experiments/1119_1328_ablation_generation/human_eval
```

**Output**: 6 sample sets (JSON + Markdown)
- `c2_vs_c4_biggest_diff_n15.json` - Biggest score differences
- `c2_vs_c4_most_similar_n15.json` - Similar scores (calibration)
- `c2_before_after_biggest_improvement_n15.json` - C2 refinement helped
- `c4_before_after_biggest_improvement_n15.json` - C4 refinement helped
- Plus "biggest decline" sets

---

## Phase 3: Create Annotation Interfaces

### Step 4: Generate self-contained HTML files
```bash
# For C2 vs C4 comparison (blind A/B)
python prepare_ui_with_data.py \
  ../../experiments/1119_1328_ablation_generation/human_eval/c2_vs_c4_biggest_diff_n15.json \
  ui_c2_vs_c4_diff.html

# For calibration
python prepare_ui_with_data.py \
  ../../experiments/1119_1328_ablation_generation/human_eval/c2_vs_c4_most_similar_n15.json \
  ui_c2_vs_c4_similar.html

# For before/after comparison
python prepare_ui_with_data.py \
  ../../experiments/1119_1328_ablation_generation/human_eval/c2_before_after_biggest_improvement_n15.json \
  ui_c2_before_after.html
```

**Output**: Self-contained HTML files (each ~200KB)

---

## Phase 4: Host & Share

### Step 5: Host on GitHub Pages (recommended)

```bash
# Option A: New gh-pages branch
git checkout --orphan gh-pages
git rm -rf .
cp scripts/ablation/ui_*.html .
git add *.html
git commit -m "Add annotation UIs"
git push origin gh-pages

# Option B: Python server (local)
python3 -m http.server 8000
# Share: http://YOUR_IP:8000/ui_c2_vs_c4_diff.html
```

### Step 6: Send to collaborators

**Example email**:
```
Subject: RiskBench Annotation - 15 min task

Hi [Name],

Please annotate AI scenarios: https://yourusername.github.io/riskbench/ui_c2_vs_c4_diff.html

Instructions:
1. Enter your name
2. Compare versions A & B
3. Answer questions
4. Download JSON at end
5. Send me the file

Deadline: [DATE]
Time: ~15-20 minutes

Thanks!
```

---

## Phase 5: Collect & Analyze

### Step 7: Collect annotation files

Annotators will send you files like:
- `annotations_Person1_1234567890.json`
- `annotations_Person2_1234567891.json`
- etc.

### Step 8: Merge annotations

```python
import json
from pathlib import Path

merged = []
for f in Path('./collected/').glob('annotations_*.json'):
    with open(f) as file:
        data = json.load(file)
        merged.extend(data['annotations'])

with open('all_annotations.json', 'w') as f:
    json.dump(merged, f, indent=2)

print(f"Merged {len(merged)} annotations from {len(list(Path('./collected/').glob('annotations_*.json')))} people")
```

### Step 9: Analyze results

```python
from collections import Counter

annotations = json.load(open('all_annotations.json'))

# Human preferences
prefs = Counter(a['better_version'] for a in annotations)
print(f"Version A preferred: {prefs['A']}")
print(f"Version B preferred: {prefs['B']}")
print(f"Similar: {prefs['similar']}")

# LLM agreement
agree = Counter(a['llm_agreement'] for a in annotations)
print(f"\nLLM agreement: {agree}")

# By sample (inter-rater reliability)
from collections import defaultdict
by_sample = defaultdict(list)
for a in annotations:
    by_sample[a['sample_id']].append(a['better_version'])

agreements = []
for sample_id, votes in by_sample.items():
    most_common = Counter(votes).most_common(1)[0]
    agreement_rate = most_common[1] / len(votes)
    agreements.append(agreement_rate)

print(f"\nMean inter-rater agreement: {sum(agreements)/len(agreements):.1%}")
```

---

## Expected Timeline

| Phase | Time | Who |
|-------|------|-----|
| 1. Generate data | 2-4 hours | You (runs automatically) |
| 2. Sample extraction | 5 minutes | You |
| 3. Create UIs | 2 minutes | You |
| 4. Setup hosting | 10 minutes | You |
| 5. Annotation | 15-20 min each | 6 collaborators |
| 6. Collection | 1 day | Wait for responses |
| 7. Analysis | 30 minutes | You |

**Total**: ~2 days with automation

---

## File Structure

```
scripts/ablation/
├── run_ablation.py              # Run experiments
├── sample_for_human_eval.py     # Extract samples
├── annotation_ui.html           # UI template
├── prepare_ui_with_data.py      # Embed data in UI
├── COMPLETE_WORKFLOW.md         # This file
├── README_SAMPLING.md           # Sampling details
├── README_ANNOTATION.md         # UI details
└── HOSTING_GUIDE.md             # Hosting options

experiments/MMDD_HHMM_ablation_generation/
├── c2_aware_output.jsonl        # Raw C2 results
├── c4_oneshot_output.jsonl      # Raw C4 results
├── analysis_results.txt         # Quantitative analysis
├── score_heatmap.png            # Visual comparison
└── human_eval_samples/          # Extracted samples
    ├── c2_vs_c4_biggest_diff_n15.json
    ├── c2_vs_c4_most_similar_n15.json
    └── ...
```

---

## Key Decisions

### How many samples? (n)
- **n=10-15**: Good for quick validation
- **n=20-30**: More robust statistical power
- **n=50**: Full coverage (use all matched pairs)

### How many annotators?
- **2-3 per sample**: Measure inter-rater reliability
- **6 total**: Can cover different sample sets or overlap

### Which samples to prioritize?
1. **Biggest differences** - Test if LLM caught real quality gaps
2. **Similar scores** - Calibration check
3. **Before/after improvements** - Validate refinement impact

---

## Success Metrics

✅ **LLM Judge Validated** if:
- Human preferences correlate with LLM score differences
- >70% agreement on "similar" samples
- Humans don't catch obvious errors LLM missed

✅ **Refinement Helpful** if:
- Humans prefer "after" versions >60% of time
- LLM improvement scores align with human preference

✅ **C2 vs C4 Distinguishable** if:
- Humans can identify quality differences
- Agreement with LLM on which is better >65%

---

## Troubleshooting

**Problem**: Samples don't match between C2 and C4
**Solution**: Check `seed: 42` is set in both configs

**Problem**: UI not loading data
**Solution**: Use `prepare_ui_with_data.py`, not raw `annotation_ui.html`

**Problem**: Can't collect annotations
**Solution**: Use GitHub Pages or Python server, not file:// URLs

**Problem**: Low inter-rater agreement
**Solution**: Normal! Capture in "unsure" category, focus on clear cases

---

## Next Steps After Analysis

Based on results:
1. **If LLM judge validated** → Use for automated eval at scale
2. **If C2 > C4** → Deploy C2 pipeline
3. **If refinement helps** → Keep review/refine steps
4. **If issues found** → Iterate on prompts, re-run with fixes

---

**Questions?** See individual README files in `scripts/ablation/`
