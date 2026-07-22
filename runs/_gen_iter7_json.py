"""Generate runs/pending_experiment.json for iter 7: unseen-ground confidence
calibration unlocking the reinstated exp-26 capacity trunk. The figure is
exp 26's validated SVG (same architecture, reinstated) with the calibration
mechanism added in red in the training lane."""
import json
import sqlite3

conn = sqlite3.connect("experiments.sqlite")
svg = conn.execute("SELECT arch_svg FROM experiments WHERE id=26").fetchone()[0]
conn.close()

# --- adapt exp 26's figure -------------------------------------------------
svg = svg.replace("viewBox='0 0 980 340'", "viewBox='0 0 980 372'")
svg = svg.replace(">blocks 9–10 — new<", ">blocks 9–10 — reinstated<")
svg = svg.replace(">int8 FC store — new<", ">int8 FC store — reinstated<")
# extend the ochre training-lane leader down to the relocated note
svg = svg.replace("M 644 186 L 654 186 L 654 310", "M 644 186 L 654 186 L 654 349")

old_note = ("<text x='368' y='316' font-family='Palatino,Georgia,serif' "
            "font-size='9.5' fill='#8a6a1e' font-weight='400' text-anchor='start' "
            "font-style='italic'>training-only lane — unchanged: Gaussian-CE map "
            "target · committed-coord L2 · conf BCE · 24 fresh-draw epochs, "
            "cosine LR → 0</text>")
assert old_note in svg, "exp26 training-lane note not found verbatim"

RED, INK, MUT = "#8c2f1f", "#111111", "#8a6a1e"
F = "Palatino,Georgia,serif"
gx, gy, s, n = 700, 288, 45, 5
cell = s / n
glyph = [f"<rect x='{gx}' y='{gy}' width='{s}' height='{s}' fill='none' "
         f"stroke='{INK}' stroke-width='1.2'/>"]
for i in range(1, n):
    glyph.append(f"<line x1='{gx + i * cell:.0f}' y1='{gy}' x2='{gx + i * cell:.0f}' "
                 f"y2='{gy + s}' stroke='{INK}' stroke-width='0.45' opacity='0.5'/>")
    glyph.append(f"<line x1='{gx}' y1='{gy + i * cell:.0f}' x2='{gx + s}' "
                 f"y2='{gy + i * cell:.0f}' stroke='{INK}' stroke-width='0.45' opacity='0.5'/>")
for (cx_, cy_) in ((1, 1), (3, 3), (4, 0)):
    glyph.append(f"<rect x='{gx + cx_ * cell:.0f}' y='{gy + cy_ * cell:.0f}' "
                 f"width='{cell:.0f}' height='{cell:.0f}' fill='{RED}' fill-opacity='0.45'/>")

new_block = (
    # red dashed leader: Confidence caption -> held-back-blocks glyph (ends AT it)
    f"<line x1='725' y1='252' x2='725' y2='284' stroke='{RED}' stroke-width='1' "
    f"stroke-dasharray='2 4'/>"
    + "".join(glyph)
    + f"<text x='754' y='302' font-family='{F}' font-size='10.5' fill='{RED}' "
      f"font-weight='600' text-anchor='start'>abstain bar set on held-back ground — new</text>"
    + f"<text x='754' y='315' font-family='{F}' font-size='9.5' fill='{RED}' "
      f"font-weight='400' text-anchor='start'>~10% of train blocks never enter a training draw;</text>"
    + f"<text x='754' y='327' font-family='{F}' font-size='9.5' fill='{RED}' "
      f"font-weight='400' text-anchor='start'>the bar is tuned on ground as unseen as the exam's</text>"
    + f"<text x='368' y='355' font-family='{F}' font-size='9.5' fill='{MUT}' "
      f"font-weight='400' text-anchor='start' font-style='italic'>training-only lane — "
      f"losses and schedule unchanged: Gaussian-CE map target · committed-coord L2 · "
      f"conf BCE · 24 fresh-draw epochs, cosine LR → 0</text>"
)
svg = svg.replace(old_note, new_block)

