# RiskBench Human Evaluation

A simple, local web tool to evaluate AI-generated risk scenarios.

## 🚀 Quick Start

1. **Start the tool**
   Inside this directory (`scripts/annotation/`), run:
   ```bash
   python3 -m http.server 8000
   ```

2. **Open in Browser**
   Go to: [http://localhost:8000](http://localhost:8000)

3. **Annotate**
   - **Login**: Select your name from the list.
   - **Task 1 (Pipeline Comparison)**: Choose which AI model is better (A vs B).
   - **Task 2 (Improvement Check)**: Judge if the refinement actually improved the output.

4. **Submit**
   - When finished, click **"Download Annotations"**.
   - Send the downloaded JSON file to the project lead.

---

## 🛠️ For Developers

### Generating New Data
To generate fresh samples from the latest experiments:
```bash
# Run the interactive data processor
python3 prepare_ui_with_data.py
```
This will scan the `experiments/` folder and update the JSON files in `data/`.

### Adding Annotators
Edit `data/annotators.json` to add or remove names from the login dropdown.
