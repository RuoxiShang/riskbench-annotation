# RiskBench Human Evaluation

A simple web tool to evaluate AI-generated risk scenarios.

## 🚀 How to Use

1. **Open the App**
   [https://ruoxishang.github.io/riskbench-annotation/](https://ruoxishang.github.io/riskbench-annotation/)

2. **Start Session**
   - Select your name to log in.
   - Choose a task (**Pipeline Comparison** or **Improvement Check**).

3. **Annotate**
   - Read the scenario.
   - Vote on which version is better.
   - Check if you agree with the AI judge.

4. **Submit**
   - When finished, click **"Download Annotations"**.
   - Send the downloaded `.json` file to Anna.

---

## 🔧 For Admin (Data Update)

To update the data displayed on the site:
1. Run `python3 prepare_ui_with_data.py` locally to generate new batches.
2. Commit and push the updated `data/*.json` files to GitHub.
3. GitHub Pages will automatically serve the new data.
