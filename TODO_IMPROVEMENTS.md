# RiskBench Annotation UI: Future Improvements

## 1. Data Persistence (High Priority)
**Current State**: Data is currently only stored in browser memory (and `localStorage` for simple progress). If the browser cache is cleared or the session is lost, annotations are gone until downloaded.
**Goal**: Implement robust saving to prevent data loss.
**Plan**:
- **Auto-Save to LocalStorage**: Ensure every single click/input is immediately serialized to `localStorage` so a refresh restores the exact state.
- **Backend Integration (Optional)**: If hosting allows (e.g., a simple Flask/FastAPI backend instead of static GitHub Pages), send POST requests to save to a server-side DB or JSON file.
- **"Download Backup" Button**: Always visible button to dump current progress to a local JSON file, just in case.

## 2. Streamlined Annotation Workflow (UI/UX)
**Current State**: Users must scroll down to the bottom form, read text, and click radio buttons for every sample.
**Goal**: "One-click" or "Keyboard-driven" efficiency.
**Plan**:
- **Click-to-Vote**: Make the "Version A" / "Version B" (or Before/After) columns themselves clickable. Clicking a column selects it as the "Better" one.
- **Conditional Logic**: 
  - If Human Choice == LLM Choice → Auto-advance (or show "Correct/Agree" and offer quick "Next").
  - If Human Choice != LLM Choice → *Then* reveal the "Why do you disagree?" text box (optional or required).
- **Keyboard Shortcuts**: Bind `Left Arrow` / `Right Arrow` to select A/B, and `Enter` to confirm/next.

## 3. Navigation & Skipping
**Current State**: Linear progression. Refreshing might lose place if not perfectly synced.
**Goal**: Flexible, non-linear navigation.
**Plan**:
- **Sidebar List**: Replace the simple progress bar with a clickable list of sample IDs (e.g., "1", "2", "3"...).
- **Status Indicators**: Color-code the list items (Gray = Unseen, Blue = Skipped/In-progress, Green = Completed).
- **Robust State Restoration**: On load, check `localStorage` and pre-fill all answered questions, allowing the user to jump between samples freely without losing unsaved inputs.

## 4. Task 3: Human Baseline / Blind Review
**Current State**: Users see the scenario, actions, and LLM scores/rationales all at once.
**Goal**: Get unbiased human judgment first.
**Plan**:
- **New Task Mode**: "Task 3: Blind Review" (or similar).
- **Workflow**:
  1.  Show ONLY Scenario + Actions (hide LLM scores/rationales).
  2.  User votes on better version.
  3.  *Reveal* LLM scores/rationales.
  4.  User marks agreement/disagreement.

## 5. Task Renaming
**Current State**: "Pipeline Comparison" and "Improvement Check".
**Goal**: Simplify terminology.
**Plan**:
- Rename "Pipeline Comparison" → **Task 1**
- Rename "Improvement Check" → **Task 2**
- (Future) "Blind Review" → **Task 3**
