## 🚀 Hosting Guide for Annotation UI

This guide shows the **simplest ways** to share the annotation UI with your collaborators.

---

## Quick Start (3 Steps)

### 1. Prepare the HTML file with your data

```bash
cd scripts/ablation

# Create self-contained HTML with embedded data
python prepare_ui_with_data.py \
  ../../experiments/1119_1328_ablation_generation/human_eval_samples/c2_vs_c4_biggest_diff_n10.json \
  annotation_ui_ready.html
```

This creates a **single HTML file** with all data embedded.

### 2. Choose a hosting method (pick ONE)

- **Option A**: GitHub Pages (free, public)
- **Option B**: Python Simple Server (local network)
- **Option C**: File sharing (Dropbox, Google Drive)

### 3. Share the link with collaborators

---

## Hosting Options

### **Option A: GitHub Pages** (Recommended - Free & Easy)

✅ Free
✅ No setup
✅ Works from anywhere
✅ Permanent URL

**Steps:**

1. **Create a GitHub repository** (or use existing)
   ```bash
   # If you don't have one yet
   gh repo create riskbench-annotation --public
   # Or just use your existing riskbench repo
   ```

2. **Copy HTML file to a gh-pages branch**
   ```bash
   cd /Users/annashang/code/riskbench

   # Create gh-pages branch (first time only)
   git checkout --orphan gh-pages
   git rm -rf .

   # Copy your HTML file
   cp scripts/ablation/annotation_ui_ready.html index.html
   git add index.html
   git commit -m "Add annotation UI"
   git push origin gh-pages
   ```

3. **Enable GitHub Pages**
   - Go to your repo on GitHub
   - Settings → Pages
   - Source: Deploy from branch `gh-pages`
   - Save

4. **Get your URL**
   - Will be: `https://YOUR_USERNAME.github.io/REPO_NAME/`
   - Example: `https://annashang.github.io/riskbench/`

5. **Share the link!**
   - Send this URL to all 6 collaborators
   - They can access it from anywhere, anytime

---

### **Option B: Python Simple Server** (Local Network Only)

✅ Instant
✅ No GitHub needed
⚠️ Only works while your computer is running
⚠️ Collaborators must be on same network OR you need to expose port

**Steps:**

1. **Start server**
   ```bash
   cd /Users/annashang/code/riskbench/scripts/ablation
   python3 -m http.server 8000
   ```

2. **Find your IP address**
   ```bash
   # On Mac
   ifconfig | grep "inet " | grep -v 127.0.0.1
   ```
   Example output: `inet 192.168.1.100`

3. **Share URL with collaborators**
   - On same WiFi: `http://192.168.1.100:8000/annotation_ui_ready.html`
   - They open this in their browser

**To expose publicly** (if collaborators are remote):
```bash
# Install ngrok
brew install ngrok

# Expose local server
ngrok http 8000

# Copy the public URL (e.g., https://abc123.ngrok.io)
# Share: https://abc123.ngrok.io/annotation_ui_ready.html
```

---

### **Option C: File Sharing** (Simplest, No Server)

✅ Super simple
✅ Works offline
⚠️ Each person gets their own copy
⚠️ Need to collect files back manually

**Steps:**

1. **Share the HTML file directly**
   - Upload `annotation_ui_ready.html` to:
     - Google Drive
     - Dropbox
     - Email attachment
     - Slack/Discord

2. **Collaborators download and open**
   - Double-click the HTML file
   - Opens in their web browser
   - Everything works offline!

3. **Collect responses**
   - Each person clicks "Download Annotations"
   - They send you back the JSON file
   - You merge them manually or with a script

---

## Creating Multiple Annotation UIs

If you want different collaborators to annotate different sets:

```bash
# Person 1: C2 vs C4 biggest differences
python prepare_ui_with_data.py \
  ../../experiments/.../c2_vs_c4_biggest_diff_n15.json \
  ui_person1_c2_vs_c4.html

# Person 2: C2 before/after improvements
python prepare_ui_with_data.py \
  ../../experiments/.../c2_before_after_biggest_improvement_n15.json \
  ui_person2_c2_before_after.html

# Person 3: Similar pairs for calibration
python prepare_ui_with_data.py \
  ../../experiments/.../c2_vs_c4_most_similar_n15.json \
  ui_person3_calibration.html
```

Then host each HTML file separately or combine them.

---

## Collecting Annotations

After collaborators finish, they'll download JSON files named:
```
annotations_PersonName_1234567890.json
```

### Merge annotations (script):

```bash
# Create a merge script
cat > merge_annotations.py << 'EOF'
import json
import sys
from pathlib import Path

annotations_dir = Path(sys.argv[1])
merged = []

for json_file in annotations_dir.glob('annotations_*.json'):
    with open(json_file) as f:
        data = json.load(f)
        merged.extend(data['annotations'])
        print(f"Loaded {len(data['annotations'])} from {json_file.name}")

output = Path(sys.argv[2])
with open(output, 'w') as f:
    json.dump(merged, f, indent=2)

print(f"\n✓ Merged {len(merged)} total annotations")
print(f"✓ Saved to {output}")
EOF

# Run it
python merge_annotations.py ./collected_annotations/ merged_annotations.json
```

---

## Troubleshooting

### "Page not loading data"
- Check browser console (F12)
- Make sure HTML file was generated with `prepare_ui_with_data.py`
- Try opening in Chrome or Firefox

### "Can't download annotations"
- Browser may block downloads from local files
- Host on GitHub Pages instead
- Or allow downloads in browser settings

### "Collaborator can't access the link"
- **GitHub Pages**: Check repo is public
- **Local server**: Make sure they're on same network
- **ngrok**: URL expires after 2 hours on free plan (restart ngrok)

### "Different people annotating same samples"
- Good! You want inter-rater reliability
- Just make sure to track who annotated what
- The JSON includes annotator name and timestamp

---

## Best Practices

✅ **Do**:
- Test the URL yourself before sharing
- Give clear instructions to collaborators
- Set a deadline for annotations
- Have 2-3 people annotate the same samples (inter-rater reliability)

❌ **Don't**:
- Don't use file:// URLs (won't work properly)
- Don't edit HTML file manually after generating
- Don't assume collaborators know how to download JSON files (show them!)

---

## Example Email to Collaborators

```
Subject: RiskBench Annotation Task

Hi everyone,

Please help evaluate AI-generated risk scenarios by clicking this link:
https://annashang.github.io/riskbench/

Instructions:
1. Enter your name at the top
2. Read each scenario and compare the two versions
3. Answer the questions
4. Click through all samples
5. Download your annotations at the end
6. Send the JSON file back to me

Should take about 15-20 minutes for 15 samples.

Deadline: [DATE]

Questions? Let me know!

Thanks,
Anna
```

---

## My Recommendation

For **6 collaborators** working remotely:

1. Use **GitHub Pages** (Option A)
2. Create **1-2 HTML files** with different sample sets
3. Have **2-3 people annotate the same samples** for reliability
4. **Collect JSON files** via email or shared folder
5. **Merge using script** above

This is free, requires no ongoing maintenance, and works from anywhere!
