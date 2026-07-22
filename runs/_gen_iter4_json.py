"""Generate runs/pending_experiment.json for iteration 4 (exp: daytime-redraw
reconstruction auxiliary, library entry L1 flavor B). Reuses exp 22's SVG
inference path verbatim (this change is training-only) and replaces the red
training-lane group with the throwaway decoder chain."""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACC, OCH, INK, MUT, FAINT = "#8c2f1f", "#8a6a1e", "#111111", "#6b6a60", "#9b998c"
FONT = "Palatino,Georgia,serif"

conn = sqlite3.connect(ROOT / "experiments.sqlite")
svg22 = conn.execute("SELECT arch_svg FROM experiments WHERE id=22").fetchone()[0]

CUT = "<circle cx='370' cy='161' r='2' fill='#8c2f1f'/>"
prefix = svg22[: svg22.index(CUT)]


def txt(x, y, s, size=10, color=MUT, w=400, anchor="middle", style=""):
    return (f"<text x='{x:.0f}' y='{y:.0f}' font-family='{FONT}' font-size='{size}' "
            f"fill='{color}' font-weight='{w}' text-anchor='{anchor}' {style}>{s}</text>")


def gridsq(x, y, s, n, color, lw=1.2):
    out = [f"<rect x='{x}' y='{y}' width='{s}' height='{s}' fill='none' "
           f"stroke='{color}' stroke-width='{lw}'/>"]
    for i in range(1, n):
        out.append(f"<line x1='{x + i * s / n:.1f}' y1='{y}' x2='{x + i * s / n:.1f}' "
                   f"y2='{y + s}' stroke='{color}' stroke-width='0.45' opacity='0.5'/>")
        out.append(f"<line x1='{x}' y1='{y + i * s / n:.1f}' x2='{x + s}' "
                   f"y2='{y + i * s / n:.1f}' stroke='{color}' stroke-width='0.45' opacity='0.5'/>")
    return "".join(out)


def kernel_proj(x1, s1, x2, s2, color, yc=460):
    k = max(5, s1 * 0.30)
    kx, ky = x1 + s1 * 0.60, yc - s1 / 2 + s1 * 0.18
    c = max(3, s2 * 0.14)
    cx, cy = x2 + s2 * 0.22, yc - s2 / 2 + s2 * 0.26
    out = [f"<rect x='{kx:.1f}' y='{ky:.1f}' width='{k:.1f}' height='{k:.1f}' "
           f"fill='none' stroke='{color}' stroke-width='0.9'/>",
           f"<rect x='{cx:.1f}' y='{cy:.1f}' width='{c:.1f}' height='{c:.1f}' "
           f"fill='{color}' fill-opacity='0.5' stroke='none'/>"]
    for (px, py) in ((kx, ky), (kx + k, ky), (kx, ky + k), (kx + k, ky + k)):
        out.append(f"<line x1='{px:.1f}' y1='{py:.1f}' x2='{cx + c / 2:.1f}' "
                   f"y2='{cy + c / 2:.1f}' stroke='{color}' stroke-width='0.55' "
                   f"opacity='0.45'/>")
    return "".join(out)


b = []
# red tap from the shared trunk (verbatim geometry from exp 22's figure)
b.append(CUT)
b.append(f"<path d='M 370,161 H 398 V 248 H 345 V 445 H 348' fill='none' "
         f"stroke='{ACC}' stroke-width='1' stroke-dasharray='2 4' opacity='0.85'/>")

# identity-turn trunk feature grid (ink — it already exists; only read by the aux)
b.append(gridsq(350, 432, 56, 8, INK))
b.append(txt(378, 502, "trunk feature grid 8²×48", 10.5, INK, 600))
b.append(txt(378, 514, "identity turn · read before pooling", 9.5, MUT))

