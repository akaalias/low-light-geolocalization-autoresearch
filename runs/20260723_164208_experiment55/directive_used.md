# FORCED RESEARCH DIRECTION — THIS EXPERIMENT ONLY

Whatever the pivot/streak notes below suggest as a "family," this experiment is
**pre-assigned** one specific direction: an **ACE / DSAC-style dense
scene-coordinate regression with a robust geometric solve**, deliberately
replacing the current global image→coordinate regressor (which behaves like
Absolute Pose Regression and has plateaued).

Your design for THIS experiment MUST do all of the following:

1. **Replace the trunk.** No MobileNet, no carried-over champion backbone.
   Build a compact from-scratch conv encoder that outputs a *spatial grid* of
   features over the frame (e.g. H'×W' cells), not a single global vector.

2. **Regress a ground coordinate PER CELL (dense scene-coordinate
   regression).** Each cell predicts the (u, v) map coordinate it is looking at
   — i.e. "this patch is looking at *this* spot on the memorized area" — plus a
   per-cell confidence / log-variance. This is the ACE/DSAC idea: many local
   correspondences, not one global guess.

3. **Aggregate with a ROBUST consensus — NOT a plain mean.** A plain mean of the
   per-cell coordinates was exactly the weakness of the earlier per-patch attempt
   (experiment 4) and must not be repeated. Use a robust, *differentiable*
   inlier-weighted consensus: confidence/soft-inlier weighting, iterative
   reweighted least squares, or a differentiable-RANSAC-style soft vote, so that
   featureless / ambiguous cells (forest canopy, water, low-texture) are
   down-weighted instead of dragging the position fix. A hard RANSAC/consensus
   solve may be used at inference; keep the training-time aggregation
   differentiable.

4. **Confidence → honest abstention.** Overall confidence must collapse when few
   cells agree (a signal-free frame), so the model abstains rather than guessing
   — this is desirable, and §6's coverage metric rewards honest abstention.

**Why (prior art to reuse):** scene-coordinate regression (DSAC / DSAC* / ACE)
memorizes an area into a compact scene-specific network and recovers position by
robust geometric consensus over many local correspondences — far more accurate
than global pose regression, and ACE-class networks are tiny and fast enough for
the ESP32-P4 budget. The current champion is APR-style and has stalled at ~1 km;
this is the deliberate move to the geometry-based family the spec (§3) names.

Stay within the frozen harness and the ESP32-P4 deployment gates; do not touch
frozen files. Pre-register the hypothesis / method / architecture stages for
this specific design as usual.
