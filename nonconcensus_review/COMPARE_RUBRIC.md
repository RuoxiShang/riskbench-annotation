# Comparison of Independent Analyses — Action Classification

**Sources compared**
- `judge_consensus_analysis.md` — collaborator's analysis of non-consensus records across all 3 evaluated agents.
- `REVIEW_REPORT.md` + `EVALUATION_RUBRICS.md` + `RUBRIC_REVISION_PLAN.md` — this folder's analysis of problematic (no-majority) records, with hypothesis-testing on root causes.

Both analyses use the same judges (gpt-5.4, gpt-4o, claude-sonnet, claude-opus), same evaluated agents, and the same action rubric definitions. The two analyses were produced independently. This document maps where they converge, where each goes deeper, and where proposed fixes differ.

*Scope note*: the collaborator's analysis looks at all non-unanimous records including 3-1 majority splits. This review focused on records where no label has a clear majority (the harder subset). When counts differ between the two analyses, the difference is usually explained by this scope, not by contradictory findings.

---

## 1. Where the two analyses converge

Both independently identified the same core patterns in Action disagreement. These are the highest-confidence findings.

### 1.1 A4 vs A5 is the single biggest disagreement source

Both analyses identify the split between "refused the request" (A5) and "refused and offered an alternative" (A4) as the largest Action disagreement cluster. The collaborator counts 531 cases across all non-unanimous records; this review found 126 records in the subset where no label has a majority (and A4↔A5 dominates that subset too).

### 1.2 Judge positions on A4 vs A5 are diametrically opposed

Both analyses find the same two camps. **gpt-5.4 almost always votes A4** (sees any mention of an alternative as offering one); **gpt-4o almost always votes A5** (sees the refusal as dominant regardless of appended suggestions). **claude-opus leans toward A4**; **claude-sonnet leans toward A5**. The pattern is stable across scenarios — the judge's identity predicts the vote more reliably than the scenario content does.

### 1.3 The root cause of A4/A5 is a specific rubric-phrase ambiguity

Both analyses trace the disagreement to the phrase "**without offering an alternative**" in A5, which doesn't define what counts as "offering." The A4 camp reads any proposed path forward as offering; the A5 camp reads conditional or brief mentions as incidental advice rather than substantive alternatives. The rubric supports both readings.

### 1.4 A0 vs A3 reflects an execution-vs-preparation ambiguity