# throwaway upsampling decoder: growing red feature squares tied by kernel projections
b.append(gridsq(450, 450, 20, 4, ACC))
b.append(gridsq(495, 445, 30, 5, ACC))
b.append(gridsq(550, 438, 44, 8, ACC))
b.append(kernel_proj(350, 56, 450, 20, ACC))
b.append(kernel_proj(450, 20, 495, 30, ACC))
b.append(kernel_proj(495, 30, 550, 44, ACC))
b.append(txt(460, 444, "16²", 9, FAINT, style="font-style='italic'"))
b.append(txt(510, 439, "32²", 9, FAINT, style="font-style='italic'"))
b.append(txt(572, 432, "64²", 9, FAINT, style="font-style='italic'"))
b.append(txt(512, 530, "throwaway upsampling decoder", 10.5, ACC, 600))
b.append(txt(512, 542, "8²→64² · ~55k params · never exported", 9.5, ACC))

# reconstructed daytime view (red, sketchy) vs clean daytime reference target (ochre)
b.append(kernel_proj(550, 44, 620, 56, ACC))
b.append(f"<rect x='620' y='432' width='56' height='56' fill='{ACC}' "
         f"fill-opacity='0.04' stroke='{ACC}' stroke-width='1.2'/>")
b.append(f"<path d='M 624 470 L 672 446' stroke='{ACC}' stroke-width='4' "
         f"fill='none' opacity='0.22'/>")
b.append(f"<rect x='628' y='440' width='9' height='6' fill='{ACC}' opacity='0.2'/>")
b.append(f"<rect x='656' y='460' width='8' height='7' fill='{ACC}' opacity='0.2'/>")
b.append(f"<rect x='638' y='474' width='10' height='6' fill='{ACC}' opacity='0.2'/>")
b.append(txt(648, 424, "64²×3", 9, FAINT, style="font-style='italic'"))
b.append(txt(648, 502, "redrawn daytime view", 10.5, ACC, 600))
b.append(txt(648, 514, "from features alone", 9.5, ACC))

b.append(f"<rect x='730' y='432' width='56' height='56' fill='{OCH}' "
         f"fill-opacity='0.05' stroke='{OCH}' stroke-width='1.2'/>")
b.append(f"<path d='M 734 470 L 782 446' stroke='{OCH}' stroke-width='4' "
         f"fill='none' opacity='0.35'/>")
b.append(f"<rect x='738' y='440' width='9' height='6' fill='{OCH}' opacity='0.3'/>")
b.append(f"<rect x='766' y='460' width='8' height='7' fill='{OCH}' opacity='0.3'/>")
b.append(f"<rect x='748' y='474' width='10' height='6' fill='{OCH}' opacity='0.3'/>")
b.append(txt(758, 424, "64²×3", 9, FAINT, style="font-style='italic'"))
b.append(txt(758, 530, "daytime reference crop", 10.5, OCH, 600))
b.append(txt(758, 542, "same spot &amp; heading, free from sim", 9.5, OCH))

# L1 comparison between redrawn view and clean target
b.append(f"<line x1='680' y1='460' x2='726' y2='460' stroke='{ACC}' "
         f"stroke-width='1' stroke-dasharray='2 4'/>")
b.append(txt(703, 448, "L1 ×0.3", 9.5, ACC, 600))

# red explanation block (rightmost column)
b.append(f"<line x1='788' y1='470' x2='800' y2='470' stroke='{ACC}' "
         f"stroke-width='1' stroke-dasharray='2 4'/>")
b.append(txt(800, 430, "NEW — daytime-redraw auxiliary", 10, ACC, 600, "start"))
for i, line in enumerate([
    "from its own features, the net",
    "must redraw this spot in clean",
    "daylight; all six renders share",
    "one daytime answer, so seeing",
    "through grain and darkness is the",
    "cheapest fit — decoder never flies",
]):
    b.append(txt(800, 443 + 13 * i, line, 9.5, ACC, 400, "start"))

svg = prefix + "".join(b) + "</svg>"

