# Infrastructure journal

The compute story of this project, in eras. Each era notes what ran where,
what it cost, and why we moved on — so that any number in
`experiments.sqlite` can be read against the hardware that produced it
(`duration_s` is only comparable within an era).

## Era 1 — M1 MacBook Air (bootstrap + experiments 1–10, 2026-07-20 → 21)

Everything — headless agent, training, scoring — ran on a fanless M1
MacBook Air (16 GB), training on MPS. Measured behavior over the first ten
experiments:

- **Agent design phase:** ~7–12 min per iteration, flat (LLM-API-bound; a
  GPU changes nothing here). Billed $2.40–$5.96/iteration via API.
- **Train + score:** ~13 min at bootstrap (4 areas × ~200 s), growing to
  ~40 min once experiment 7 scaled training data 7.5× and experiments 8/10
  grew the model. Whole iterations ran 20–50 min.
- **Thermal throttling is real and visible in the lineage:** iteration 4's
  `train_info.json` shows frankfurt at 1120 s while its three sibling areas
  took ~200 s each — the fanless Air throttled mid-iteration. Within-era
  `duration_s` noise of this size is expected.

The loop kept rewarding more data and more capacity, so this was only
going to get worse. End of era: best 2299.74 m (experiment 10).

## Era 2 — RunPod Secure Cloud RTX 4090 (2026-07-21 → )

The **entire loop** moved to a RunPod pod: the loop is strictly sequential
and restart-safe, so splitting agent-local/train-remote would add moving
parts for no win. The laptop's only jobs now are provisioning, sync, and
pulling lineage back — all via `infra/runpod.sh`.

| | |
|---|---|
| Pod | Secure Cloud, 1× RTX 4090 (24 GB), ≥8 vCPU, ≥30 GB RAM |
| Image | `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04` |
| Disk | 50 GB volume at `/workspace` (survives `stop`, not `terminate`) |
| Price | $0.69/hr while running; ~$5/mo volume |
| Repo | `/workspace/low-light-geolocalization-autoresearch`, venv with `--system-site-packages` (reuses image torch 2.4.1+cu124) |
| Agent auth | `CLAUDE_CODE_OAUTH_TOKEN` (subscription via `claude setup-token`), passed at loop launch — **not** stored on the pod or in RunPod's console env |

**Data policy — important:** `data/` is **rsynced up, never re-fetched** on
the pod. The held-out eval crops are part of the frozen harness; a re-fetch
could silently produce different tiles and make scores incomparable across
eras. `infra/runpod.sh sync-up` enforces this by construction.

**Known measurement caveats of the era switch, logged once here:**

- The latency gate (`pipeline/score.py`, 250 ms single-thread host-CPU
  proxy) now measures an EPYC server core instead of an M1 core. Current
  models sit far under the budget either way; if a future model runs near
  the gate, re-check on the actual target before trusting a pass/fail flip.
- CUDA vs MPS training is not bit-identical. The first pod iteration
  compares against an M1-scored best — an accepted one-time discontinuity.
- LLM cost per iteration moved from ~$4 API billing to ~$0 marginal
  (subscription token). GPU cost is ~$0.14/iteration at observed speeds —
  for 100 experiments, GPU spend is $15–30; the LLM was always the
  dominant cost line.

### Reproduce from nothing

```bash
# laptop: .env with RUNPOD_API_KEY (+ CLAUDE_CODE_OAUTH_TOKEN for launch)
infra/runpod.sh up          # Secure 4090, ssh key injected
infra/runpod.sh status      # wait until ssh endpoint appears
infra/runpod.sh sync-up     # repo + data/ (~4.7 GB); never the DB
infra/runpod.sh seed-db     # one-time: seed the fresh pod's experiments.sqlite
                            # (guarded — refuses if the pod already has one)

# pod one-time setup (infra/runpod.sh ssh):
apt-get update && apt-get install -y rsync tmux
cd /workspace/low-light-geolocalization-autoresearch
python3.11 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
curl -fsSL https://claude.ai/install.sh | bash
git config --global user.email you@example.com
git config --global user.name  "you (autoresearch pod)"
git config --global --add safe.directory /workspace/low-light-geolocalization-autoresearch
```

### Operate

