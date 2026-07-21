# The Library — human inspiration notes

Maintained by the human researcher. These notes do not fix your answer and
you are free to ignore them — pick one up only when it genuinely fits your
read of the experiment history. If you build on an entry, say so in your
hypothesis. Entries are inspiration, not instructions; you own the design.

---

## L1 · Canonicalize the night: denoise toward the clean render (2026-07-21)

The worst-case input is the noisy night frame. What if the hard part —
seeing through gain noise and washed-out color — were handled explicitly,
so the localizer works on something closer to a clean, high-contrast
rendering of the ground?

Unfair advantage of this codebase: the frozen relighting sim provides
**pixel-aligned supervised pairs for free** — for any training location you
can load both the clean daytime reference crop and its rendered night
frame (same cx/cy through `pipeline.dataset`, different lighting bucket, or
the reference image itself). No labeling cost, unlimited pairs.

Two flavors, different deployment economics:

- **A. Explicit pre-model**: a small translator (tiny U-Net-ish) runs
  first; the localizer sees the cleaned image. It flies, so it spends the
  4 MiB / 250 ms budget — keep it tiny.
- **B. Training-only reconstruction auxiliary** (the budget-free version):
  keep one deployed model, but during training attach a decoder that must
  reconstruct the clean daytime render from the encoder's features, then
  discard it. Forces the encoder to internally canonicalize lighting and
  noise at zero inference cost — lives entirely in the "never flies" lane.

Prior art the idea rhymes with: night→day translation for place
recognition (ToDayGAN-family), denoising pretraining, reconstruction
auxiliaries for robust features.
