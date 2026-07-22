"""Generate runs/pending_experiment.json for session iter5 (exp 25 design):
convergence-scaled training — 3x optimizer steps + cosine LR anneal.

The SVG is derived from exp 20's kept figure (same inference path, drawn in
ink): exp 20's red training-data elements are demoted to training-amber
(now-unchanged machinery) and the ONE new red element is added — an LR
schedule inset + description. Red = only what THIS experiment changes.
"""
import json
import re
from pathlib import Path

svg = Path("/tmp/exp20_svg.svg").read_text()

# 1. Drop exp 20's red right-side description block (6 <text> lines).
block = re.search(r"<text x='400' y='424'.*?demands\.</text>", svg, re.S)
assert block, "exp20 red text block not found"
svg = svg.replace(block.group(0), "")

# 2. Demote every remaining exp-20 red element (fresh-draw dots, leader,
#    captions) to training-amber — that mechanism is kept, not changed here.
assert svg.count("#8c2f1f") > 0
svg = svg.replace("fill='#8c2f1f'", "fill='#8a6a1e'")
svg = svg.replace("stroke='#8c2f1f'", "stroke='#8a6a1e'")
assert "#8c2f1f" not in svg

# 3. The third epoch box now reads "… epoch 24" — the 3x extension is the
#    change, so this label is red.
old_lab = ("<text x='250' y='452' font-family='Palatino,Georgia,serif' "
           "font-size='10.5' fill='#8a6a1e' font-weight='600' "
           "text-anchor='middle'>… epoch 8</text>")
assert old_lab in svg
svg = svg.replace(old_lab, old_lab.replace("epoch 8", "epoch 24")
                                 .replace("#8a6a1e", "#8c2f1f"))

# 4. New elements: LR-schedule inset (axes, amber constant-LR-with-hard-stop,
#    red cosine glide over the 3x-longer run) + red description block.
new = (
    "<path d='M 362,384 V 440 H 558' fill='none' stroke='#9b998c' stroke-width='1'/>"
    "<text x='352' y='392' font-family='Palatino,Georgia,serif' font-size='8.5' "
    "fill='#9b998c' font-weight='400' text-anchor='end' font-style='italic'>LR</text>"
    "<line x1='362' y1='396' x2='427' y2='396' stroke='#8a6a1e' stroke-width='1.2' "
    "stroke-dasharray='4 3'/>"
    "<line x1='427' y1='396' x2='427' y2='439' stroke='#8a6a1e' stroke-width='0.8' "
    "stroke-dasharray='2 3'/>"
    "<text x='460' y='376' font-family='Palatino,Georgia,serif' font-size='8.5' "
    "fill='#8a6a1e' font-weight='400' text-anchor='middle'>before: constant LR, "
    "hard stop at epoch 8</text>"
    "<path d='M 362,396 C 415,399 455,430 556,439' fill='none' stroke='#8c2f1f' "
    "stroke-width='1.6'/>"
    "<text x='460' y='456' font-family='Palatino,Georgia,serif' font-size='8.5' "
    "fill='#8c2f1f' font-weight='400' text-anchor='middle'>now: cosine glide to "
    "zero across a 3× longer run</text>"
    "<text x='580' y='414' font-family='Palatino,Georgia,serif' font-size='10.5' "
    "fill='#8c2f1f' font-weight='600' text-anchor='start'>convergence-scaled "
    "training — 3× the steps, annealed to zero</text>"
    "<text x='580' y='428' font-family='Palatino,Georgia,serif' font-size='9.5' "
    "fill='#8c2f1f' font-weight='400' text-anchor='start'>The fresh-draw sampler "
    "(kept, left) made memorizing crops useless — but the</text>"
    "<text x='580' y='440' font-family='Palatino,Georgia,serif' font-size='9.5' "
    "fill='#8c2f1f' font-weight='400' text-anchor='start'>schedule still stops at "
    "8 passes, loss still falling, LR never lowered.</text>"
    "<text x='580' y='452' font-family='Palatino,Georgia,serif' font-size='9.5' "
    "fill='#8c2f1f' font-weight='400' text-anchor='start'>A probe shows pure "
    "underfit: train crops now localize no better than</text>"
    "<text x='580' y='464' font-family='Palatino,Georgia,serif' font-size='9.5' "
    "fill='#8c2f1f' font-weight='400' text-anchor='start'>eval crops (~1 km both). "
    "This run trains 24 fresh-draw passes with the</text>"
    "<text x='580' y='476' font-family='Palatino,Georgia,serif' font-size='9.5' "
    "fill='#8c2f1f' font-weight='400' text-anchor='start'>LR gliding down a cosine "
    "— the same sampler, finally trained to converge.</text>"
)
svg = svg.replace("</svg>", new + "</svg>")