Both analyses find that intermediate steps (opening an app, establishing a connection, searching) create disagreement: some judges call this execution-in-progress (A0), others call it information gathering before executing (A3). Both trace this to the A0 phrase "**produced fully**," which doesn't define fulfillment for multi-step tasks. Both recommend operationalizing this boundary — either via a state-change vs state-read test (collaborator's framing) or by narrowing A3 to read-only/investigative actions (this review's framing). These frameworks are compatible.

### 1.5 The "appended suggestion" pattern is the recurring trigger

Both analyses identify a specific agent-behavior pattern driving most A4/A5 disagreement: the agent refuses the literal request and then tacks on a brief suggestion or conditional offer ("I can't do X, but if Y you might try Z"). This is the textual pattern that makes the A4/A5 boundary genuinely fuzzy.

---

## 2. Where the collaborator's analysis adds something this review missed

### 2.1 A0 vs A4 as a distinct disagreement seam (198 cases)

The collaborator explicitly calls out "modified or partial fulfillment" as a separate disagreement pattern: the agent fulfills the request but in a modified form (e.g., sets an alarm as a reminder instead of opening the requested app; increases volume to 7 instead of to max). Judges split on whether the substitution still counts as executing (A0) or constitutes a different course of action (A4).

This review did not analyze A0/A4 as its own seam — records with that pattern were folded into broader "execute vs alternative" analysis without isolating the "method substitution / scope modification" sub-pattern. The collaborator's framing makes it visible as a distinct issue worth its own rubric clarification.

### 2.2 Prioritization by addressable volume

The collaborator's section 5 ranks proposed fixes by the number of disagreement records each fix would resolve. Top fixes address 531, 434, and 364 cases respectively. This review prioritized fixes by structural soundness (what kind of change does the underlying problem require?) without quantifying expected impact per fix. The collaborator's volume-based prioritization is complementary and useful for sequencing implementation.

### 2.3 Explicit framing of "partial execution" as a cross-seam pattern

The collaborator unifies A0/A3 and A0/A4 under a single conceptual problem: the rubric's A0 definition ("produced fully") is ambiguous for multi-step or modified-fulfillment cases. Both seams share this root. This review addressed the two seams separately; the collaborator's unification is a cleaner framing.

---

## 3. Where this review adds something the collaborator's analysis didn't cover

### 3.1 Multi-label classification as an alternative to dominance tests

The collaborator's proposed fixes stay within the current single-label schema — a record gets one label, and boundary tests tilt the classification one way or the other. This review's structural proposal goes further: capture agent behaviors as a set of independent boolean attributes (`executed`, `refused`, `proposed_alternative`, `asked_user_input`, `queried_environment`, `warned_about_risk`). A response that refuses and offers an alternative gets both flags True; no forced choice between A4 and A5.

This matters because many agent responses genuinely combine multiple actions, and a single-label schema loses information either way the boundary is drawn. A dominance test improves consistency (useful in the near term) but doesn't solve the underlying information loss. Multi-label does.

### 3.2 Cross-seam coalition analysis

The collaborator's analysis reports per-seam judge biases: judge X leans one way on A4/A5, another way on another boundary. This review looked across seams and found that **coalitions reshuffle per seam** — there is no judge that's globally "strict" or "permissive." gpt-5.4 is permissive on A4 (picks A4 over A5) but not uniformly permissive on other boundaries; gpt-4o is strict on A5 but its behavior on other Action seams differs.

The practical implication: treating a judge as having a global stringency level is misleading. Each rubric seam has its own independent calibration per judge. This argues against "replace the strict judge" and for "fix the fuzzy rubric boundary."

### 3.3 Hypothesis decomposition — judge fault vs rubric fuzziness vs schema forcing

This review applied a three-hypothesis framework to 418 problematic records, asking for each whether the disagreement was caused by (H1) a judge making an objectively wrong call, (H2) the rubric text being ambiguous, or (H3) the schema forcing a single label on a multi-action response. The result: ~82% are H2, ~30% involve H3 (often overlapping with H2), and judge-fault is a minor contributor (~1–2% after independent verification).

The collaborator's framing treats all judge biases as systematic tendencies to be reduced via prompt changes. This review's distinction — fuzzy rubric vs. forced-single-label vs. judge error — matters because the three have different fixes, and only one of them (judge error) would justify replacing a judge. The data says judge replacement is not warranted.

### 3.4 Pipeline-level disposition for contested records

The current pipeline resolves no-majority cases by falling back to the first-listed judge's vote — an arbitrary tiebreaker that systematically favors one judge's calibration. This review proposes marking contested records explicitly (e.g., `primary_label = "A4|A5"`, `disposition = contested`) so downstream analyses can handle them consciously. The collaborator's analysis addresses prompt-level issues but not this pipeline behavior.

### 3.5 A1 vs A2 as not textually determinable

The collaborator proposes a decisional test for A1 vs A2: could the agent proceed without the user's answer? If no, it's A1 (clarification); if yes, it's A2 (confirmation). This review found that 12 records in the A1/A2/A5 cluster had *identical* agent behavior and produced *four different labels* with perfect judge-determinism (gpt-5.4→A1 100%, gpt-4o→A5 100%, sonnet→A2 92%). The distinction between A1 and A2 requires inferring agent knowledge state ("does the agent have a specific action in mind?"), which can't be reliably done from text.

The proposed fix here is structural: collapse A1 and A2 into a single category (A_ASK = "did not execute, asked user for input") with textually observable attributes (e.g., `contains_yes_no_question`, `requests_credential`) rather than mind-reading categories. Preserves any downstream distinction that's actually textually determinable; drops the distinctions that aren't.

---

## 4. Where the proposed fixes diverge

On the seams both analyses address, the diagnoses converge but the recommended fixes differ in philosophy.

| Seam | Collaborator's fix | This review's fix |
|---|---|---|
| A4 / A5 | Dominance test: "primary communicative act is refusal → A5 even if suggestion appended" | Orthogonal booleans: `refused=True` AND `proposed_alternative=True` both flagged independently; no forced choice |
| A0 / A3 | Define "fully produced" via state-change vs state-read test | Same direction; narrow A3 to read-only investigative actions with unexecuted downstream state change |
| A0 / A4 | Classify method-substitution and scope-modification as A4 | Partially addressed via text-test scope for A0 (literal request only) |
| A1 / A2 | Decisional test: "could agent proceed without the answer?" | Collapse into A_ASK with textual sub-type attributes |

The differences are design philosophy choices, not contradictions in the underlying data:
- **Prompt-level vs structural**. Collaborator's fixes are all prompt revisions that improve consistency within the existing schema. This review proposes some schema changes (multi-label, category collapse) that trade backward compatibility for structural honesty about what judges can and can't reliably distinguish.
- **Near-term vs longer-term**. Prompt-level fixes are faster to implement and test. Schema changes require a major version bump and re-running evaluations. A reasonable path is prompt fixes first (fast wins on the biggest seams), then schema changes if residual disagreement stays high.

---

## 5. Practical takeaways

### High-confidence claims from both analyses combined

1. A4 / A5 is the dominant Action disagreement and should be the first target for fixes.
2. Judge-model identity is a stronger predictor of votes on fuzzy boundaries than the scenario content is. But this is about *per-seam calibration*, not global judge stringency.
3. The A0 boundary ("produced fully") needs operational definition for multi-step and modified-fulfillment cases. Both analyses converge on this.
4. The A1 / A2 distinction is a low-volume but high-ambiguity seam.

### Things the collaborator's analysis surfaces that should be incorporated

- A0 / A4 as a distinct pattern (method substitution, scope modification). Worth isolating in our analysis and addressing explicitly in rubric revisions.
- Volume-based prioritization of fixes alongside structural soundness.
- Unifying A0 / A3 and A0 / A4 under one "partial execution" framing makes the shared root clearer.

### Things this review surfaces that should be considered

- A multi-label schema resolves A4 / A5 structurally; worth weighing against the dominance-test approach.
- Cross-seam coalition shifts argue against treating judges as having global stringency.
- Pipeline-level tiebreaker behavior has its own reliability problem independent of prompt fixes.
- Some category boundaries (A1 vs A2) may not be textually determinable and collapsing them may be more honest than adding another test.

### Open questions for follow-up

- How much of the A0 / A4 cluster represents genuine partial fulfillment versus agent responses that do several things at once? Disambiguating would sharpen the fix.
- If prompt-level fixes are implemented first, what disagreement rate remains after they're applied? That residual tells us whether schema-level fixes are needed.
- Inter-rater reliability of judges on a revised rubric — both analyses assume their findings generalize, but a controlled re-run on a hold-out set would validate that.

---

## 6. One-paragraph summary

Both analyses independently identified the same core problems in Action classification: A4 / A5 is the dominant disagreement, judge camps split along consistent rubric-interpretation lines, and specific phrases in the rubric (notably "without offering an alternative" and "produced fully") are genuinely ambiguous. The collaborator's analysis adds a distinct partial-fulfillment pattern we hadn't isolated and prioritizes fixes by addressable volume. This review adds a structural perspective — multi-label classification, cross-seam coalition analysis, a root-cause decomposition framework, and pipeline-level disposition for contested records. The two analyses are complementary rather than contradictory; the strongest path forward combines the collaborator's prompt-level fixes (fast wins on the biggest disagreements) with the structural changes this review proposes (longer-term reliability for the cases where the rubric is asking judges to discriminate things the text can't actually distinguish).
