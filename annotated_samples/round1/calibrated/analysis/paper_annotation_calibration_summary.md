# Annotation and Calibration Summary

## Process

We used a pool of six human annotators. Before the main annotation pass, the
annotators aligned on the axis-specific rubric and label definitions. The task
was then run through a custom annotation UI that showed the relevant scenario,
the target agent thought or action, the label options, and the full rubric
definitions throughout annotation. Annotators did not see model-judge labels
during this process.

Each selected sample was independently labeled by three human annotators from
the pool. The assigned annotators labeled only the target axis for that sample:
detection labels for agent thoughts, action-type labels for agent actions, or
safety labels for agent actions. We first measured agreement on these raw human
annotations. We then conducted a calibration pass over disagreement cases. During
this pass, we corrected clear annotator-level mistakes where the intended rubric
application was straightforward, while leaving genuinely ambiguous or
judgment-dependent cases as disagreements. This refinement step corrected 40
individual annotator labels across 38 samples.

Agreement improved substantially after this correction pass. Unanimous
agreement increased from 44/134 samples to 80/134 samples, and nominal
Krippendorff's alpha increased from 0.459 to 0.662. Because the disagreement
reduction came from resolving clear annotation errors rather than changing the
rubric, we treated the rubric as sufficiently stable for final adjudication.

After the annotator-correction pass, remaining unresolved cases were reviewed by
calibration reviewers and assigned final benchmark labels. These final labels
were recorded separately from the individual annotator labels: final adjudication
did not retroactively force every annotator label to match. In total, 134
samples were reviewed, 128 were retained with final labels, and 6 were dropped
as unsuitable for final evaluation.

## Agreement Metrics

We report nominal Krippendorff's alpha because the labels are categorical rather
than ordinal. For the combined overall number, labels are axis-prefixed before
computing alpha, so labels from different axes are not treated as the same label
space. We also report the disagreement rate, defined as the fraction of samples
where the three human annotations were not unanimous.

## Agreement Before and After Calibration

| Stage | Items | Unanimous | Majority | Tie | Disagreement Rate | Nominal Alpha |
|---|---:|---:|---:|---:|---:|---:|
| Original human annotations | 134 | 44 | 75 | 15 | 0.672 | 0.459 |
| Refined human annotations | 134 | 80 | 41 | 13 | 0.403 | 0.662 |

Retained-only agreement follows the same pattern. On the 128 retained samples,
nominal alpha increased from 0.472 before correction to 0.680 after correction.

## Agreement by Axis

| Axis | Stage | Items | Unanimous | Majority | Tie | Disagreement Rate | Nominal Alpha |
|---|---|---:|---:|---:|---:|---:|---:|
| Action | Original | 52 | 21 | 25 | 6 | 0.596 | 0.443 |
| Action | Refined | 52 | 34 | 12 | 6 | 0.346 | 0.646 |
| Detection | Original | 66 | 15 | 42 | 9 | 0.773 | 0.239 |
| Detection | Refined | 66 | 30 | 29 | 7 | 0.545 | 0.458 |
| Safety | Original | 16 | 8 | 8 | 0 | 0.500 | 0.266 |
| Safety | Refined | 16 | 16 | 0 | 0 | 0.000 | 1.000 |

## Final Calibrated Dataset

| Axis | Final Label | Count |
|---|---|---:|
| Action | A0 | 12 |
| Action | A1 | 3 |
| Action | A2 | 2 |
| Action | A3 | 6 |
| Action | A4 | 19 |
| Action | A5 | 4 |
| Action | Dropped | 6 |
| Detection | D0 | 18 |
| Detection | D1 | 13 |
| Detection | D2 | 24 |
| Detection | D3 | 11 |
| Safety | SAFE | 12 |
| Safety | UNSAFE | 4 |

The final retained set contains 128 samples: 46 action samples, 66 detection
samples, and 16 safety samples. Six action-axis samples were dropped.

## Final Label Relationship to Sources

Among the 128 retained samples, final calibrated labels matched the refined
human consensus in 109 cases (85.2%). Exact agreement with the judge plurality
was lower, 41/128 (32.0%), largely because many judge votes were ties. The final
label was within the judge plurality set in 107/128 cases (83.6%).

## Generated Artifacts

- `final_calibrated_review_2026-05-03.json`: frozen calibrated source of truth.
- `final_scenario_labels_all.csv`: all 134 reviewed samples, including dropped rows.
- `final_scenario_labels_retained.csv`: 128 retained samples with final labels.
- `agreement_before_after_overall.csv`: overall agreement before and after correction.
- `agreement_before_after_by_axis.csv`: axis-level agreement before and after correction.
- `final_label_distribution.csv`: final label counts by axis.
- `dropped_rows.csv`: dropped sample list.
