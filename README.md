# RiskBench Human Evaluation

Interactive web interface for evaluating AI-generated risk assessment scenarios.

## 📝 Annotation Tasks

### Main Task: C2 vs C4 Comparison (20 samples)
**URL**: https://ruoxishang.github.io/riskbench-annotation/

Compare two versions of risk scenarios (blind A/B test) to evaluate:
- Which version has better quality
- Whether LLM judge scores are accurate
- Time estimate: ~15-20 minutes

### Calibration Task: Similar Scores (20 samples)
**URL**: https://ruoxishang.github.io/riskbench-annotation/calibration.html

Evaluate pairs where the LLM judge found similar quality scores.
- Validates LLM agreement
- Time estimate: ~15-20 minutes

## 🚀 How to Participate

1. Click one of the URLs above
2. Enter your name/ID at the top
3. Read each scenario carefully
4. Compare Version A and Version B
5. Answer the evaluation questions:
   - Which version is better?
   - Do you agree with LLM judge?
   - Optional comments
6. Click "Next" to proceed through all samples
7. **Important**: Download your annotations (JSON file) at the end
8. Send the JSON file to Anna

## 💾 Saving Your Work

- Progress is automatically saved in your browser
- You can close and return later (same browser)
- **Must download JSON when complete** to submit your annotations

## ⏰ Timeline

- **Deadline**: [To be announced]
- **Time commitment**: 15-20 minutes per task
- **Tasks**: You may be asked to complete one or both tasks

## 📊 What We're Evaluating

Each sample contains:
- **Scenario**: A risk assessment situation
- **Version A & B**: Two different generated action sets
  - Baseline action (medium risk)
  - Higher risk action
  - Lower risk action
- **LLM Scores**: Reference scores from automated judge

Your feedback helps us:
- Validate automated evaluation quality
- Compare different generation approaches
- Improve AI risk assessment systems

## ❓ Questions?

Contact: Anna Shang (annashang@[domain])

## 🛠️ Technical Details

- **Single-page application**: No installation needed
- **Works offline**: All data embedded
- **Browser compatibility**: Chrome, Firefox, Safari, Edge
- **Mobile-friendly**: Responsive design
- **Privacy**: No data collected until you download and send the JSON file

---

Built with ❤️ for RiskBench ablation study
