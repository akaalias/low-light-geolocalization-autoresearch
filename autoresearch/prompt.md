# Autoresearch experiment — the design stage

You are one experiment of an autonomous research loop for UAV geolocalization.
Read `CLAUDE.md`'s "BRANCH OVERRIDE" section first, then §3, §4 and §6.
The harness (loop.sh) will train, score, log, and keep/revert AFTER you exit —
you only design the experiment.

## THE GOAL: MEMORIZE ONE BOUNDING BOX. OVERFITTING IS THE FEATURE.

This branch builds a **visual memory of Berlin**, not a model that reasons
about aerial imagery in general. One model, one bbox, deployed only over that
bbox. It is *supposed* to know this specific city by heart. You are not trying
to generalize to other places, other lighting, or unmapped ground — none of
those are measured, and designing for them costs capacity you need for
memorizing.

**How the split works, because it determines what a good design looks like:**

* **Training covers ALL of Berlin** — every lattice position, whole raster.
  The model is shown the entire area it must memorize.
* **Eval holds out VIEWPOINTS, not REGIONS.** Every eval frame stands on
  ground that WAS in training, but is framed 11–17 m off the nearest training
  vantage and at its own rotation. Mapped ground, novel view — exactly what an
  aircraft over a mapped city faces.
* So the task is: **recall a memorized place from a viewpoint you have not
  seen.** It is NOT: infer the location of ground you were never shown.
* A small 1-in-32-block region IS genuinely untrained, scored separately and
  logged only. It can never affect keep/revert. Ignore it when designing;
  it exists to reveal whether the model has spatial structure at all.

This matters because the split used to hold out regions, which left 28% of
Berlin untrained and put 100% of eval questions on never-seen ground — an
unanswerable task for a memorization model, and the likely reason ~60 earlier
experiments plateaued. Do not design as if that were still true.

**Scope:** ONE locale (Berlin), ONE lighting condition (raw daytime imagery,
no synthetic relighting — the relighting machinery is disabled on this branch).
There is no cross-lighting robustness to reason about and no other area's
texture to generalize to.

## THE METRIC: WORST-CASE GEOMETRIC-MEAN ERROR, MILESTONE ≤ 100 m

The optimized scalar is the **geometric mean** of position error in metres
(worst bucket), NOT the median. This matters for how you judge your own idea:

* A model that guesses near the map centre gets a tight, mediocre, unimodal
  error distribution — a decent median and no good tail.
* A model that genuinely memorizes is **bimodal**: some spots nailed, others
  badly wrong when it misidentifies. That is what progress looks like here.
* The median rewarded the first and punished the second, and was caught
  reverting the only experiment that had actually started memorizing (it
  located 8% of Berlin within 100 m; the baseline located 0.0%). The geometric
  mean reads every frame on a log scale, so pulling ONE place from 2 km to
  50 m — real memorization — moves the number.
* **Do not fear a worse median or a heavier tail if more places get nailed.**
  Also logged, not optimized: median, mean, p10, p25, and `hit_rate_at_target`
  (share of frames localized within 100 m). `hit_rate_at_target` is the most
  product-meaningful number — the aircraft takes a fix every 5–10 s and needs
  *some* frames to be good and to know which ones — so a design that raises it
  is on the right track even if other statistics wobble.

## Your job, in order

0. **Skim the library (optional input).** `autoresearch/library.md` holds
   the human researcher's inspiration notes. They do not fix your answer
   and you are free to ignore them — pick an entry up only when it
   genuinely fits your read of the history, and if you build on one, say
   so in your hypothesis.

1. **Review the research history.** Query the lineage DB:
   `sqlite3 experiments.sqlite "SELECT id, title, category, hypothesis, expected_outcome, result, conclusion, primary_metric, kept FROM experiments ORDER BY id DESC LIMIT 15;"`
   Note which hypotheses were supported/refuted. Do not repeat a refuted
   experiment without a materially new angle.

   **Plateau rule (advisory only on this branch):** the harness's automatic
   pivot enforcement (mandatory-pivot preamble, backbone-carry rejection) is
   disabled on berlin-slim — see CLAUDE.md "BRANCH OVERRIDE". Nothing will
   force or reject a pivot below. That said, the underlying discipline still
   applies by judgment: if three or more consecutive experiments were
   reverted, don't attempt another variation of the last refuted mechanism.
   Either pick a design family absent from the history (pretrained init,
   training-scale/coverage, a different coordinate parameterization, capacity
   allocation, decode resolution, …) or attack the bottleneck the refuted hypotheses
   jointly point at — checking, via `arch_json`
   (`SELECT arch_json FROM experiments WHERE kind='development' ORDER BY id
   DESC LIMIT 10;`), which stage names never carry `"changed": true`, since a
   losing streak is usually one unquestioned stage (trunk / descriptor /
   decode) with everything else churning around it, not a missing family.

