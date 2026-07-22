# Autoresearch iteration — one focused experiment

You are one iteration of an autonomous research loop for UAV low-light
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
   attack the bottleneck the refuted hypotheses jointly point at.

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
     ]},
     "architecture_svg": "<svg viewBox='0 0 980 300' …>…</svg>"
   }
   ```

   `architecture_svg` is the **technical architecture diagram** of the model
   you are testing — a proper ML-paper figure of the design, drawn by you,
   shown at the top of this experiment's gallery entry. **Draw tensors and
   operations as the things they are — NOT as labeled boxes:** the input
   image as a pixel-textured square; conv feature maps as pseudo-3D slabs
   that shrink spatially and deepen in channels; 1-D vectors as thin
   vertical tick-bars; fully-connected layers as fans of thin crossing
   lines between bars; spatial fields/grids as actually-drawn grids with
   shaded cells; decodes/aggregations as thin lines converging from cells
   onto a point; samplers/targets as small pictorial glyphs. Captions sit
   UNDER each element (name ≤10.5px weight 600, sub-note ≤9.5px); tensor
   shapes annotate the flow in small italics (128×128×3 → 8²×128 → 1024).
   Losses/targets/samplers live in a lane below the inference path,
   annotated with slanted dashed leader lines to small text — no boxes
   around them. Draw the two FROZEN endpoints — the camera-frame input and
   the (lat, lon, confidence) output — entirely in #9b998c with a small
   italic “frozen contract” tag: they are fixed by the harness and outside
   your search space. Everything between them is your design: draw it in ink,
   with red only on what THIS experiment changes. Style contract, so all experiments' figures read as one
   paper: viewBox width 980 (height ~300–360); transparent background; ink
   #111111, captions #6b6a60, annotations/arrows #9b998c; **#8c2f1f (red)
   reserved for exactly what this experiment changed**; training-only
   elements in #8a6a1e (or red if changed); font-family
   Palatino,Georgia,serif; stroke-width ≈1.2 elements, 1 arrows; fills only
   faint tints (opacity ≤ .12); no gradients, no icons, no emoji. Inference
   flows left → right from camera frame to (lat, lon, confidence).
   **The camera frame is a fixed glyph — copy it verbatim.** It must look
   like an actual nadir frame of terrain (streets, building footprints),
   not abstract pixels, and be identical in every figure. Use exactly this
   snippet, substituting Y for the frame's top edge (pick Y so the frame
   centers on your inference lane; captions go under it as usual — note
   128²×3 is the model input crop, ~1 m/px, not the sensor's native
   resolution):
   ```svg
   <g id='cam-terrain'><rect id='frozen-input' x='26' y='Y' width='76'
      height='76' fill='#f6f4ea' stroke='#9b998c' stroke-width='1.6'/>
   <path d='M31 Y+47 L97 Y+27' stroke='#e6e3d4' stroke-width='5' fill='none'/>
   <path d='M59 Y+6 L49 Y+70' stroke='#e6e3d4' stroke-width='3.5' fill='none'/>
   <rect x='34' y='Y+9' width='12' height='8' fill='#d9d5c3' transform='rotate(-8 40 Y+13)'/>
   <rect x='78' y='Y+8' width='10' height='11' fill='#cfccbd'/>
   <rect x='35' y='Y+57' width='13' height='8' fill='#d9d5c3'/>
   <rect x='75' y='Y+50' width='10' height='9' fill='#cfccbd' transform='rotate(6 80 Y+54)'/>
   <rect x='54' y='Y+31' width='9' height='8' fill='#d9d5c3' opacity='.85'/>
   <ellipse cx='86' cy='Y+63' rx='8' ry='6' fill='#8a6a1e' opacity='.12'/>
   <circle cx='40' cy='Y+28' r='.7' fill='#6b6a60' opacity='.5'/>
   <circle cx='70' cy='Y+14' r='.7' fill='#6b6a60' opacity='.5'/>
   <circle cx='92' cy='Y+36' r='.7' fill='#6b6a60' opacity='.5'/>
   <circle cx='52' cy='Y+52' r='.7' fill='#6b6a60' opacity='.5'/>
   <circle cx='82' cy='Y+70' r='.7' fill='#6b6a60' opacity='.5'/>
   <circle cx='31' cy='Y+42' r='.7' fill='#6b6a60' opacity='.5'/></g>
   ```
   (Y+n means the literal number Y plus n — compute the values. Every glyph
   element stays strictly INSIDE the frame border — figcheck rejects a
   figure without the `cam-terrain` group.) Draw your
   receptive-field square and kernel-projection lines on top of it as
   usual.
   **Anchor the frozen endpoints identically in every figure** so all
   experiments' figures line up when compared down the gallery page: the
   camera-frame square starts at x=26 (its captions centered on x=53), and
   the output is right-anchored — decode crosshair at x=812, the
   (lat, lon, confidence) text block text-anchor=start at x=828. Mark the
   anchors machine-checkably: the camera-frame rect carries
   `id='frozen-input'`, the output text block carries `id='frozen-output'`.
   Lay the elements between them out on a running x-cursor with generous
   spacing so nothing overlaps.
   **Readability contract** (figcheck verifies this geometrically): no
   text may overlap other text, and no line (arrows, converge fans,
   leader lines) may pass through a label — a line may END at a label,
   never cross one. Rules distilled from review rounds: dashed leaders
   run as orthogonal L-routes through empty lanes, never diagonally
   across components; converge/vote lines originate at their true
   sources (the actual dots or window cells, not generic positions);
   every element owns its caption — adjacent columns stagger their
   caption rows instead of colliding; prefer moving a label into empty
   horizontal space over stacking it against a neighbor. Width is fixed
   at 980, but **height is yours**: grow the viewBox (240–640) whenever
   more vertical room makes the layout cleaner rather than cramming.
   **Before finishing, validate:**
   `.venv/bin/python -m autoresearch.figcheck` — it checks the anchor
   contract on runs/pending_experiment.json; revise until it prints PASS.
   Consecutive conv layers must be tied by kernel-projection lines (small
   kernel square on one face, faint lines converging to a cell on the
   next) so the encoder reads as one computation, not boxes in a row.
   `archive/arch_svg_reference.py` is the concrete reference implementation
   of this entire visual language — read it and reuse its helper geometry
   for any stage that already has one.

   `eli5` and `architecture` feed the human-facing gallery. `architecture.stages`
   is the model's inference path left-to-right, camera frame → (lat, lon,
   confidence) output — one box per stage, plain-language `detail`,
   `"changed": true` ONLY on the stages this experiment touches. Reuse the
   previous experiment's stage names verbatim wherever a stage is unchanged
   (check `SELECT arch_json FROM experiments WHERE arch_json IS NOT NULL ORDER BY id DESC LIMIT 1;`) —
   the diagrams are compared box-by-box across experiments. A change that only
   affects training (loss, augmentation, schedule) keeps the inference stages
   unchanged and adds one final stage with `"train_only": true` describing the
   training signal.

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
- ONE focused change per iteration — if you can't describe it in one sentence,
  it's too big. Prefer architectural/procedural novelty over hyperparameter
  nudges (§3): changing a learning rate is a weak experiment; changing the
  coordinate parameterization, loss family, relighting-for-training, or model
  topology is a strong one.
- Do not run training yourself; the harness does that.
- Stay within the deployment gates: exported ONNX ≤ 4 MiB per area, host
  latency proxy ≤ 250 ms (see pipeline/score.py).
