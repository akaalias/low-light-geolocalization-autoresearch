# FORCED RESEARCH DIRECTION — THIS EXPERIMENT ONLY

Whatever the pivot/streak notes below suggest, this experiment is **pre-assigned**
one direction: an **ACE / DSAC-style dense scene-coordinate regression with a
robust geometric solve**, replacing the current global image→coordinate regressor
(APR-style, plateaued). A previous attempt with this design was undertrained at a
tiny budget; this run gets a real training budget, so make the design one that
*benefits* from it.

Your design for THIS experiment MUST do all of the following:

1. **Replace the trunk.** No MobileNet, no carried-over champion backbone. A
   compact from-scratch conv encoder producing a *spatial grid* of features over
   the frame (e.g. 16×16 cells), not a single global vector.

2. **Regress a ground coordinate PER CELL (dense scene-coordinate regression),**
   plus a per-cell confidence / log-variance. Each cell predicts the (u, v) map
   coordinate it observes — many local correspondences, not one global guess.

3. **Aggregate with a ROBUST consensus — NOT a plain mean.** Use a robust,
   *differentiable* inlier-weighted consensus (confidence/soft-inlier weighting,
   iteratively-reweighted least squares, or a differentiable-RANSAC-style soft
   vote) so featureless / ambiguous cells are down-weighted. A hard consensus may
   be used at inference; keep training aggregation differentiable. Give the model
   enough capacity that more epochs/crops actually help it converge.

4. **Confidence → honest abstention** when few cells agree (a signal-free frame),
   so the model abstains rather than guessing (§6 coverage rewards this).

**Why:** scene-coordinate regression (DSAC/DSAC*/ACE) memorizes an area into a
compact scene-specific network and recovers position by robust geometric
consensus over many local correspondences — far more accurate than global pose
regression, and ACE-class nets are tiny/fast enough for the ESP32-P4. This is the
deliberate move to the geometry-based family the spec (§3) names.

Stay within the frozen harness and the ESP32-P4 deployment gates; do not touch
frozen files. Pre-register the hypothesis / method / architecture stages as usual.
