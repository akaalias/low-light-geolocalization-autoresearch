# UAV Low-Light Geolocalization — Autoresearch Bootstrap Spec

You are Claude Code Instance #1. Your job in this session is to **bootstrap**
this repository — scaffold the pipeline, prove the harness works end-to-end on
one small baseline run, and set up the autoresearch loop as a standalone bash
script. You are **not** the autoresearch loop itself. Once the harness is
proven, stop and hand off; a separate bash script will invoke headless Claude
Code instances repeatedly to do the actual research.

---

## 0. Mission

Build a from-scratch, from-scratch-licensed pipeline that, given a geographic
bounding box, trains a compact model that takes a single live camera frame
from a UAV's low-light sensor and returns an estimated GPS coordinate — with
no reference imagery shipped on the aircraft, no internet connectivity
required at inference time, and no external tool/matcher dependencies with
unclear licensing. The end deliverable per bounding box is a single weights
file plus one inference function: `estimate_position(frame) -> (lat, lon, confidence)`.

The system that produces that deliverable is itself the thing we're building:
an autonomous research loop that repeatedly trains, evaluates, and rewrites
its own approach until it hits the target metric defined below — not a
hyperparameter search over a fixed design, a coding agent free to change
architecture, loss, data augmentation, and training procedure entirely.

**Hard requirement: the pipeline must be general-purpose, not built for
Berlin+Prignitz specifically.** Every stage — fetch, relight, train, export
— must accept an arbitrary bounding box as a parameter, with no area-specific
constants, coordinate-range assumptions, or hardcoded logic anywhere in the
frozen pipeline or the trainable code. The five areas in §5 exist to exercise
and verify this genericity; they are not the limit of what the pipeline
should support. See §5 for how this is actually tested, since "accepts any
bbox in principle" and "actually verified not to overfit to the known areas"
are different claims.

---

## 1. Critical framing — read this twice

**One trained model = one bounding box.** The model memorizes its specific
training area directly into its weights (scene-coordinate regression /
absolute pose regression, not retrieval or matching against shipped
reference images). It will not — and is not expected to — generalize to a
different city.

The four evaluation areas defined in §6 are **four independent pipeline
runs**, each producing its own model. They exist to prove that the
*training method* (architecture search, relighting approach, augmentation
strategy — whatever the autoresearch loop lands on) generalizes across
structurally different area types (dense urban vs. sparse rural vs. two
other major metros), not to produce one model that covers all four. Do not
build a multi-area or multi-tenant model. Do not average performance across
areas in a way that hides a bad result in one of them — see §7.

---

## 2. Deployment target (hard constraints)

These come from a real, already-chosen airframe and are non-negotiable
unless explicitly revisited by the human:

- **Airframe:** TBS Source One V6, 5" open-source freestyle frame, paired
  with a minimal/low-cost FC+ESC stack and motors. This is a freestyle
  platform, not a survey platform — spare payload and power margin are
  small.
- **Payload budget:** camera + companion compute combined should target
  well under 50 g.
- **Power budget:** hard ceiling ≈ 6–9 W average (derived from ~5% of a
  typical 20–30 Wh 4S–6S pack over a ~10 minute flight). Target well under
  that — ideally under 2 W — since the whole point of this project is
  "little expense to battery."
- **Companion board:** **ESP32-P4**, chosen over ESP32-S3 specifically for
  its native MIPI-CSI + integrated ISP (so a real low-light MIPI camera
  module can attach directly) and its hardware CNN accelerator / vector
  instructions. Bare chip ~$3–4 in quantity; dev boards with camera support
  ~$25–50. **This is a recommendation, not yet hardware-validated** — see
  §10, first bullet.
- **Sensor:** low-light "starlight"-class CMOS (STARVIS2/IMX585 class or
  similar), MIPI interface to match the P4. Sensor cost is explicitly
  **not** constrained — only weight and power are.
- **Deployment artifact:** a single weights file (ONNX, converted to
  whatever runtime the P4 toolchain needs) plus one function,
  `estimate_position(frame) -> (lat, lon, confidence)`. **No reference
  imagery is shipped on-device** — this is the constraint that drives the
  scene-coordinate-regression architecture choice in §4.
- **Fix schedule:** adaptive, not continuous — roughly every 5–10 s during
  cruise, stepping up to every 1–2 s during final approach/landing (below
  ~30–50 m altitude). No optical-flow or rangefinder aiding is assumed;
  the vision fix is the only drift correction available, which is why the
  coarse-phase interval should stay toward the tighter end of that range.
- **Cost outside the sensor:** prefer the smallest/cheapest board and
  components that satisfy the above, but this is a soft preference, not a
  hard gate.

---

## 3. Modeling approach