# --- pre-registration ------------------------------------------------------
exp = {
    "title": "Unseen-ground confidence calibration unlocks the reinstated 3×-capacity trunk",
    "category": "training",
    "hypothesis": (
        "Exp 26's capacity scaling delivered its predicted accuracy gain but was vetoed "
        "solely by the coverage gate: its deployment gates passed (3.09 MB, 4.6 ms) and its "
        "like-for-like medians fell 20–35% (munich morning 536→347 m, frankfurt "
        "evening 798→466 m, prignitz morning 450→350 m), yet 8 of 24 cells dropped "
        "below the 0.2 coverage floor → 1e9. This iteration's forensics isolate why: "
        "calibrate_conf_shift sets the abstention threshold on TRAIN-split crops at locations "
        "the model trained on, and the 3× trunk sharpened the confidence head's "
        "separation between trained-on and unseen ground — calibration-time keep rates "
        "were IDENTICAL between iter 5 and iter 6 (0.40–0.88 per bucket) while conf_shift "
        "leapt from 0.2–0.7 to 2.5–3.6 and eval coverage collapsed from 0.25–0.67 "
        "to 0.08–0.43. A threshold that keeps 40% of visited ground kept only 8–19% of "
        "held-out ground. Calibrating instead on train blocks fenced off from every training "
        "draw measures the confidence distribution the scorer actually faces, so the 40% keep "
        "floor transfers to eval and the real capacity gain becomes scoreable. (The same "
        "mechanism also explains exp 25's near-floor night coverage of 0.25–0.31 — "
        "this fix de-risks every future capacity increase, not just this one.)"
    ),
    "method": (
        "ONE new mechanism in model/train.py — block-held-out confidence calibration: "
        "deterministically hash ~1 in 10 train-split blocks (stable_hash, per area) into a "
        "calibration-only set; the per-epoch fresh-draw sampler uses only crops whose 182-px "
        "windows touch no calibration block (mirror of the frozen eval-buffer rule, so no "
        "calibration pixel is ever trained on); calibrate_conf_shift draws its 400 crops per "
        "bucket exclusively from calibration-block crops. MIN_KEEP_RATE=0.40, "
        "CAL_CROPS_PER_BUCKET=400, losses, schedule, sampler mechanics unchanged. Alongside, "
        "model/model.py reinstates exp 26's pre-registered architecture verbatim (MobileNetV3-"
        "Small features[:11] with stride/dilation surgery preserving the 8×8 grid; int8 "
        "dynamic quantization of MatMul/Gemm at export), which was refuted only through the "
        "calibration artifact this experiment removes."
    ),
    "expected_outcome": (
        "Eval coverage lands near the 0.35–0.45 design point in every cell (vs "
        "0.085–0.43 in exp 26), clearing the 0.2 floor everywhere. Medians rise relative "
        "to exp 26's deflated-coverage readings but keep most of the capacity gain: predicted "
        "worst-case median 600–750 m vs the 797.91 m best, night cells binding. If exp "
        "26's apparent gain was mostly a selection effect of low coverage, the metric will "
        "land ≈800 m or slightly worse — a clean measurement of capacity at the "
        "designed operating point either way."
    ),
    "init_strategy": "pretrained:mobilenet_v3_small IMAGENET1K_V1 features[0..10] (torchvision, BSD-3)",
    "eli5": (
        "Last round we gave the model a bigger brain and its guesses genuinely got better "
        "— but the result was thrown out on a technicality. The model is allowed to say "
        "'no fix' when unsure, and the rules demand it answers at least 20% of the time. We "
        "tune its shyness bar using places from its own training tour, and the bigger brain "
        "became so much more confident about places it had already visited than about new "
        "ones that the bar landed wildly wrong for new ground: it went nearly silent on the "
        "exam. The fix is to fence off a slice of the map the model never gets to study and "
        "tune the shyness bar there — on ground exactly as unfamiliar as the exam's. Same "
        "bigger brain, bar set honestly."
    ),
    "architecture": {"stages": [
        {"name": "Camera frame",
         "detail": "128×128 px aerial crop, one of 6 simulated lighting conditions",
         "changed": False},
        {"name": "Rotation fan",
         "detail": "the crop is copied into its four 90° turns (exact pixel re-arrangements, no blur) and all four copies travel through the same network side by side",
         "changed": False},
        {"name": "Feature extractor",
         "detail": "ImageNet-pretrained MobileNetV3-Small, first 11 blocks — reinstated from the vetoed round: the deeper extractor's accuracy gain was real (errors fell 20–35% at like-for-like confidence), and its two added blocks still skip the image-shrinking step so the 8×8 grid the rest of the model reads stays intact",
         "changed": True},
        {"name": "Layout summary",
         "detail": "a slim extra layer condenses the 8×8 feature grid into a 512-number code that remembers what sits where in the crop; the texture average (96 numbers) is kept alongside",
         "changed": False},
        {"name": "Lighting gate",
         "detail": "a tiny network reads the crop's own average brightness together with the 96-number texture summary and outputs one number: how night-like is this shot?",
         "changed": False},
        {"name": "Probability map",
         "detail": "two scorers read each of the four turned copies and the gate blends their per-cell guesses into one voted heat map; the scorers' bulky connection tables again fly as compact 1-byte integers (measured cost ~7 m of wobble), freeing the file space that pays for the deeper feature extractor — reinstated from the vetoed round",
         "changed": True},
        {"name": "Decode",
         "detail": "the heat map's contrast is turned up first (peaks boosted, faint background suppressed), then the answer is the balance point of the sharpened map — committing to the strongest hotspot instead of averaging every faint guess across the whole city",
         "changed": False},
        {"name": "Confidence",
         "detail": "the model still inspects the shape of its own heat map and says 'no fix' below a tuned bar — but the bar is NOW tuned on a fenced-off slice of the map the model never trained on, so 'sure enough to answer' means the same thing on new ground as it did in training; last round it was tuned on visited places and the model went nearly silent on the exam",
         "changed": True},
        {"name": "Output", "detail": "(lat, lon, confidence)", "changed": False},
        {"name": "Training signal",
         "detail": "unchanged — same position and confidence grading as before",
         "changed": False, "train_only": True},
        {"name": "Training data",
         "detail": "~10% of the map's training blocks (plus a thin no-peeking ring) are fenced off from every draw and reserved for setting the confidence bar; the fresh 6,000-place draws per lighting condition now come from the remaining ground",
         "changed": True, "train_only": True},
        {"name": "Training schedule",
         "detail": "unchanged — 24 fresh-draw passes with the cosine glide kept from last round",
         "changed": False, "train_only": True},
    ]},
    "architecture_svg": svg,
    "implementation_brief": (
        "Two files change: model/model.py (reinstate exp 26's capacity+quant design exactly) "
        "and model/train.py (the ONE new mechanism: block-held-out confidence calibration). "
        "pipeline/, loop.sh and everything in /FROZEN are off-limits; never read or evaluate "
        "hamburg.\n\n"
        "STEP 0 — pretrained snapshot: model/pretrained/mnv3s_features10.pt already "
        "exists in the working tree (created during iter 6; it holds mobilenet_v3_small "
        "IMAGENET1K_V1 features[:11] state_dict with keys prefixed 'features.'). Verify it "
        "loads; if missing, regenerate with: import torch; from torchvision.models import "
        "mobilenet_v3_small, MobileNet_V3_Small_Weights; m = mobilenet_v3_small(weights="
        "MobileNet_V3_Small_Weights.IMAGENET1K_V1); torch.save({'features.'+k: v for k, v in "
        "m.features[:11].state_dict().items()}, 'model/pretrained/mnv3s_features10.pt'). "
        "Keep mnv3s_features8.pt in place.\n\n"
        "STEP 1 — model/model.py:\n"
        "  a. PRETRAINED_TRUNK_PATH -> Path(__file__).parent / 'pretrained' / "
        "'mnv3s_features10.pt'.\n"
        "  b. _build_pretrained_trunk(): trunk = mobilenet_v3_small(weights=None)."
        "features[:11]; strip the 'features.' key prefix and load_state_dict(strict=True) "
        "exactly as now; THEN apply the dilation surgery (after loading — weight shapes "
        "are unaffected):\n"
        "     dw9 = trunk[9].block[1][0]   # 5x5 depthwise conv of block 9\n"
        "     assert dw9.stride == (2, 2) and dw9.groups == dw9.in_channels\n"
        "     dw9.stride = (1, 1)\n"
        "     dw10 = trunk[10].block[1][0]  # 5x5 depthwise conv of block 10\n"
        "     assert dw10.kernel_size == (5, 5) and dw10.groups == dw10.in_channels\n"
        "     dw10.dilation = (2, 2); dw10.padding = (4, 4)\n"
        "     Update the builder docstring: output is now 96x8x8. NO other TinyLocNet/forward "
        "changes — feat_ch and fmap_hw are probed dynamically, so layout_squeeze, "
        "loc_logits, dark_logits, gate and conf_head all re-width themselves.\n"
        "  c. export_onnx(model, path): export fp32 with the EXACT current torch.onnx.export "
        "call (opset 17, dynamo=False, input_names=['frame'], output_names=['uvc']) but to a "
        "sibling temp file, then (imports inside the function): from onnxruntime.quantization "
        "import quantize_dynamic, QuantType; quantize_dynamic(tmp_path, path, weight_type="
        "QuantType.QInt8, op_types_to_quantize=['MatMul', 'Gemm']). The FINAL "
        "<out>/models/<area>.onnx is the int8 artifact the frozen scorer loads; keep the fp32 "
        "file beside it as <area>_fp32_debug.onnx (forensics only — the scorer reads "
        "<area>.onnx). Do NOT quantize Conv ops: whole-graph ConvInteger was probed and "
        "destroys both accuracy and the latency gate; MatMul/Gemm-only is measured inert "
        "(~0.001 uv) and fast (~4.8 ms).\n"
        "  d. Append a short exp-27 paragraph to the module docstring: exp-26 capacity/quant "
        "design reinstated; it was vetoed by a calibration-transfer artifact, not by its own "
        "hypothesis.\n\n"
        "STEP 2 — model/train.py (the new mechanism):\n"
        "  a. Extend the existing pipeline.dataset import with BLOCK_PX and WINDOW_PX "
        "(stable_hash is already imported from pipeline.common).\n"
        "  b. New constant next to CAL_CROPS_PER_BUCKET: CAL_BLOCK_MOD = 10  # ~1 in 10 "
        "train blocks becomes calibration-only ground, mirroring the eval split's own "
        "block-lattice construction.\n"
        "  c. New module-level helpers:\n"
        "     def _is_cal_block(area, bx, by):\n"
        "         return stable_hash(f'{area}:calblock:{bx}:{by}') % CAL_BLOCK_MOD == 0\n"
        "     def split_fit_cal(area, crops):\n"
        "         half_w = WINDOW_PX // 2 + 1\n"
        "         fit, cal = [], []\n"
        "         for c in crops:\n"
        "             cx, cy = c['cx'], c['cy']\n"
        "             if _is_cal_block(area, cx // BLOCK_PX, cy // BLOCK_PX):\n"
        "                 cal.append(c); continue\n"
        "             bxs = range((cx - half_w) // BLOCK_PX, (cx + half_w) // BLOCK_PX + 1)\n"
        "             bys = range((cy - half_w) // BLOCK_PX, (cy + half_w) // BLOCK_PX + 1)\n"
        "             if any(_is_cal_block(area, bx, by) for bx in bxs for by in bys):\n"
        "                 continue  # buffer crop: neither trained on nor calibrated on\n"
        "             fit.append(c)\n"
        "         return fit, cal\n"
        "     Docstring for split_fit_cal: partitions the train-split crop list so that no "
        "calibration-block pixel is ever seen by a training window — the same buffer rule "
        "pipeline.dataset.list_crops applies around eval blocks; crops whose own block is a "
        "cal block form the calibration set, window-straddling crops are dropped entirely.\n"
        "  d. train_area(): after crops = list_crops(...), add fit_crops, cal_crops = "
        "split_fit_cal(area, crops) and print the three counts once. Use fit_crops everywhere "
        "the sampler used crops: n_per_epoch = 6 * min(max_crops_per_bucket, len(fit_crops)) "
        "and sample_epoch(area, meta, fit_crops, ...). Pass cal_crops to calibration.\n"
        "  e. calibrate_conf_shift(model, area, data_dir, device, rng, cal_crops): replace "
        "its internal meta-load + list_crops lines with the passed cal_crops (the meta local "
        "becomes unused — remove it). Everything else inside is unchanged: 400 crops per "
        "bucket sampled (min-guarded, replace=False) from cal_crops, stored relight render "
        "per bucket, fresh random angles, per-bucket logit quantile at 1 - MIN_KEEP_RATE, "
        "T = min over buckets, conf_shift.fill_ formula, returned dict keys.\n"
        "  f. info dict: set 'init' to 'pretrained:mobilenet_v3_small IMAGENET1K_V1 "
        "features[0..10] (torchvision, BSD-3)' and add 'n_fit_crops': len(fit_crops), "
        "'n_cal_crops': len(cal_crops), 'cal_block_mod': CAL_BLOCK_MOD, "
        "'cal_on_unseen_ground': True.\n"
        "  g. NOTHING else changes: CLI flags (--area --out-dir --data-dir --epochs "
        "--max-crops-per-bucket --seed), EPOCH_MULT = 3 with the per-step cosine anneal to 0, "
        "TRAIN_REALIZATIONS = 3 and prepare_realizations, per-epoch fresh-draw sampling "
        "mechanics, MIN_KEEP_RATE = 0.40, loss_fn, and the two-group optimizer (the new "
        "trunk blocks live in model.features, so they join the 1e-4 trunk-LR group "
        "automatically).\n\n"
        "STEP 3 — smoke test before handing back (no training): build_model(); total "
        "params must be 1,305,002 (trunk 576,464); model.features(torch.zeros(1,3,128,128)) "
        "-> shape (1, 96, 8, 8); split_fit_cal(area, list_crops(...)) on berlin returns "
        "disjoint non-empty sets, len(cal) ~8–12% of total and len(fit) ~70–80%; "
        "export_onnx to a temp dir -> final file ~3,091,446 bytes (assert <= 4*1024*1024); "
        "onnxruntime CPUExecutionProvider (intra_op=1) on zeros(1,3,128,128) float32 -> "
        "output shape (1,3) with u,v in [0,1]; 20-run median latency far below 250 ms "
        "(iter-6 probe measured ~4.8 ms). runs/_probe_iter6_export.py is a working reference "
        "for the surgery + quantized-export + latency lines.\n\n"
        "FIXED CONTRACTS (restated): train.py CLI unchanged; one ONNX per area at "
        "<out>/models/<area>.onnx taking a 1x3x128x128 float32 input in [0,1] and returning "
        "[[u, v, conf]] with u, v normalized map coords and conf in [0,1]; the conf_shift "
        "buffer is exported inside the model; the export must pass pipeline/score.py's "
        "frozen deployment gates (<= 4 MiB, <= 250 ms single-thread host latency proxy); "
        "training and calibration may only use the 'train' split from "
        "pipeline.dataset.list_crops; never modify pipeline/, the eval sets, or anything in "
        "/FROZEN; never touch, read, or evaluate hamburg."
    ),
}

with open("runs/pending_experiment.json", "w") as f:
    json.dump(exp, f, ensure_ascii=False, indent=2)
print("wrote runs/pending_experiment.json; svg bytes:", len(svg))