```bash
# launch (on the pod, inside tmux so ssh drops don't kill the loop):
tmux new -s loop
CLAUDE_CODE_OAUTH_TOKEN=... ./autoresearch/loop.sh 25
# models per task (defaults; override via env): DESIGN_MODEL=claude-fable-5
# does the creative/strategic design, IMPL_MODEL=claude-sonnet-5 implements
# the brief. Both are persisted per experiment (agent_model_design/_impl
# columns). Policy: never Opus.

# watch from the laptop:
infra/runpod.sh ssh         # then: tmux attach -t loop
# or: sqlite3 over ssh — see README "Watch progress"

# after a batch:
infra/runpod.sh pull        # runs/ + sqlite + state/ back, ff-merge pod commits
infra/runpod.sh stop        # stop paying $0.69/hr; volume persists
infra/runpod.sh terminate   # only when truly done — destroys the volume
```

Graceful stop of a running loop: `touch state/stop` on the pod (finishes
the current iteration, then exits) — same mechanism as local.

**Iteration anatomy (since 2026-07-21):** each iteration is a two-stage
agent (design → implementation, separate models, both recorded in the DB)
followed by **parallel** training of all 4 areas (independent per-area
out-dirs merged afterward — `train.py`'s `train_info.json` append is not
concurrency-safe, so areas never share an out-dir), then scoring. Every
run dir carries `timings.json` with the per-phase breakdown
(agent_design_s / agent_impl_s / train_wall_s / score_s / samples_s /
holdout_s / gallery_s / total_s) — measured on the 4090 the design phase
dominates (~15–20 min LLM vs ~3–4 min parallel training), which is why a
bigger GPU is NOT the lever for faster iterations. TODO(gallery): render
this breakdown in the experiment-detail view.

### Persistence — every experiment survives the pod

Since 2026-07-21 the loop's final step each iteration commits the
**complete iteration record** — `runs/<id>/` (experiment design, agent
result, models, heatmaps, samples, any holdout check),
`experiments.sqlite`, `state/` — and pushes to GitHub, for kept **and**
reverted experiments alike. A reverted experiment's model-code diff is
discarded by design, but its record now lives in git, not just on
whatever disk ran it. Push failures are non-fatal (retried implicitly
next iteration).

Mechanics: binary artifacts (`runs/**/*.png`, `runs/**/*.onnx`, `*.pt`)
go through **Git LFS** (~30 MB/iteration would sink plain git); JSON +
SQLite stay plain. The pod pushes over a **write-scoped deploy key**
(`~/.ssh/id_ed25519` on the pod, registered on the repo as
"lowlight-autoresearch pod"), with a global `insteadOf` rewriting the
https origin to ssh. `data/` and `gallery/` stay untracked (regenerable).

**LFS quota:** GitHub's free tier is 1 GB LFS storage / 1 GB/mo
bandwidth. At ~30 MB/iteration a $5/mo 50 GB data pack becomes necessary
around experiment ~30 — buy it before the loop starts failing pushes.

### Development workflow — changing code while the pod is "production"

Two writers exist: the **loop on the pod** (commits kept experiments,
only ever touches `model/`) and **you locally** (harness, pipeline,
infra, docs). The rule that keeps git history linear: **one side writes
at a time, and `pull` before `sync-up` — always.** `sync-up` enforces
this: it refuses to run if the pod holds commits local main lacks.

Rolling out a local change:

```bash
# 1. stop the loop at an iteration boundary (on the pod):
infra/runpod.sh ssh   # then inside: touch <repo>/state/stop
# 2. bring the pod's results + kept commits home:
infra/runpod.sh pull  && git push
# 3. edit + verify locally — MPS still works for a cheap end-to-end proof:
EPOCHS=1 SKIP_AGENT=1 ./autoresearch/loop.sh 1   # harness smoke, no agent
# 4. commit locally, roll out, relaunch:
git commit … && infra/runpod.sh sync-up
infra/runpod.sh ssh   # tmux new -s loop; CLAUDE_CODE_OAUTH_TOKEN=… ./autoresearch/loop.sh 25
```