**Scene coordinate regression / absolute pose regression, trained from
scratch per bounding box.** The model encodes "what does this specific area
look like, from which positions, under which lighting" directly into its
weights and regresses a coordinate at inference — no retrieval, no stored
reference images, no external matcher network in the deployed path. (This
family includes methods like DSAC/DSAC++ and ACE — "Accelerated Coordinate
Encoding" — which are specifically designed to train a compact,
scene-specific network quickly on a single GPU; useful prior art, not a
required dependency.)

**Search space explicitly open to the autoresearch loop, not fixed by this
spec:**
- Single unified model vs. several small lighting-condition-specific models
  behind a lightweight dispatcher (the human's own instinct leans toward
  the latter, but the loop should be free to experiment and decide based
  on the metric — including how well each option fits the P4's memory
  budget).
- Backbone/architecture, loss function, augmentation strategy, and
  quantization-aware training approach.
- From-scratch weight init vs. a permissively-licensed (MIT/BSD/Apache)
  pretrained backbone used only for initialization — log which was tried
  and why; see §10.

**Explicit goal for the loop:** favor real architectural/procedural
novelty over parameter tuning. If an experiment only changes a
hyperparameter within a fixed design, it is not using the agent's actual
advantage over a hyperparameter sweep.

---

## 4. Data pipeline (frozen — the loop must not rewrite this)

This part is fixed by the bootstrap instance (you) and must not be modified
by later autoresearch iterations, so that improvements are measured against
a stable, trustworthy eval set.

1. **Input:** a geographic bounding box.
2. **Reference imagery fetch:** daytime satellite/aerial imagery for that
   box from an **open-licensed source only** — Sentinel-2 (Copernicus, free
   for commercial and non-commercial use with attribution) and/or open
   orthophoto/DOP programs (e.g. Berlin/Brandenburg's open geoportal,
   equivalents for Bavaria/Hesse for the Munich/Frankfurt areas). **Do not
   use Google Maps or Bing tiles** — their terms prohibit exactly this kind
   of caching/derivative-model use, and the human wants this repo
   open-sourceable.
3. **Synthetic low-light relighting:** transform the daytime reference into
   six lighting-condition variants — morning, midday, afternoon, early
   evening, evening, night. Starting point: separate **reflected ambient
   light** (terrain/buildings — dims with time-of-day/ambient level) from
   **active artificial lighting** (streetlamps, windows — stays lit
   regardless of natural ambient level or cloud cover), then apply a
   sensor gain/noise curve approximating the chosen low-light sensor's
   response. This mirrors a rough prototype already built by the human in
   an earlier exploration (an HTML/canvas ambient-illumination simulator) —
   reuse that logic as a v0 starting point, not as a fixed final answer.
   **This relighting method is one of the areas most open to genuine
   improvement by the loop** — if it can find a better sim-to-real
   approach (e.g. learned relighting instead of hand-tuned curves), that's
   exactly the kind of novel result this project is for.
4. **Train/eval split:** held-out crops not seen during training, per area,
   per lighting bucket.

---

## 5. Areas (see §1 — five separate pipeline runs, not one combined model)

Four **development areas** the loop optimizes against, plus one **blind
holdout** it never sees during optimization:

| Area | Role |
|---|---|
| Berlin | Primary / dense urban reference case |
| Prignitz, Brandenburg | Rural extreme — among the lowest population density in Germany, minimal artificial lighting |
| Munich metro | Second major-metro replicate |
| Frankfurt metro | Third major-metro replicate |
| **Hamburg metro** | **Blind generalization holdout.** Structurally distinct from the other four (port city, Elbe river, more spread-out geometry) so it can't be passed by coincidence. |

The rural/urban spread across the four development areas exists to catch a
pipeline that quietly overfits its design choices (relighting curve,
augmentation, model capacity) to one area's texture and lighting density.
The fifth area exists for a different, stricter reason: to catch the
pipeline *itself* being overfit — hardcoded assumptions, quirks the loop
learned to exploit across all four known areas at once — which a worst-case
metric computed only over those four cannot detect, since the loop is free
to adapt to all of them simultaneously.

**Rule: the holdout area's data is never touched by the autoresearch loop's
optimization step.** It is evaluated only as a final, periodic, read-only
check (e.g. once per N kept improvements, or once at the end of a work
session) and its result is logged but must **not** feed back into which
experiments get kept or reverted — see §6 and §7. If the holdout score
diverges badly from the four development areas' worst-case score, that's a
signal the pipeline has a genericity problem worth investigating before
continuing, not something to quietly average away.

---

## 6. Target metric — the single scalar the loop optimizes

**Primary (optimized by the loop):** worst-case (max, not mean) median
position error in meters, across all 6 lighting buckets × the **4
development areas only** (Berlin, Prignitz, Munich, Frankfurt — not the
Hamburg holdout), evaluated on held-out crops within those areas.
**Target: ≤ 20 m.**

Use worst-case rather than mean deliberately — an average can hide a bad
rural or night-time failure behind a good Berlin-daytime score, which is
exactly the failure mode §5's rural/urban spread is designed to catch.

