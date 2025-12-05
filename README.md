# RiskBench Human Evaluation

A simple web tool to evaluate AI-generated risk scenarios.

## 🚀 How to Use

1. **Open the App**
   [https://ruoxishang.github.io/riskbench-annotation/](https://ruoxishang.github.io/riskbench-annotation/)

2. **Start Session**
   - Select your name to log in.
   - Choose a task:
     - **Pipeline Comparison**: Compare C2 vs C4 pipeline outputs side-by-side
     - **Improvement Check**: Compare before/after refinement
     - **Score Review**: Review top and bottom scoring samples individually

3. **Annotate**
   - Read the scenario.
   - Vote on which version is better (for comparison tasks).
   - Add observations (for score review).

4. **Submit**
   - When finished, click **"Download Annotations"** or **"Download Observations"**.
   - Send the downloaded `.json` file to Anna.

---

## 🔧 For Admin (Data Update)

### Pipeline & Improvement Data
To update comparison data:
```bash
python3 prepare_data.py <experiment_dir>
```

### Score Review Data
To generate review data for top/bottom samples by score:
```bash
# From a C5 or other experiment output
python3 prepare_review_data.py <output.jsonl> --top 5 --bottom 5

# With custom output name
python3 prepare_review_data.py experiments/c5_obscure/output.jsonl --name c5_review
```

This creates `data/review_samples.json` (or custom name) containing:
- Metadata (total samples, overall average, score range)
- Top N samples with highest scores
- Bottom N samples with lowest scores

### Deployment
1. Commit and push the updated `data/*.json` files to GitHub.
2. GitHub Pages will automatically serve the new data.
