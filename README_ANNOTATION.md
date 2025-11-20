# 🎯 RiskBench Annotation System

Simple, self-contained web-based annotation system for human evaluation of AI-generated risk scenarios.

---

## 📁 Files

| File | Purpose |
|------|---------|
| `annotation_ui.html` | Template for annotation interface |
| `prepare_ui_with_data.py` | Script to embed data into HTML |
| `HOSTING_GUIDE.md` | Instructions for sharing with collaborators |
| `README_ANNOTATION.md` | This file |

---

## 🚀 Quick Start (3 Commands)

```bash
# 1. Generate samples to annotate (if not done yet)
python sample_for_human_eval.py \
  ../../experiments/1119_1328_ablation_generation \
  15 \
  ../../experiments/1119_1328_ablation_generation/human_eval

# 2. Create annotation UI with embedded data
python prepare_ui_with_data.py \
  ../../experiments/1119_1328_ablation_generation/human_eval/c2_vs_c4_biggest_diff_n15.json \
  annotation_ui_ready.html

# 3. Share with collaborators (see HOSTING_GUIDE.md)
# Option 1: GitHub Pages (recommended)
# Option 2: Python server: python3 -m http.server 8000
# Option 3: Send HTML file directly
```

---

## 🎨 UI Features

### ✅ KISS Design Principles
- **Single-file HTML** - No dependencies, no build step
- **Embedded data** - Everything in one file
- **Works offline** - No server required for basic use
- **Mobile-friendly** - Responsive design
- **Auto-save progress** - Annotations stored as you go
- **Download results** - Export JSON at the end

### What Annotators See

1. **Scenario** - The risk assessment scenario
2. **Version A & B** - Two versions of actions (blind comparison)
3. **LLM Scores** - Judge's scores for reference
4. **Evaluation Form** - Simple questions:
   - Which version is better?
   - Do you agree with LLM judge?
   - Comments (optional)
5. **Progress Bar** - Know where they are
6. **Navigation** - Previous/Next buttons

### What You Get Back

JSON file with:
```json
{
  "annotator": "PersonName",
  "completed_at": "2025-11-19T...",
  "total_samples": 15,
  "annotations": [
    {
      "annotator": "PersonName",
      "sample_id": 0,
      "comparison_type": "C2 vs C4 (after refinement)",
      "timestamp": "2025-11-19T...",
      "better_version": "A",
      "llm_agreement": "yes",
      "comments": "..."
    },
    ...
  ]
}
```

---

## 📊 Recommended Workflow

### For 6 Collaborators × 15 Samples Each

**Goal**: Validate LLM judge and compare C2 vs C4

**Setup**:
```bash
# Generate samples
python sample_for_human_eval.py \
  ../../experiments/1119_1328_ablation_generation \
  15 \
  ../../experiments/1119_1328_ablation_generation/human_eval

# Create 2 different UIs
python prepare_ui_with_data.py \
  human_eval/c2_vs_c4_biggest_diff_n15.json \
  ui_set1_differences.html

python prepare_ui_with_data.py \
  human_eval/c2_vs_c4_most_similar_n15.json \
  ui_set2_calibration.html
```

**Distribution**:
- **Persons 1-3**: Annotate `ui_set1_differences.html` (biggest differences)
- **Persons 4-6**: Annotate `ui_set2_calibration.html` (similar pairs)

**Why?**:
- Set 1 tests: Can humans detect quality differences LLM found?
- Set 2 tests: Do humans agree when LLM says they're similar?
- 3 people per set → Inter-rater reliability

---

## 🔧 Customization

### Change Questions

Edit `annotation_ui.html` and modify the `renderEvaluationForm()` function:

```javascript
function renderEvaluationForm() {
    return `
        <div class="evaluation-form">
            <h3>Your Evaluation</h3>

            <!-- Add your custom questions here -->
            <div class="question">
                <div class="question-text">Your custom question?</div>
                <div class="radio-group">
                    <!-- Radio options -->
                </div>
            </div>
        </div>
    `;
}
```

### Add Rating Scale

Replace radio buttons with a 1-5 scale:

```javascript
<div class="question">
    <div class="question-text">Rate overall quality (1-5):</div>
    <input type="range" min="1" max="5" step="1"
           name="quality_rating" class="rating-slider">
</div>
```

### Change Colors/Styling

All CSS is in the `<style>` block at the top of `annotation_ui.html`.

---

## 📈 Analyzing Results

### Merge Multiple Annotators

```python
import json
from pathlib import Path

merged = []
for json_file in Path('./collected/').glob('annotations_*.json'):
    with open(json_file) as f:
        data = json.load(f)
        merged.extend(data['annotations'])

with open('merged_annotations.json', 'w') as f:
    json.dump(merged, f, indent=2)
```

### Compute Inter-Rater Agreement

```python
from collections import defaultdict

# Group by sample_id
by_sample = defaultdict(list)
for ann in merged:
    by_sample[ann['sample_id']].append(ann['better_version'])

# Compute agreement
for sample_id, votes in by_sample.items():
    agreement = len([v for v in votes if v == votes[0]]) / len(votes)
    print(f"Sample {sample_id}: {agreement:.0%} agreement")
```

### Compare Human vs LLM

```python
# Check if humans agree with LLM score rankings
for ann in merged:
    human_prefers = ann['better_version']  # 'A' or 'B'
    llm_agrees = ann['llm_agreement']      # 'yes', 'partial', 'no'

    # Your analysis here
```

---

## ⚠️ Common Issues

### "Can't download JSON file"
- Browser security blocks local file downloads
- **Fix**: Host on GitHub Pages or use Python server

### "Data not loading"
- Forgot to run `prepare_ui_with_data.py`
- **Fix**: Don't use `annotation_ui.html` directly, use the generated file

### "Annotations lost on refresh"
- Browser cleared localStorage
- **Fix**: Tell annotators to download JSON after each session

### "Mobile display issues"
- Complex scenarios may overflow
- **Fix**: CSS is responsive, but test on actual devices

---

## 💡 Tips

✅ **Do**:
- Test yourself before sending to others
- Include clear deadline in instructions
- Have 2-3 people annotate same samples
- Save intermediate results
- Give annotators a preview sample to practice

❌ **Don't**:
- Don't edit HTML manually after generating
- Don't use same filename for different sample sets
- Don't forget to collect JSON files back!

---

## 🎓 Example Instructions for Annotators

> **Subject**: RiskBench Annotation Task - 15 minutes
>
> Hi [Name],
>
> Please help evaluate AI-generated scenarios by clicking this link:
> **[YOUR_URL_HERE]**
>
> **What to do**:
> 1. Enter your name at the top (e.g., "Anna" or "Reviewer1")
> 2. Read each scenario
> 3. Compare Version A and Version B
> 4. Answer the 2-3 questions
> 5. Click "Next" until done
> 6. Click "Download Annotations" at the end
> 7. **Send me the downloaded JSON file**
>
> **Time**: ~15-20 minutes for 15 samples
>
> **Deadline**: [DATE]
>
> **Questions?** Reply to this email
>
> Thank you! 🙏

---

## 📚 See Also

- `HOSTING_GUIDE.md` - How to share the UI
- `README_SAMPLING.md` - How to generate samples
- `sample_for_human_eval.py` - Sample generation script

---

## 🤝 Contributing

To improve the annotation UI:

1. Edit `annotation_ui.html` template
2. Test changes locally
3. Document new features here
4. Share improvements!

---

**Questions?** Check `HOSTING_GUIDE.md` or ask Anna.