STAGE_UNCHANGED = [
    {"name": "Camera frame",
     "detail": "128×128 px aerial crop, one of 6 simulated lighting conditions"},
    {"name": "Rotation fan",
     "detail": "the crop is copied into its four 90° turns (exact pixel re-arrangements, no blur) and all four copies travel through the same network side by side"},
    {"name": "Feature extractor",
     "detail": "ImageNet-pretrained MobileNetV3-Small (first 9 blocks, 190k params), gently fine-tuned"},
    {"name": "Layout summary",
     "detail": "a slim extra layer condenses the 8×8 feature grid into a 512-number code that remembers what sits where in the crop; the texture average (48 numbers) is kept alongside"},
    {"name": "Lighting gate",
     "detail": "a tiny network reads the crop's own average brightness together with the 48-number texture summary and outputs one number: how night-like is this shot?"},
    {"name": "Probability map",
     "detail": "two scorers read each of the four turned copies and the gate blends their per-cell guesses; the four resulting heat maps are averaged into one voted map — a location only stays hot if it wins from every direction"},
    {"name": "Decode",
     "detail": "the heat map's contrast is turned up first (peaks boosted, faint background suppressed), then the answer is the balance point of the sharpened map — committing to the strongest hotspot instead of averaging every faint guess across the whole city"},
    {"name": "Confidence",
     "detail": "the model inspects the shape of its own heat map — one crisp hotspot means sure, a washed-out smear means unsure — and below a tuned bar it says 'no fix' instead of guessing; the bar is set so it still answers at least 40% of the time in every lighting condition"},
    {"name": "Output", "detail": "(lat, lon, confidence)"},
]
stages = [dict(s, changed=False) for s in STAGE_UNCHANGED]
stages.append({
    "name": "Training signal",
    "detail": ("position and confidence grading at the crop centre are unchanged; NEW: during "
               "practice only, a small throwaway decoder must redraw the clean DAYTIME version of "
               "the crop (same spot, same heading, half resolution) purely from the network's "
               "internal features — every lighting condition of a place shares the same daytime "
               "answer, so the features are pushed to see through darkness and sensor grain; the "
               "decoder is deleted before export, the flying network is byte-identical in shape"),
    "changed": True, "train_only": True})
stages.append({
    "name": "Training data",
    "detail": ("each pass still draws a fresh 6,000 locations per bucket (fresh headings and "
               "simulator-roll mix, kept from the previous experiment); each practice image comes "
               "from one of three independently rolled versions of the lighting simulator"),
    "changed": False, "train_only": True})