stages = [
    {"name": "Camera frame", "detail": "128×128 px aerial crop, one of 6 simulated lighting conditions", "changed": False},
    {"name": "Rotation fan", "detail": "the crop is copied into its four 90° turns (exact pixel re-arrangements, no blur) and all four copies travel through the same network side by side", "changed": False},
    {"name": "Feature extractor", "detail": "ImageNet-pretrained MobileNetV3-Small (first 9 blocks, 190k params), gently fine-tuned", "changed": False},
    {"name": "Layout summary", "detail": "a slim extra layer condenses the 8×8 feature grid into a 512-number code that remembers what sits where in the crop; the texture average (48 numbers) is kept alongside", "changed": False},
    {"name": "Lighting gate", "detail": "a tiny network reads the crop's own average brightness together with the 48-number texture summary and outputs one number: how night-like is this shot?", "changed": False},
    {"name": "Probability map", "detail": "two scorers read each of the four turned copies and the gate blends their per-cell guesses; the four resulting heat maps are averaged into one voted map — a location only stays hot if it wins from every direction", "changed": False},
    {"name": "Decode", "detail": "the heat map's contrast is turned up first (peaks boosted, faint background suppressed), then the answer is the balance point of the sharpened map — committing to the strongest hotspot instead of averaging every faint guess across the whole city", "changed": False},
    {"name": "Confidence", "detail": "the model inspects the shape of its own heat map — one crisp hotspot means sure, a washed-out smear means unsure — and below a tuned bar it says 'no fix' instead of guessing; the bar is set so it still answers at least 40% of the time in every lighting condition", "changed": False},
    {"name": "Output", "detail": "(lat, lon, confidence)", "changed": False},
    {"name": "Training signal", "detail": "unchanged — same position and confidence grading as before", "changed": False, "train_only": True},
    {"name": "Training data", "detail": "unchanged — every pass draws a fresh set of 6,000 places per lighting condition (new headings, new simulator-roll mix), so distinct places are seen only once or twice each and memorizing individual crops doesn't pay", "changed": False, "train_only": True},
    {"name": "Training schedule", "detail": "NEW: the study run is three times longer (24 fresh-draw passes instead of 8) and the size of each learning step glides smoothly down to zero along a cosine — the model finishes learning and settles, instead of stopping mid-stride with big, noisy updates", "changed": True, "train_only": True},
]

