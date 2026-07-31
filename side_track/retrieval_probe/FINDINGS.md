# Retrieval/embedding-index feasibility probe — findings (2026-07-30)

## Why

After 60+ autoresearch experiments plateaued around 743m worst-case median
(target 20m), we did a literature review (three parallel research agents:
scene-coordinate/pose-regression prior art, cross-view/retrieval
geo-localization, UAV/low-light-specific systems) to check whether the
core "classify into a 32x32 grid of map cells, no reference imagery
on-device" approach had a known-better alternative.

Verdict from that research: the field's actual high-accuracy results
(University-1652, Sample4Geo, NetVLAD-successors) come from **retrieval
against a stored reference gallery/embedding database** — something our
"map lives entirely in the weights" constraint explicitly rules out.
Database-free methods (PoseNet, DSAC++, ACE, GLACE) are validated at
room/building scale (30-220m scenes), not km-scale. No published system
combines zero-reference-imagery + one compact model + km-scale +
<20-50m accuracy.

Given a ~5MB compact embedding index (not raw imagery) comfortably fits
the "few MB you own" budget, we decided to test — cheaply, before
touching CLAUDE.md or the frozen pipeline — whether embedding + nearest-
neighbor retrieval is even in the right ballpark for this project's data,
using the champion's own pretrained trunk as the encoder backbone.

## What we tested

Isolated side-track script (`probe.py`, this directory), never touching
`model/` or any frozen file. Berlin only, using already-cached local data
(`data/berlin`, `render_cache/berlin`). Protocol: train a small InfoNCE
contrastive projection head on top of the champion's pretrained
MobileNetV3-Small trunk (same-location crops across lighting/heading are
positives), build a retrieval index over train-split locations, evaluate
1-NN error on held-out eval-split crops per lighting bucket — same
worst-case-median-across-buckets metric as `pipeline/score.py`, for a
direct comparison to the 743.1m champion.

| Round | Change from previous | Worst-case median |
|---|---|---|
| 1 | Baseline: batch=64, uniform anchor sampling, single-view index entries | 2699.1m |
| 2 | Batch 64->256 (more negatives/step), confusability-weighted sampling (reused exp-35's own trick), no-replacement batches | 2817.3m |
| 3 | + average 4 views/location in the index (query stays single-view, matching real deployment: only one live frame at inference) | 2696.3m |
| — | **Champion (classification + soft-argmax decode)** | **743.1m** |

Training loss converged to near-zero (~0.03) in **all three rounds**,
regardless of what changed — the consistent signal across three
independently-targeted fixes.

## Conclusion

Three rounds, three different specific hypotheses (negatives too easy →
disproved by round 2; index view-noise → disproved by round 3), zero
movement in the eval number. That consistency is itself informative: the
bottleneck isn't any of the three things we cheaply fixed. What's left is
more fundamental — this scale of training (1200 steps, ~6-7 touches per
location on average across ~45k locations) is far short of what real
retrieval systems use (Sample4Geo-class methods: tens of thousands of
steps, systematic hard-negative mining, not a quick contrastive pass).
Testing that fairly is a real multi-hour-plus engineering investment, not
a cheap probe, and would still require amending CLAUDE.md's no-reference-
imagery constraint first (never done — this was explicitly a pre-decision
feasibility check).

**Recommendation: parked.** Not "retrieval is proven wrong" — the cheap
version of it is proven uncompetitive, three times over, which is enough
signal to not spend more incremental effort here without a real
investment decision. If revisited later, don't repeat rounds 1-3's
mistakes (small batch, single-view index) — go straight to a properly-
scaled training run matching a published recipe (e.g. Sample4Geo's
hard-negative mining approach), and settle the CLAUDE.md amendment
question first since a positive result would be moot without it.

## Artifacts

- `probe.py` — final version (round 3)
- `run_v1_collapsed.log`, `run_v2_biggerbatch.log`, `run.log` (round 3) — raw logs per round
