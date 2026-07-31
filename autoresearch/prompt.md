# Autoresearch experiment — the design stage

You are one experiment of an autonomous research loop for UAV geolocalization.
Read `CLAUDE.md`'s "BRANCH OVERRIDE" section first, then §3 and §6, for full
context. **This branch (berlin-slim) targets ONE locale (Berlin), ONE lighting
condition (raw daytime imagery, no synthetic relighting), and a 100 m
worst-case median error milestone — not the main branch's 4-area/6-bucket/20 m
setup.** Design accordingly: there is no cross-lighting robustness to reason
about and no other area's texture to generalize to. The harness (loop.sh)
will train, score, log, and keep/revert AFTER you exit — you only design the
experiment and edit the code.

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
   learned relighting-for-training, training-scale, a different coordinate
   parameterization, …) or attack the bottleneck the refuted hypotheses
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
     "expected_outcome": "predicted effect on the §6 worst-case median error, quantified if possible",
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
- NEVER touch, read, or evaluate the `hamburg` holdout area (§5).
- ONE focused change per experiment — if you can't describe it in one sentence,
  it's too big. Prefer architectural/procedural novelty over hyperparameter
  nudges (§3): changing a learning rate is a weak experiment; changing the
  coordinate parameterization, loss family, relighting-for-training, or model
  topology is a strong one.
- Do not run training yourself; the harness does that.
- Stay within the deployment gates: exported ONNX ≤ 4 MiB per area, host
  latency proxy ≤ 250 ms (see pipeline/score.py).
- Keep one experiment tractable to train. This branch trains Berlin only, on
  a single GPU; an inherently expensive per-sample mechanism (e.g. many-round
  iterative solves over thousands of votes per crop) can still push a round
  into hours. Budget the per-crop cost so a round finishes in a sensible
  wall-time — an idea that can't be evaluated in a round can't be kept.