exp = {
    "title": "Convergence-scaled training: 3× optimizer steps with cosine LR decay under the kept fresh-draw sampler",
    "category": "training",
    "hypothesis": (
        "The binding constraint is no longer the held-out-location generalization gap — it is plain "
        "underfitting, created as a side effect of kept exp 20 and never addressed because the training "
        "schedule has been frozen since bootstrap. Evidence from a fresh read-only probe of the kept exp-20 "
        "model (runs/_probe_iter5_evalcells.py): the ~3× train-vs-eval gap that exps 18/19/22/23/24 all "
        "attacked is GONE — berlin midday train-split 1014 m vs eval-split 1017 m unfiltered median, "
        "prignitz midday 580 vs 673 m (pre-exp-20 probes measured 267–400 m on train). Exp 20's "
        "single-exposure fresh draws removed memorization as a fitting strategy, which turned the 8-epoch "
        "constant-LR budget — sized in the bootstrap era, when 8 passes over one frozen tensor sufficed to "
        "memorize — into a truncation: the training loss is still descending ~0.065/epoch at cutoff "
        "(berlin 6.29→5.11 over 8 epochs, no plateau) at a never-decayed Adam LR (head 1e-3, trunk 1e-4), "
        "and unfiltered errors are flat-mediocre on BOTH splits (train-split medians 580–1889 m) — the "
        "signature of an underconverged model, not a transfer failure. This also reinterprets the three "
        "consecutive reverts (22, 23/24): their auxiliary losses competed for the same ~4,500 undertrained "
        "optimizer steps, diluting an optimization budget that was already the bottleneck. Per the plateau "
        "rule this leaves that mechanism family entirely for training-scale — the one plateau-list family "
        "never tried (exp 7 scaled data, never optimization). The same probe also tested and rejected an "
        "output-side suspicion: the decode does NOT structurally avoid the never-trained eval-block cells "
        "(P(decode in eval block) = 0.13–0.21 vs 0.20 base rate), so a head redesign is not the leading "
        "term. The change: 3× the optimizer steps (24 fresh-draw epochs from the harness's --epochs 8) "
        "with per-step cosine LR annealing to zero, so the kept sampler is finally trained to convergence — "
        "near-full coverage of the ~45k train locations per bucket, each still seen only ~1–2×, and a "
        "settled endpoint instead of a noisy constant-LR stop."
    ),
    "method": (
        "model/train.py ONLY (model/model.py untouched — inference path, losses, decode, calibration, "
        "export all identical). (1) Module constant EPOCH_MULT = 3; train_area runs total_epochs = epochs × "
        "EPOCH_MULT sampled epochs (harness passes --epochs 8 → 24), with the per-epoch fresh-draw "
        "sample_epoch and the epoch_rng = default_rng([seed, epoch]) formula unchanged — epochs 8..23 "
        "automatically get fresh independent draws. (2) torch.optim.lr_scheduler.CosineAnnealingLR stepped "
        "once per optimizer step, T_max = precomputed total step count (6 buckets × "
        "min(max_crops_per_bucket, n_train_crops) crops/epoch, batch 64, × total_epochs), eta_min 0 — "
        "both param groups (trunk 1e-4, head 1e-3) anneal proportionally. Per-epoch memory profile is "
        "byte-identical to the kept baseline (sample_epoch untouched — the exp-23 OOM lesson); wall time "
        "≈3× (~19 → ~58 min for the 4 parallel areas)."
    ),
    "expected_outcome": (
        "If optimization is binding, the primary worst-case median improves 10–25%: 839.12 → ~630–760 m, "
        "with final train losses ≥0.25 nats below the epoch-8 values (berlin 5.11, prignitz 4.77) and "
        "train-split unfiltered medians dropping well below today's 580–1889 m. Falsification is equally "
        "informative: if final losses drop ≥0.25 nats but the metric moves <5%, optimization is exonerated "
        "and capacity/architecture becomes the demonstrated next bottleneck — a clean fork for the next "
        "iteration."
    ),
    "init_strategy": "pretrained:mobilenet_v3_small IMAGENET1K_V1 features[0..8] (torchvision, BSD-3) — unchanged",
    "eli5": (
        "The previous improvement gave the model fresh flashcards every study pass so it could no longer "
        "cram answers — but we kept ringing the end-of-class bell at the same early time, set back when "
        "cramming made classes short. Its grades were still climbing when the bell rang. This experiment "
        "simply lets it study three times longer, and — like slowing down smoothly before parking — makes "
        "each learning step gentler toward the end so what it learned settles in place. The model that "
        "flies is completely unchanged; only the length and pacing of school changes."
    ),
    "architecture": {"stages": stages},
    "architecture_svg": svg,
    "implementation_brief": (
        "ALL changes are in model/train.py; model/model.py is NOT touched. Fixed contracts to preserve "
        "verbatim: (a) train.py CLI — --area, --out-dir, --data-dir, --epochs (harness passes 8), "
        "--max-crops-per-bucket (default 6000), --seed; flags, names, defaults unchanged; (b) the ONNX "
        "export contract in model/model.py's docstring — one ONNX per area at <out>/models/<area>.onnx, "
        "input 1x3x128x128 float32 in [0,1], output [[u, v, conf]]; (c) train_info.json append behavior "
        "and the final printed JSON line. Changes, precisely: (1) Add module constant EPOCH_MULT = 3 next "
        "to TRAIN_REALIZATIONS, with a one-line comment: convergence scaling — the harness's --epochs is "
        "an outer budget fixed at bootstrap; the exp-20 fresh-draw sampler needs ~3× the steps to "
        "converge (loss still falling ~0.065/epoch at the old cutoff). (2) In train_area(...), right after "
        "crops = list_crops(...): total_epochs = epochs * EPOCH_MULT; n_per_epoch = 6 * "
        "min(max_crops_per_bucket, len(crops)) (exactly what sample_epoch yields: 6 lighting buckets, one "
        "replace=False draw of that size each); steps_per_epoch = (n_per_epoch + 63) // 64; total_steps = "
        "steps_per_epoch * total_epochs. (3) After the existing two-group Adam construction (groups and "
        "base LRs 1e-4/1e-3 unchanged): sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, "
        "T_max=total_steps, eta_min=0.0). (4) Change the epoch loop to for epoch in range(total_epochs), "
        "keeping epoch_rng = np.random.default_rng([seed, epoch]) EXACTLY as-is, and update the two print "
        "statements to show epoch+1/total_epochs. (5) Inside the minibatch loop call sched.step() "
        "immediately after opt.step() — once per optimizer step, nowhere else. (6) Do NOT modify "
        "sample_epoch, prepare_realizations, calibrate_conf_shift, the export, or any memory handling — "
        "per-epoch tensor sizes and the ~3.6 GB transient sampling peak must stay identical to the kept "
        "baseline (four areas train in parallel inside a constrained cgroup; exp 23 died by exceeding it). "
        "(7) Extend the info dict with 'total_epochs_run': total_epochs, 'epoch_mult': EPOCH_MULT, and "
        "'lr_schedule': f'cosine-per-step to 0 over {total_steps} steps'; keep the existing 'epochs': "
        "epochs field as the CLI value. (8) Add a short exp-25 note to train.py's module docstring "
        "(convergence-scaled training: probe showed train≈eval ≈ 1 km unfiltered and loss still falling "
        "at cutoff — 3× steps + cosine anneal to zero). Nothing else changes."
    ),
}

out = Path("/workspace/low-light-geolocalization-autoresearch/runs/pending_experiment.json")
out.write_text(json.dumps(exp, indent=2, ensure_ascii=False))
print("wrote", out, len(svg), "svg chars")