Caveats: (a) **frozen-file changes are era events** — anything touching
`pipeline/` or scoring makes metrics incomparable with earlier rows, so
note it here and expect a baseline re-seed, as in the bootstrap era
resets. (b) **The pod's `experiments.sqlite` is production and flows one
way only** (pod → laptop via `pull`; `sync-up` excludes it, `seed-db` is
the guarded one-time exception for a fresh pod). Local smoke rows from
`SKIP_AGENT=1` runs therefore never pollute the permanent lineage — the
next `pull` simply replaces the local DB, discarding them along with any
other local-only DB edits. DB fixes/migrations (e.g. `archive/`'s figure
scripts) are run *on the pod*, then flow back via `pull`. (c) GitHub is
the off-site archive: `git push` after every `pull` so kept experiments
land there.

## Deployment assumptions & known sim-to-real gaps (2026-07-21)

What the frozen harness covers and deliberately does not, re: viewpoint —
written down so nobody flies this with wrong expectations:

- **Heading (yaw): covered.** Eval crops carry deterministic per-crop
  0–360° rotations (`pipeline/dataset.py` — heading-agnostic eval from
  day 1); training uses random rotation augmentation about the crop
  center. The §6 metric already measures heading-invariant accuracy.
- **Camera tilt (off-nadir): NOT modeled.** Orthophotos are nadir; no
  perspective augmentation exists. A freestyle frame pitches 10–25°+ in
  cruise, so real frames are perspective-distorted vs training data.
  Intended mitigation (deployment-side, pipeline unchanged): IMU-known
  attitude → homography rectification to synthetic nadir on the P4, plus
  attitude-gating fixes to low-pitch moments (the adaptive fix schedule
  already allows choosing when to fix). Perspective augmentation in
  training is a possible loop experiment (approximate — ignores building
  parallax).
- **Altitude/scale: fixed at ~1 m/px (≈100 m AGL).** Real AGL variation
  changes ground sampling distance; mitigation is baro-based rescale of
  the frame to 1 m/px before inference, same rectification step.

## Publishing roadmap (planned, not yet built)

As results come in, two **separate, shareable HTML pages** will be written
in addition to the working gallery:

1. **Results page** — the headline numbers and their honest breakdown:
   per-area/per-bucket error tables, the metric-over-experiments trajectory,
   holdout checks vs development worst-case, heatmaps.
2. **Approach & techniques page** — the research method itself: the frozen
   harness / agent-editable split, pre-registration discipline,
   keep/revert lineage, what the loop actually discovered (which
   experiment families worked, which reverted, and why).

Both should render from `experiments.sqlite` + `runs/` artifacts the same
way `autoresearch/gallery.py` does (single source of truth, no hand-copied
numbers), and follow the same Tufte-style visual vocabulary as the
existing gallery and the author's prior research pages.

**Publish target: public GitHub Pages** (built 2026-07-21, dormant until
the repo goes public), in the style of the author's
[airloom](https://github.com/akaalias/airloom) page.

**Parity contract:** `infra/build_site.sh` is the single site assembler —
run it locally and open `_site/gallery/index.html` to preview *exactly*
what deploys; `.github/workflows/pages.yml` runs the same script on every
push. All presentation logic lives in `autoresearch/gallery.py` (one
renderer for local + live); the build script only packages its output
next to `runs/` PNGs/JSON with their existing relative paths. Change the
renderer → verify locally → push → live pages update. The workflow's
build job runs on every push as a render smoke-test; the deploy job is
gated on the repo variable `PAGES_ENABLED=true`.

**Going public — the switch list:** (1) set repo visibility public,
(2) Settings → Pages → Source: GitHub Actions, (3) set repo variable
`PAGES_ENABLED=true`, (4) buy the LFS data pack. Licensing is ready:
MIT `LICENSE` for code + NOTICE for imagery-derived artifacts; both
gallery pages carry the required attribution footer (dl-de/by-2-0,
CC BY 4.0, Copernicus, torchvision BSD-3).

**Known ceilings:** GitHub Pages sites have a ~1 GB soft limit — the
PNG-only site is ~340 MB at experiment 10 and grows ~25 MB/experiment,
so expect to prune (e.g., full artifacts for kept experiments only)
around experiment ~35. LFS in CI goes through the Actions cache, so only
each iteration's new objects hit the bandwidth quota. `data/` (4.3 GB
imagery) stays out of git and out of the site; anyone can regenerate it
— README "Quickstart" + "Adding a new deployment area" document the
credential-free fetch/relight path for arbitrary bboxes.