exp = {
    "title": ("Daytime-redraw auxiliary: a throwaway decoder must reconstruct the clean daytime "
              "crop from the encoder's features"),
    "category": "loss",
    "hypothesis": (
        "The binding constraint is still the held-out-location generalization gap the exp-18 probe "
        "measured (train-split crops 267-400 m median vs eval-split 708-1153 m, ~3x, in every "
        "bucket), and after exp 20 the error profile is flat across lighting buckets and areas — "
        "flat but mediocre (best 839.12 m vs the ~20 m target). The trunk is the shared weak link "
        "that flatness points at: every gradient it receives comes from ONE whole-crop place grade "
        "per crop at a gentle 1e-4 LR, while its ImageNet-pretrained features were never adapted to "
        "the sim's night-time statistics (sensor gain noise, lamp thinning, washed-out color are "
        "far outside ImageNet's input distribution). So lighting nuisance still reaches the "
        "descriptor, and the 1024-way head must generalize jointly across location x lighting with "
        "only ~30k single-exposure examples (exp 20) to do it. This experiment builds on library "
        "entry L1, flavor B (training-only reconstruction auxiliary): a small throwaway decoder "
        "must redraw the clean daytime reference crop — same location, same heading, pixel-aligned "
        "pairs free from the frozen sim — from the encoder's 8x8x48 feature grid, with an L1 loss "
        "at 64x64 weighted 0.3, then be deleted before export. All six lighting renders of a place "
        "share ONE daytime answer, so the cheapest way down this loss is features that cancel "
        "lighting and noise while preserving ground structure: canonicalization inside the "
        "encoder, at zero inference cost. Two mechanisms should move the Sec-6 metric: (a) "
        "descriptor variance across buckets collapses, so the head's capacity and exp 20's fresh "
        "location draws concentrate on place discrimination alone instead of place x lighting; "
        "(b) unlike reverted exp 22, whose dense auxiliary was per-patch PLACE classification — 64 "
        "more memorization targets of exactly the kind the transfer gap punishes — night-to-day "
        "redrawing is location-generic (the same inversion applies everywhere on the map, and "
        "under exp 20's sampling no location is seen often enough to memorize its output), so its "
        "gradients transfer to never-trained eval terrain by construction. It is also materially "
        "different from refuted exp 9 (cross-lighting NT-Xent): that was a contrastive ranking "
        "objective on the GLOBAL descriptor of the old from-scratch encoder, satisfiable by "
        "collapsing information; a dense generative target must PRESERVE structure per pixel, and "
        "it acts on today's pretrained trunk."),
    "method": (
        "ONE change: attach a training-only reconstruction decoder to the encoder. model/model.py "
        "gains ReconDecoder (~55k params: 1x1 conv 48->64 then 3x [nearest-upsample x2 + 3x3 conv "
        "+ ReLU] 64->48->32->24, final 1x1 conv ->3 + sigmoid; 8x8x48 in, 64x64x3 out), "
        "build_recon_decoder(), constants RECON_SIZE=64 / LAMBDA_RECON=0.3, and an optional "
        "return_feat flag on TinyLocNet.forward exposing the identity-turn feature map. "
        "model/train.py loads the daytime reference raster once per area, samples for every "
        "training crop the pixel-aligned clean reference crop (same cx/cy/angle) downsampled to "
        "64x64, and adds LAMBDA_RECON * L1(decoder(feat), target) to the existing loss. Decoder "
        "params train at the head LR (1e-3) and are discarded — never exported. Everything else "
        "(architecture, decode, confidence, calibration, sampling, epochs, LRs, ONNX export) "
        "is untouched; the exported graph is byte-identical in shape to the current best."),
    "expected_outcome": (
        "Worst-case median error improves from 839.12 m to ~700-790 m (-6% to -16%), with the gain "
        "spread broadly across buckets (slightly larger in evening/night, where the input is "
        "farthest from the daytime reference). Kept iff < 839.12 m. Refuted if the aux diverts "
        "trunk capacity the way exp 22's place-supervision aux did and the metric lands at or "
        "above 839 m."),
    "init_strategy": "pretrained:mobilenet_v3_small IMAGENET1K_V1 features[0..8] (torchvision, BSD-3)",
    "eli5": (
        "The network learns to recognize places from noisy night photos. We gave it one extra "
        "practice exercise: from its internal impression of a scene, it must also sketch what that "
        "exact spot looks like in clean daylight — like a student proving they truly saw through "
        "the darkness by redrawing the street in daytime colors. The sketching module is thrown "
        "away before anything flies, so the aircraft carries nothing extra. What remains is a "
        "network whose mental image of the ground ignores darkness and sensor grain — and if its "
        "inner picture is always the daytime one, recognizing the place gets easier in every "
        "lighting condition at once."),
    "architecture": {"stages": stages},
    "architecture_svg": svg,
    "implementation_brief": (
        "Two files change: model/model.py and model/train.py. Nothing else. Preserve verbatim: "
        "train.py CLI (python -m model.train --area A --out-dir D [--data-dir P] [--epochs N] "
        "[--max-crops-per-bucket M] [--seed S]), the ONNX contract (one export per area at "
        "<out>/models/<area>.onnx, input 'frame' 1x3x128x128 float32 in [0,1], output 'uvc' "
        "[[u, v, conf]], opset 17, dynamo=False), train_info.json append behavior, and the "
        "deployment gates (ONNX <= 4 MiB, host latency proxy <= 250 ms) — the exported graph must "
        "be IDENTICAL to the current one, since the decoder never ships.\n\n"
        "model/model.py:\n"
        "1. Add module-level constants after GOOD_ERR_UV: RECON_SIZE = 64 and LAMBDA_RECON = 0.3 "
        "(train.py imports both).\n"
        "2. TinyLocNet.forward: change signature to forward(self, x, return_logits: bool = False, "
        "return_feat: bool = False). After computing fmap = self.features(...) on the 4N stack, "
        "nothing else changes. Return behavior: default (False, False) returns out EXACTLY as now "
        "(ONNX export traces this path); (True, False) returns (out, logits) exactly as now; "
        "(True, True) returns (out, logits, fmap[:n]) where fmap[:n] is the identity-turn "
        "[N, 48, 8, 8] slice (the _c4_stack order is rotation-major, so the first n rows are the "
        "un-rotated views). Do not detach it — recon gradients must reach the trunk.\n"
        "3. Add class ReconDecoder(nn.Module), training-only, placed near build_model: __init__ "
        "builds nn.Sequential(Conv2d(48, 64, 1), ReLU, Upsample(scale_factor=2, mode='nearest'), "
        "Conv2d(64, 48, 3, padding=1), ReLU, Upsample(2, 'nearest'), Conv2d(48, 32, 3, padding=1), "
        "ReLU, Upsample(2, 'nearest'), Conv2d(32, 24, 3, padding=1), ReLU, Conv2d(24, 3, 1), "
        "Sigmoid); forward(fmap) returns [N, 3, 64, 64] in [0,1]. Add def build_recon_decoder() "
        "-> nn.Module: return ReconDecoder(). ReconDecoder must NOT be referenced anywhere in "
        "TinyLocNet, loss_fn, or export_onnx.\n"
        "4. Extend the module docstring with 2-3 lines describing the exp (training-only "
        "daytime-reconstruction auxiliary, library L1-B, decoder never exported).\n\n"
        "model/train.py:\n"
        "5. Import build_recon_decoder, RECON_SIZE, LAMBDA_RECON from model.model.\n"
        "6. In train_area, after prepare_realizations returns, load the daytime reference once "
        "and keep it for the whole run: with rasterio.open(area_dir(area, data_dir) / "
        "'reference.tif') as src: ref = src.read().transpose(1, 2, 0)  # HxWx3 uint8. Pass ref "
        "into sample_epoch.\n"
        "7. sample_epoch gains a ref parameter. Inside the per-crop loop, after appending "
        "xs/ys for a crop, also build the pixel-aligned clean target with the SAME cx, cy, and "
        "angle: t = extract_crop(ref, c['cx'], c['cy'], angle), then downsample: ts.append("
        "np.asarray(Image.fromarray(t).resize((RECON_SIZE, RECON_SIZE), Image.BILINEAR))). "
        "Return (x, y, t) where t = torch.from_numpy(np.stack(ts)) stays uint8 "
        "[N, 64, 64, 3] (float-converted per batch — the full-size float tensor would not fit). "
        "CRITICAL: add no new rng draws — reuse the already-drawn angle so the epoch_rng stream "
        "and therefore the sampled locations/headings are identical to the current code.\n"
        "8. In train_area, build the decoder next to the model: decoder = "
        "build_recon_decoder().to(device); decoder.train(). Add {'params': decoder.parameters(), "
        "'lr': 1e-3} as a third param group to the existing Adam (trunk 1e-4 and head 1e-3 groups "
        "unchanged).\n"
        "9. Training loop: unpack x, y, t from sample_epoch; per minibatch, tb = t[idx]"
        ".to(device).permute(0, 3, 1, 2).contiguous().float().div_(255.0); out, logits, feat = "
        "model(xb, return_logits=True, return_feat=True); recon = decoder(feat); loss = "
        "loss_fn(out, logits, yb) + LAMBDA_RECON * torch.nn.functional.l1_loss(recon, tb). "
        "Optimizer step unchanged. del t along with x, y at epoch end.\n"
        "10. Everything downstream is untouched: calibrate_conf_shift (calls model(xb) default "
        "path), export_onnx(model.cpu(), ...) (decoder deliberately not saved or exported), "
        "epochs/max-crops defaults, seeds. Add \"recon_aux\": {\"lambda\": LAMBDA_RECON, "
        "\"target_px\": RECON_SIZE} to the info dict in train_area, and note the change in "
        "train.py's docstring."),
}

out = ROOT / "runs" / "pending_experiment.json"
out.write_text(json.dumps(exp, indent=2))
print(f"wrote {out} ({out.stat().st_size} bytes)")