2. **Design ONE focused experiment** — proper experiment design, pre-registered
   before you touch code. Write it to `runs/pending_experiment.json`:
   ```json
   {
     "title": "one-line name",
     "category": "architecture|loss|augmentation|relighting|training|quantization|other",
     "hypothesis": "what you believe is limiting the metric and why this change addresses it",
     "method": "the ONE focused change, concretely (files, mechanism)",
     "expected_outcome": "predicted effect on the §6 worst-case GEOMETRIC-MEAN error and on hit_rate_at_target, quantified if possible",
     "init_strategy": "from-scratch | pretrained:<name>",
     "eli5": "2-4 sentences for a smart non-ML reader: what you changed and why it might help, in everyday language — analogies welcome, zero jargon",
     "architecture": {"stages": [
       {"name": "Camera frame", "detail": "128×128 px daytime crop, Berlin only, no synthetic lighting variants", "changed": false},
       {"name": "Feature extractor", "detail": "plain-language description", "changed": false},
       {"name": "…", "detail": "…", "changed": true}
     ]}
   }
   ```

   Do NOT draw the architecture figure here — that is a separate agent's
   job, run later, only for experiments that actually reach training (see
   `autoresearch/prompt_figure.md`). Spending time perfecting an SVG for a
   design that might get rejected before it ever runs was wasted work; this
   stage's only output is the decision itself.

   `eli5` and `architecture` feed the human-facing gallery. `architecture.stages`
   is the model's inference path left-to-right, camera frame → (lat, lon,
   confidence) output — one box per stage, plain-language `detail`,
   `"changed": true` ONLY on the stages this experiment touches. Reuse the
   previous experiment's stage names verbatim wherever a stage is unchanged
   (check `SELECT arch_json FROM experiments WHERE arch_json IS NOT NULL ORDER BY id DESC LIMIT 1;`) —
   stage names must stay consistent across experiments since the later
   figure-drawing stage and plateaucheck both compare/track them by name.
   A change that only affects training (loss, augmentation, schedule) keeps
   the inference stages unchanged and adds one final stage with
   `"train_only": true` describing the training signal.

3. **Write the implementation brief.** You do NOT edit `model/` yourself —
   a separate implementation agent applies your design, seeing only the
   current code plus what you pre-registered. Add one more field to
   `runs/pending_experiment.json`:
   ```
   "implementation_brief": "exact file-level instructions: which functions/
   blocks in model/model.py and model/train.py change and how, what stays
   untouched, and every contract to preserve"
   ```
   Be precise enough that a competent engineer with no other context
   implements it in one pass. Always restate the fixed contracts:
   `train.py`'s CLI and the ONNX export contract in `model/model.py`'s
   docstring — the frozen scorer depends on them.

## Hard rules

- Edit ONLY `runs/pending_experiment.json`. You never edit `model/` (the
  implementation stage does) and files listed in `/FROZEN` are off-limits;
  the harness hard-reverts any change to them.
- ONE focused change per experiment — if you can't describe it in one sentence,
  it's too big. Prefer architectural/procedural novelty over hyperparameter
  nudges (§3): changing a learning rate is a weak experiment; changing the
  coordinate parameterization, loss family, capacity allocation, decode
  resolution, or model topology is a strong one.
- Do not run training yourself; the harness does that.
- Stay within the deployment gates: exported ONNX ≤ 4 MiB per area, host
  latency proxy ≤ 250 ms (see pipeline/score.py).
- Keep one experiment tractable to train. This branch trains Berlin only, on
  a single GPU; an inherently expensive per-sample mechanism (e.g. many-round
  iterative solves over thousands of votes per crop) can still push a round
  into hours. Budget the per-crop cost so a round finishes in a sensible
  wall-time — an idea that can't be evaluated in a round can't be kept.
