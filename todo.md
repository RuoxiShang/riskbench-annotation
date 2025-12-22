# RiskBench Scenario Generation and Human Verification


### Updated To-do
There are a few issues with the current annotation tasks
1. the first does this scenario have a real risk? and second questions Is the risk obvious or subtle? are ambiguous, meaning that it's hard for the human annotator to assess this when they see the first example. what's the bar? what's the standard? what's considered to have real risk and obvious risk?
2. the three tags are also not clear enough. the first one is domain, second is x, third is y. this is not clear, but I also don't know how to improve this. it's also not clera what is the definition of the risk type and risk factor. the domain is self explanatory, but the other two are not


### Annotation UI
- Hide AI scores from annotators to avoid bias
- Replace "Neither" with two options: "Both are bad" / "Both are good"
- Add explicit judging criteria for annotators (leverage llm-as-a-judge dimensions)
- Add new tasks. e.g. verify llm-as-a-judge accuracy (is the AI score correct?)

### Data Sampling (`prepare_data.py`)
- Filter for similar response lengths across risk levels (reduce length-risk correlation)
- Use semantic similarity for better pairwise scenario matching

### Scenario Generation (pipeline)
- Drop "medium" risk level — only use "low" vs "high" for now
- Make risk implicit rather than explicit in scenarios

### Open Questions
- How to standardize deltas between risk levels?
- Final benchmark size?

---

## Meeting Notes 11/26

### Context
To give everyone a better understanding of what the scenarios, actions, examples look like so that we can collectively critique and improve upon them, we built a human annotation UI.
- Annotation webtool: https://ruoxishang.github.io/riskbench-annotation/
- Annotation sheet: riskbench-annotation
- 6 of us examined a total of 45 examples during this meeting and shared feedback

---

### Issues & Next Steps

#### 1. Scenario Sampling

**Scenario similarity & comparison quality**
- Current comparison setup only uses three high-level tags. Even when those tags match, the actual scenarios can be quite different, which makes pairwise comparisons hard.
- Idea: Generate more scenarios and then compute semantic similarity (between scenarios and/or their risk/rating properties) so that comparisons happen between more semantically similar items.

**Length bias in risk level**
- Longer response → higher risk; shorter response → lower risk
- The actions could bake in a spurious correlation between length and risk
- Idea: When sampling scenarios, filter/select those with similar response lengths across risk levels to reduce this bias.

#### 2. Scenario Generation

**Medium vs. low risk indistinguishable**
- Current generation pipeline makes "medium" and "low" risk scenarios too similar, so annotators find them ambiguous and hard to distinguish.
- Possible cause: The base prompt / base scenario template might not be strongly prompting for a clear "medium risk" level, leading to a weak difference from "low."
- One proposed fix: Drop the "medium" level entirely and just work with "low" vs "high" risk scenarios, at least for now.

**Risk in scenarios**
- In many scenarios, the scenario itself is already clearly compromised: the risk is too obvious and prominent.
- Ideas:
  - More variations of how visible the risk is
  - Have a layer that obscures the explicit risk label (the scenario can contain implicit risk factors without stating the risk outright)
  - Keep the risk factors present but less obvious
  - Avoid "giving the model the exact risk" directly

#### 3. Improve Annotation Process

**Current pairwise comparison UI**
- There is an option like "neither" (when annotators don't think either is better)
- More granular options needed:
  - "Both are bad"
  - "Both are good"

**Lack of clear judging dimensions**
- Right now annotators don't know what exact criteria they should use
- Idea: Introduce explicit judge dimensions (potentially leveraging dimensions we use in llm-as-a-judge)

**AI score bias**
- Currently the UI shows the AI score, which likely biases annotators
- Plan: Hide / remove the AI score from the annotator UI

#### 4. New Tasks

**Current task**
- The current task is basically pairwise comparison between systems in an ablation test configuration. Mainly used it for this meeting, as a way to get started and get feedback.

**Example of a more meaningful task**
- Ask annotators to label whether "llm-as-a-judge" is accurate: Does llm-as-a-judge correctly detect bad errors / bad responses?

**Verify llm-as-a-judge**
- Manos found one example that is low quality → indeed rated low by llm-as-a-judge
- Idea: Collect more such examples and let people verify and build confidence in llm-as-a-judge as an evaluator

---

### TBD

**Uneven deltas between risk levels**
- There are nominal levels like baseline / low / medium / high, but the "distance" between baseline→medium and medium→high can vary a lot across scenarios
- Flagging this as a problem to think about: How to standardize, balance, or control the deltas between risk levels across scenarios

**Size of the benchmark**
- The total number of scenarios to generate for the final benchmark is still undecided

---
## UI Iteration 11/25
- [x] Add full tags for risk domain, risk type, and risk factor
- [x] Add filter for these tags
- [x] Have the full llm-as-a-judge (ai score) score breakdown instead of just the final average
- [x] There should be two scenarios per paired comparison, right now there is only one scenario task used for the comparison
- [x] People don't need to indicate two questions, they can just click on version A or version B to choose one
- [x] Right now the contrast is not big, i want scenarios that have greater contrast in score differences for this task, can you ensure that in data sampling stage?
- They can highlight and annotate or leave comments
- [x] Remove the A, B tag, unnecessary
- [x] Change the style of the yellow background for scenario text, i don't like that
- Answer a list of questions (e.g. which version is better, is it really reflecting the high risk taxonomy? etc.) the questions need to be easy to answer (not ambiguous or hard to differentiate)
