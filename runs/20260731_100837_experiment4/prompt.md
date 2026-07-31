## FORCED DIRECTIVE — re-implement the lost champion

The scoring metric was corrected today (median -> geometric mean; see
pipeline/score.py). Under the corrected metric, experiment 2 is the best
result so far (1323.6 m geomean, locating 8% of Berlin within 100 m, versus
0.0% for the baseline). But experiment 2 was reverted at the time by the OLD,
broken metric, and its source code was destroyed by that revert — only its
design survives.

**This experiment must re-implement experiment 2's design faithfully**, from
the brief below. Do not improve it, do not extend it, do not substitute your
own idea: the goal is to restore a champion that was lost to a measurement
bug, so the loop has a correct starting point. Pre-register it honestly as a
re-implementation.

### Title
Classify-then-refine: 32x32 map-cell softmax + within-cell offset replaces direct coordinate regression

### Method
In model/model.py only the head and loss change: keep TinyLocNet's conv trunk (~100k params) verbatim; replace the single Linear(128,3) head with three heads over the same GAP feature — cell logits Linear(128,1024), per-cell offsets Linear(128,2048) tanh-bounded to half a cell, and the same loose-BCE confidence head as the baseline. Inference decodes argmax cell center + gathered offset inside the exported ONNX graph, so the frozen [[u,v,conf]] contract is untouched. Loss becomes cross-entropy on the true cell + MSE on the true cell's offset (teacher-forced) + the baseline's 0.1-weighted confidence BCE. model/train.py changes one line (call the new raw-output training path). Grid is defined in normalized [0,1] map coordinates, so nothing is Berlin-specific.

### Implementation brief (follow this exactly)
SCOPE: edit model/model.py and model/train.py only. Trunk, data loading, augmentation, CLI, epochs/crops defaults, and export contract all stay as they are.

=== model/model.py ===
1. Add module constant GRID = 32 (cells per axis, in NORMALIZED [0,1] map coords — no area-specific numbers anywhere).
2. TinyLocNet.__init__: keep self.features (the chans=[3,16,32,64,128] strided-conv stack) EXACTLY as is. Delete self.head = nn.Linear(chans[-1], 3). Add: self.cell_logits = nn.Linear(128, GRID*GRID); self.cell_offset = nn.Linear(128, GRID*GRID*2); self.conf_head = nn.Linear(128, 1).
3. Add a private trunk helper: _embed(x) = self.features(x).mean(dim=(2,3)) -> [B,128].
4. Add forward_train(x) -> tuple (logits, offsets, conf_logit): logits = self.cell_logits(f) [B, G*G]; offsets = torch.tanh(self.cell_offset(f)).view(B, GRID*GRID, 2) * (0.5/GRID)  (each cell's offset bounded to half a cell in normalized units); conf_logit = self.conf_head(f) [B,1]. Do NOT apply sigmoid to conf here.
5. Rewrite forward(x) (this is what export_onnx traces — it must remain the full frame->[u,v,conf] decode): compute logits, offsets, conf_logit via the same heads (share code with forward_train); idx = torch.argmax(logits, dim=1) [B]; iy = idx // GRID; ix = idx - iy*GRID  (use this subtraction form, NOT the % operator, for safe ONNX tracing); cell centers cu = (ix.float()+0.5)/GRID, cv = (iy.float()+0.5)/GRID; off = torch.gather(offsets, 1, idx.view(-1,1,1).expand(-1,1,2)).squeeze(1) [B,2]; u = (cu+off[:,0]).clamp(0,1); v = (cv+off[:,1]).clamp(0,1); conf = torch.sigmoid(conf_logit)[:,0]; return torch.stack([u,v,conf], dim=1) [B,3]. Convention throughout: ix indexes the u axis, iy the v axis, cell id = iy*GRID+ix — keep loss_fn identical on this.
6. Rewrite loss_fn(raw, target_uv) where raw is forward_train's tuple: (a) tx = target_uv[:,0].mul(GRID).floor().long().clamp(0, GRID-1), ty likewise from target_uv[:,1]; cell = ty*GRID+tx; ce = F.cross_entropy(logits, cell). (b) pred_off = torch.gather(offsets, 1, cell.view(-1,1,1).expand(-1,1,2)).squeeze(1); targ_off = target_uv - torch.stack([(tx.float()+0.5)/GRID, (ty.float()+0.5)/GRID], dim=1); off_loss = (((pred_off-targ_off)*GRID)**2).sum(dim=1).mean()  (scaled by GRID so it's O(1)). (c) confidence, SAME loose criterion as the baseline so the model stays scoreable and never abstains into the coverage FAIL: with torch.no_grad() decode the hard prediction exactly as forward does (argmax cell center + gathered offset), coord_err = ||decoded_uv - target_uv||_2, good = (coord_err < 0.5).float(); conf_bce = F.binary_cross_entropy(torch.sigmoid(conf_logit)[:,0].clamp(1e-6, 1-1e-6), good). Return ce + off_loss + 0.1*conf_bce. Preserve the existing comment explaining WHY the conf target is deliberately loose.
7. build_model(), export_onnx() (opset 17, dynamo=False, input name 'frame', output name 'uvc', dummy zeros(1,3,128,128)), and estimate_position() stay byte-identical in behavior. Update the class/module docstrings to describe the new head.
8. Export fallback ONLY if torch.onnx.export fails on gather-after-argmax: replace the gather in forward with a one-hot matmul — oh = F.one_hot(idx, GRID*GRID).float().unsqueeze(1) [B,1,G*G]; off = torch.bmm(oh, offsets).squeeze(1). Do not reach for this unless the plain gather export actually errors.

=== model/train.py ===
9. One change only: in the inner loop replace loss = loss_fn(model(xb), yb) with loss = loss_fn(model.forward_train(xb), yb). Everything else — CLI (--area, --out-dir, --data-dir, --epochs, --max-crops-per-bucket, --seed), tensor loading, rotation augmentation, Adam lr=1e-3, batch 64, ONNX path <out>/models/<area>.onnx, train_info.json logging, init field 'from-scratch' — stays untouched.

=== Contracts to verify before exiting ===
- python -m model.train --area berlin --out-dir <dir> still runs and exports <dir>/models/berlin.onnx taking 1x3x128x128 float32 in [0,1] and returning [[u,v,conf]] with u,v normalized map coords and conf in [0,1] (frozen pipeline/score.py depends on this exactly).
- Exported ONNX ≤ 4 MiB (expected ~2.0 MB: ~500k params fp32) and trivially under the 250 ms host latency proxy.
- Sanity-check the export numerically: run the ONNX through onnxruntime on a random input and confirm outputs match the torch forward() to ~1e-4.
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