**Reported separately, not optimized (the §5 holdout check):** the same
worst-case-across-lighting-buckets metric, computed on Hamburg, logged
alongside every periodic holdout check. This number must never influence
which experiments the loop keeps or reverts — its only job is to reveal
whether the pipeline generalizes to a bounding box it has never
specifically been tuned against.

**Gating (folds hard constraints into the same scalar):** if a candidate
model's exported artifact doesn't fit the ESP32-P4 deployment envelope
(memory footprint, inference latency within the adaptive-schedule budget),
record the score as failed/worst-possible regardless of accuracy. This
keeps the loop optimizing one number while still enforcing the deployment
constraints from §2.

**Secondary, logged but not directly optimized:** mean error, per-area and
per-lighting-bucket breakdown, exported model size, single-inference
latency and estimated power draw on the target board, and a coverage
metric (% of held-out frames the model returns a confident estimate for at
all — a model that honestly abstains on bad frames is more useful than one
that confidently guesses wrong).

---

## 7. Autoresearch loop architecture

Modeled on Karpathy's `autoresearch` pattern (github.com/karpathy/autoresearch),
**not** an evolutionary/genome search — the point is that the agent can
rewrite actual code (architecture, loss, training loop), not just search a
predefined parameter space.

**Structure:**
- A small set of **frozen files** the loop must never modify: the data
  pipeline (§4), the four areas' held-out eval sets, and the scoring script
  that computes §6's metric.
- One (or a small set of) **agent-editable file(s)**: model architecture
  and training procedure.
- **Loop mechanics per experiment:** branch from current best, make one
  focused change, run a short training job, score against §6, and either
  advance (keep the commit) if the score improved or revert if it didn't —
  same keep/revert discipline as Karpathy's design.
- **Compute:** one GPU per experiment run. The human has RunPod.io credits
  available — the bootstrap should make it straightforward to point a run
  at a RunPod instance, but this doesn't need to be fully automated
  (spin-up/tear-down) in v1; a documented manual step is fine to start.

**Full lineage tracking (hard requirement, not optional):**
Every experiment round must be fully reconstructable after the fact —
not just a metric number in a CSV row. Concretely:
- **Git**: one commit per kept improvement (Karpathy-style), so the code
  history *is* the research trail.
- **SQLite**: one row per experiment — timestamp, git commit hash, area,
  a description of what changed and why, every metric from §6 (primary,
  secondary, per-area/per-bucket breakdown), and paths to any generated
  artifact files for that run.
- **Self-refreshing HTML gallery**: rendered from the SQLite log, showing
  per experiment the synthetic low-light training samples used and a
  per-area error heatmap image — so a human can visually sanity-check
  results, not just read numbers. This combination (SQLite + self-refreshing
  HTML gallery + lineage tracking) mirrors a pattern the human has used
  before in a separate project; if their actual implementation differs
  from what you scaffold here, expect it to be revised after the fact —
  build a clean, reasonable version now rather than blocking on it.

---

## 8. Your job in this session (Phase 1 — bootstrap only)

1. Scaffold the repo: frozen data pipeline (§4) built as a **general
   bbox-parameterized system** (§0), proven by running it unmodified
   against at least Berlin and one other area — not just implemented once
   for Berlin and assumed to generalize. Also scaffold a first
   trivial/naive baseline model + training script, the scoring script
   (§6, including the separate holdout-check path for Hamburg per §5),
   the SQLite schema, the HTML gallery template, and the bash loop script
   described in §7 (not yet running it repeatedly).
2. Run one baseline experiment end-to-end to prove the harness works:
   fetch → relight → train (even badly) → score → log to SQLite → render
   gallery → commit.
3. Write a README explaining how to run the bash loop separately (Phase 2,
   run by the human afterward, not by you in this session).
4. Do **not** attempt to hit the §6 target yourself, and do not run more
   than the one proving experiment — that's the autoresearch loop's job,
   invoked separately.

---

## 9. Open items — resolve during bootstrap, or flag clearly if you can't

- **ESP32-P4 hardware validation**: confirm a specific low-light MIPI
  camera module is actually available and documented-compatible with the
  P4's MIPI-CSI before assuming this hardware choice is final. If you
  can't verify this with confidence, flag it explicitly in the README
  rather than silently proceeding as if it's settled.
- **From-scratch vs. permissively-licensed pretrained init** (§3) — the
  loop's call; log which was tried in each experiment's SQLite row.
- **Unified vs. dispatcher+specialist models** (§3) — the loop's call.

---

## 10. Explicitly out of scope for this project

These were explored and deliberately set aside — don't let the loop wander
into them:
- Optical-flow / rangefinder sensor fusion (§2 assumes vision-only fixes).
- Star-tracker / celestial navigation.
- Thermal or SWIR imaging as the primary sensor.
- Streetlight-constellation matching as a standalone fallback method
  (interesting, but a different system from this one).
