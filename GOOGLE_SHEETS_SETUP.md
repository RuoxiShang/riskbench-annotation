# Google Sheets Sync Setup Guide

This guide explains how to set up real-time sync from the RiskBench annotation UI to a Google Sheet.

## Step 1: Create a Google Sheet

1. Go to [Google Sheets](https://sheets.google.com) and create a new spreadsheet
2. Name it something like "RiskBench Annotations"
3. Note the URL - you'll be linking the script to this spreadsheet

## Step 2: Create the Google Apps Script

1. In your Google Sheet, go to **Extensions** > **Apps Script**
2. Delete the default code and paste the contents of `google_apps_script.js` from this folder
3. Save the project (give it a name like "RiskBench Collector")

The script automatically:
- Creates columns dynamically based on incoming data
- Handles both GET and POST requests
- Uses locking to prevent race conditions
- Adds server timestamps

## Step 3: Deploy the Web App

1. Click **"Deploy"** > **"New deployment"**
2. Click the gear icon next to "Select type" and choose **"Web app"**
3. Configure:
   - **Description**: "RiskBench Annotation Sync"
   - **Execute as**: "Me" (your email)
   - **Who has access**: **"Anyone"** (important for cross-origin requests!)
4. Click **"Deploy"**
5. **Authorize** the app when prompted:
   - Click "Review Permissions"
   - Select your Google account
   - Click "Advanced" > "Go to [project name] (unsafe)"
   - Click "Allow"
6. **Copy the Web App URL** - it looks like:
   ```
   https://script.google.com/macros/s/AKfycby.../exec
   ```

## Step 4: Update the Annotation UI

Update the `GOOGLE_SCRIPT_URL` in `index.html` (around line 899):

```javascript
const GOOGLE_SCRIPT_URL = 'https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec';
```

## Step 5: Deploy to GitHub Pages

1. Push your changes to the GitHub repo
2. Go to repo Settings > Pages
3. Select the branch to deploy (e.g., `main`)
4. Your site will be available at: `https://ruoxishang.github.io/riskbench-annotation/`

## Step 6: Test

1. Open `https://ruoxishang.github.io/riskbench-annotation/`
2. Login and complete one annotation
3. Check your Google Sheet - you should see a new row!
4. The sidebar should show "● Cloud sync active" (green dot)

## Troubleshooting

### "No data appearing in sheet"
- Make sure the Web App is deployed with **"Anyone"** access
- Check the Apps Script execution log: **View > Executions**
- Make sure the URL ends with `/exec` not `/dev`

### "Authorization required"
- Re-deploy the web app after authorizing
- Make sure to click through all the "unsafe" warnings

### "Sync indicator shows 'Local only'"
- The `GOOGLE_SCRIPT_URL` hasn't been updated
- Make sure the URL doesn't contain placeholder text

### Data not appearing after working before
- Google Apps Script deployments can have delays
- Check if you need to create a "New deployment" (not "Manage deployments")

## Data Columns (Auto-Generated)

The script automatically creates columns based on the data sent. Expected columns:

| Column | Description |
|--------|-------------|
| `server_timestamp` | When the server received the request |
| `timestamp` | When the annotation was made (client time) |
| `session_id` | Unique session identifier for tracking |
| `annotator` | Name of the annotator |
| `sample_id` | Which sample was annotated |
| `comparison_type` | "pipeline" or "improvement" |
| `better_version` | User's selection (A/B/before/after/similar) |
| `comments` | Optional user comments |
| `ui_version` | Version of the annotation interface |

## Security Notes

- The Web App URL should be kept semi-private
- Anyone with the URL can submit data (by design, for easy annotator access)
- Data is append-only - users cannot read or modify existing data
- Consider creating a new deployment URL periodically if needed
