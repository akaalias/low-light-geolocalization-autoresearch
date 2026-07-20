# Autoresearch iteration — one focused experiment

You are one iteration of an autonomous research loop for UAV low-light
geolocalization. Read `CLAUDE.md` (§1, §3, §6 especially) for full context.
The harness (loop.sh) will train, score, log, and keep/revert AFTER you exit —
you only design the experiment and edit the code.

## Your job, in order

1. **Review the research history.** Query the lineage DB:
   `sqlite3 experiments.sqlite "SELECT id, title, category, hypothesis, expected_outcome, result, conclusion, primary_metric, kept FROM experiments ORDER BY id DESC LIMIT 15;"`
   Note which hypotheses were supported/refuted. Do not repeat a refuted
   experiment without a materially new angle.

2. **Design ONE focused experiment** — proper experiment design, pre-registered
   before you touch code. Write it to `runs/pending_experiment.json`:
   ```json
   {
     "title": "one-line name",
     "category": "architecture|loss|augmentation|relighting|training|quantization|other",
     "hypothesis": "what you believe is limiting the metric and why this change addresses it",
     "method": "the ONE focused change, concretely (files, mechanism)",
     "expected_outcome": "predicted effect on the §6 worst-case median error, quantified if possible",
     "init_strategy": "from-scratch | pretrained:<name>"
   }
   ```

3. **Implement exactly that change** in the agent-editable files (`model/`).
   Keep `train.py`'s CLI contract and the ONNX export contract in `model/model.py`'s
   docstring intact — the frozen scorer depends on them.

## Hard rules

- Edit ONLY `model/` (and `runs/pending_experiment.json`). Files listed in
  `/FROZEN` are off-limits; the harness hard-reverts any change to them.
- NEVER touch, read, or evaluate the `hamburg` holdout area (§5).
- ONE focused change per iteration — if you can't describe it in one sentence,
  it's too big. Prefer architectural/procedural novelty over hyperparameter
  nudges (§3): changing a learning rate is a weak experiment; changing the
  coordinate parameterization, loss family, relighting-for-training, or model
  topology is a strong one.
- Do not run training yourself; the harness does that. A quick syntax check
  (`.venv/bin/python -c "import model.train, model.model"`) is fine.
- Stay within the deployment gates: exported ONNX ≤ 4 MiB per area, host
  latency proxy ≤ 250 ms (see pipeline/score.py).
