## PATIENCE SPENT — THIS ITERATION MUST PIVOT

17 consecutive experiments have failed to beat the current best.
A pivot means COMPLETELY RETHINKING THE ARCHITECTURE, not touching the one
stage named below as frozen while carrying the rest of the current design
over unchanged. Do not refine, extend, or swap one part of the champion's
mechanism and call it a pivot. Propose a genuinely different overall
design — the spec (§3) explicitly invites, among others: dispatcher +
lighting-condition-specialist models, learned relighting, a different
coordinate parameterization, quantization-aware capacity changes, or
training-data strategy overhauls — but whichever family you pick, it must
change how the WHOLE pipeline works end to end, not one isolated stage.



### The champion's backbone is OFF LIMITS this round

The current champion's backbone identity is: mnv3s_features8.pt,mobilenet_v3_small

Your design MUST NOT use it. Not re-tuned, not truncated at a different
layer, not wrapped in a dispatcher, not kept as one branch of an ensemble,
not reloaded from the same weights blob under a new class name. After
implementation the resulting source is scanned, and if any of those
identifiers still appear in model/ the experiment is REJECTED before
training. Rethinking the machinery bolted around an unexamined trunk is
exactly what the last five demanded pivots did; it is not a pivot.

A from-scratch trunk is an acceptable answer. So is a genuinely different
pretrained family. Carrying the same trunk across is not.

Every non-frozen stage in your architecture.stages list must be marked
"changed": true this round. If any stage is left exactly as before, this
experiment will be rejected before training even starts — this is checked
against your actual code diff, not just your own self-report.

# Autoresearch experiment — the design stage

You are one experiment of an autonomous research loop for UAV low-light
geolocalization. Read `CLAUDE.md` (§1, §3, §6 especially) for full context.
The harness (loop.sh) will train, score, log, and keep/revert AFTER you exit —
you only design the experiment and edit the code.

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

   **Plateau rule:** if three or more consecutive experiments were reverted,
   do not attempt another variation of the last refuted mechanism. Either
   pick a design family absent from the history (dispatcher + lighting
   specialists, pretrained init, learned relighting, training-scale, …) or
   attack the bottleneck the refuted hypotheses jointly point at —
   **but check which stages that "design family" actually touches before
   you commit to it.** Query the last several kept experiments'
   `arch_json` (`SELECT arch_json FROM experiments WHERE kind='development'
   ORDER BY id DESC LIMIT 10;`) and look at which stage names never carry
   `"changed": true`. A losing streak is not just "we haven't tried a
   dispatcher yet" — it is usually "the trunk / descriptor / decode has
   gone unquestioned for N rounds while satellite modules (gates, heads,
   auxiliary losses, samplers) keep churning around it." Picking a name
   off the suggested list while leaving that frozen core untouched is
   incremental tuning wearing a pivot's clothes, and the harness's own
   patience check (below, once it fires) will call this out explicitly by
   naming the frozen stages.

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
       {"name": "Camera frame", "detail": "128×128 px crop, one of 6 lighting renders", "changed": false},
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

   **If a pivot was demanded above:** every non-frozen stage must be marked
   `"changed": true` this round — checked against your ACTUAL code diff
   once implementation happens, not just this self-report. A design that
   leaves most stages unchanged gets rejected before implementation ever
   starts, so there is no reason to under-commit here: if you're not
   genuinely rethinking a stage, don't mark it changed, and don't propose
   a pivot that stops short of the bar.

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
