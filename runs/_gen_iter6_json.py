"""Generate runs/pending_experiment.json for iter 6 (exp 26):
deployment-envelope capacity scaling — 3x pretrained trunk depth paid for
by int8 FC-head storage at export."""
import json
from pathlib import Path

INK, MUT, FAINT, ACC, OCH = "#111111", "#6b6a60", "#9b998c", "#8c2f1f", "#8a6a1e"
FONT = "Palatino,Georgia,serif"
IC = 150


def txt(x, y, s, size=10, color=MUT, w=400, anchor="middle", style="", tid=None):
    tid_attr = "id='%s' " % tid if tid else ""
    return ("<text %sx='%.0f' y='%.0f' font-family='%s' font-size='%s' "
            "fill='%s' font-weight='%d' text-anchor='%s' %s>%s</text>"
            % (tid_attr, x, y, FONT, size, color, w, anchor, style, s))


def cap(xc, y, name, sub=None, name_color=INK, sub_color=MUT):
    out = [txt(xc, y, name, 10.5, name_color, 600)]
    if sub:
        out.append(txt(xc, y + 12, sub, 9.5, sub_color))
    return "".join(out)


def harrow(x1, x2, y, label=None):
    out = ["<line x1='%.0f' y1='%.0f' x2='%.0f' y2='%.0f' stroke='%s' stroke-width='1'/>"
           % (x1, y, x2 - 5, y, FAINT),
           "<path d='M %.0f,%.0f l -6,-3 v 6 Z' fill='%s'/>" % (x2, y, FAINT)]
    if label:
        out.append(txt((x1 + x2) / 2, y - 6, label, 9, FAINT, style="font-style='italic'"))
    return "".join(out)


def slab(x, s, d, color=INK):
    y = IC - s / 2
    dx, dy = d, d * 0.55
    return ("<polygon points='%.0f,%.0f %.0f,%.0f %.0f,%.0f %.0f,%.0f' fill='#00000010' stroke='%s' stroke-width='1'/>"
            % (x, y, x + dx, y - dy, x + dx + s, y - dy, x + s, y, color)
            + "<polygon points='%.0f,%.0f %.0f,%.0f %.0f,%.0f %.0f,%.0f' fill='#0000001c' stroke='%s' stroke-width='1'/>"
            % (x + s, y, x + dx + s, y - dy, x + dx + s, y - dy + s, x + s, y + s, color)
            + "<rect x='%.0f' y='%.0f' width='%.0f' height='%.0f' fill='#00000006' stroke='%s' stroke-width='1.2'/>"
            % (x, y, s, s, color))


def kernelproj(kx, ky, ks, tx, ty, color=FAINT):
    out = ["<rect x='%.0f' y='%.0f' width='%.0f' height='%.0f' fill='none' stroke='%s' stroke-width='1'/>"
           % (kx, ky, ks, ks, color)]
    for cx, cy in ((kx, ky), (kx + ks, ky), (kx, ky + ks), (kx + ks, ky + ks)):
        out.append("<line x1='%.0f' y1='%.0f' x2='%.0f' y2='%.0f' stroke='%s' stroke-width='0.6' opacity='0.6'/>"
                   % (cx, cy, tx, ty, color))
    out.append("<rect x='%.0f' y='%.0f' width='3' height='3' fill='%s'/>" % (tx - 1.5, ty - 1.5, color))
    return "".join(out)


def bar(x, h, color=INK, ticks=9):
    y = IC - h / 2
    out = ["<rect x='%.0f' y='%.0f' width='7' height='%.0f' fill='none' stroke='%s' stroke-width='1.2'/>"
           % (x, y, h, color)]
    for i in range(1, ticks):
        out.append("<line x1='%.0f' y1='%.1f' x2='%.0f' y2='%.1f' stroke='%s' stroke-width='0.5' opacity='0.5'/>"
                   % (x, y + i * h / ticks, x + 7, y + i * h / ticks, color))
    return "".join(out)


def fan(x1, h1, x2, h2, color=FAINT, n=5):
    out = []
    for i in range(n):
        ya = IC - h1 / 2 + (i + 0.5) * h1 / n
        for j in range(n):
            yb = IC - h2 / 2 + (j + 0.5) * h2 / n
            out.append("<line x1='%.0f' y1='%.1f' x2='%.0f' y2='%.1f' stroke='%s' stroke-width='0.5' opacity='0.45'/>"
                       % (x1, ya, x2, yb, color))
    return "".join(out)


def gridsq(x, s, n, bumps=(), yc=None, color=INK):
    yc = IC if yc is None else yc
    y = yc - s / 2
    out = ["<rect x='%.0f' y='%.0f' width='%.0f' height='%.0f' fill='none' stroke='%s' stroke-width='1.2'/>"
           % (x, y, s, s, color)]
    for i in range(1, n):
        out.append("<line x1='%.1f' y1='%.0f' x2='%.1f' y2='%.0f' stroke='%s' stroke-width='0.45' opacity='0.5'/>"
                   % (x + i * s / n, y, x + i * s / n, y + s, color))
        out.append("<line x1='%.0f' y1='%.1f' x2='%.0f' y2='%.1f' stroke='%s' stroke-width='0.45' opacity='0.5'/>"
                   % (x, y + i * s / n, x + s, y + i * s / n, color))
    for (gx, gy, o) in bumps:
        out.append("<rect x='%.1f' y='%.1f' width='%.1f' height='%.1f' fill='%s' fill-opacity='%.2f'/>"
                   % (x + gx * s / n, y + gy * s / n, s / n, s / n, color, o))
    return "".join(out)


# ---------------- figure ----------------
S = []
Y = 112  # camera frame top edge (centers frame on IC=150)

# 1. frozen camera-frame glyph (canonical, verbatim with Y substituted)
S.append(
    "<g id='cam-terrain'><rect id='frozen-input' x='26' y='112' width='76' height='76' "
    "fill='#f6f4ea' stroke='#9b998c' stroke-width='1.6'/>"
    "<path d='M31 159 L97 139' stroke='#e6e3d4' stroke-width='5' fill='none'/>"
    "<path d='M59 118 L49 182' stroke='#e6e3d4' stroke-width='3.5' fill='none'/>"
    "<rect x='34' y='121' width='12' height='8' fill='#d9d5c3' transform='rotate(-8 40 125)'/>"
    "<rect x='78' y='120' width='10' height='11' fill='#cfccbd'/>"
    "<rect x='35' y='169' width='13' height='8' fill='#d9d5c3'/>"
    "<rect x='75' y='162' width='10' height='9' fill='#cfccbd' transform='rotate(6 80 166)'/>"
    "<rect x='54' y='143' width='9' height='8' fill='#d9d5c3' opacity='.85'/>"
    "<ellipse cx='86' cy='175' rx='8' ry='6' fill='#8a6a1e' opacity='.12'/>"
    "<circle cx='40' cy='140' r='.7' fill='#6b6a60' opacity='.5'/>"
    "<circle cx='70' cy='126' r='.7' fill='#6b6a60' opacity='.5'/>"
    "<circle cx='92' cy='148' r='.7' fill='#6b6a60' opacity='.5'/>"
    "<circle cx='52' cy='164' r='.7' fill='#6b6a60' opacity='.5'/>"
    "<circle cx='82' cy='182' r='.7' fill='#6b6a60' opacity='.5'/>"
    "<circle cx='31' cy='154' r='.7' fill='#6b6a60' opacity='.5'/></g>")
S.append(cap(53, 205, "Camera frame", "128²×3, ~1 m/px", name_color=FAINT, sub_color=FAINT))
S.append(txt(53, 229, "frozen contract", 8.5, FAINT, style="font-style='italic'"))

# 2. rotation fan (four stacked squares)
for i in range(3, -1, -1):
    col = INK if i == 0 else FAINT
    S.append("<rect x='%d' y='%d' width='28' height='28' fill='#00000006' stroke='%s' stroke-width='1'/>"
             % (118 + i * 6, 138 - i * 6, col))
S.append(cap(145, 205, "Rotation fan", "four 90° turns"))
S.append(harrow(104, 116, IC))
S.append(harrow(168, 196, IC, "×4"))

# 3. trunk slabs with kernel projections
S.append(slab(200, 44, 6))                      # stem/early 64^2x16
S.append(cap(224, 205, "stem + early", "64²×16"))
S.append(kernelproj(214, 138, 9, 278, 146))
S.append(slab(272, 32, 10))                     # mid 16^2x24
S.append(cap(290, 232, "mid blocks", "16²×24"))
S.append(kernelproj(282, 140, 7, 346, 148))
S.append(slab(340, 24, 14))                     # blocks 4-8, 8^2x48
S.append(cap(354, 205, "blocks 4–8", "8²×48"))
S.append(kernelproj(344, 142, 6, 414, 148, color=ACC))
S.append(slab(408, 24, 26, color=ACC))          # NEW blocks 9-10, 8^2x96
S.append(cap(424, 232, "blocks 9–10 — new", "dilated — 8²×96",
             name_color=ACC, sub_color=ACC))
S.append(harrow(460, 478, IC))

# 4. layout + GAP code bar
S.append(bar(482, 70))
S.append(cap(482, 205, "layout code", "608-d"))

# 5. FC fan (int8-stored) into probability map
S.append(fan(489, 70, 560, 84, color=ACC))
S.append(cap(524, 258, "int8 FC store — new", "quantized at export · ~7 m effect",
             name_color=ACC, sub_color=ACC))

# 6. lighting gate above the fan
S.append("<circle cx='524' cy='88' r='9' fill='none' stroke='%s' stroke-width='1.2'/>" % INK)
S.append(txt(524, 92, "σ", 9, INK))
S.append(txt(524, 68, "lighting gate", 9.5, MUT))
S.append("<line x1='485' y1='112' x2='517' y2='95' stroke='%s' stroke-width='0.7' opacity='0.6'/>" % FAINT)
S.append("<line x1='532' y1='94' x2='562' y2='108' stroke='%s' stroke-width='0.7' opacity='0.6'/>" % FAINT)

# 7. probability map (32x32 field, C4 vote suggested by echo outline)
S.append("<rect x='564' y='104' width='84' height='84' fill='none' stroke='%s' stroke-width='0.7' opacity='0.5'/>" % FAINT)
BUMP = ((5, 2, .55), (4, 2, .28), (5, 1, .28), (6, 2, .18), (5, 3, .18), (2, 5, .12), (1, 6, .1))
S.append(gridsq(560, 84, 8, bumps=BUMP))
S.append(cap(602, 205, "Probability map", "32×32 cells, C4 vote"))

# 8. decode: converge lines from the hot cells to the crosshair
for (gx, gy) in ((5, 2), (4, 2), (5, 1), (6, 2), (5, 3)):
    cx = 560 + (gx + 0.5) * 84 / 8
    cy = 108 + (gy + 0.5) * 84 / 8
    S.append("<line x1='%.1f' y1='%.1f' x2='804' y2='150' stroke='%s' stroke-width='0.6' opacity='0.55'/>"
             % (cx, cy, FAINT))
S.append("<circle cx='812' cy='150' r='6' fill='none' stroke='%s' stroke-width='1.2'/>" % INK)
S.append("<line x1='812' y1='140' x2='812' y2='160' stroke='%s' stroke-width='0.8'/>" % INK)
S.append("<line x1='802' y1='150' x2='822' y2='150' stroke='%s' stroke-width='0.8'/>" % INK)
S.append(cap(788, 205, "Decode", "sharpened balance point"))
S.append(cap(725, 232, "Confidence", "abstains on smeared maps"))

# 9. frozen output block
S.append(txt(828, 144, "(lat, lon,", 10.5, FAINT, w=600, anchor="start", tid="frozen-output"))
S.append(txt(828, 158, "confidence)", 10.5, FAINT, w=600, anchor="start"))
S.append(txt(828, 172, "frozen contract", 8.5, FAINT, anchor="start", style="font-style='italic'"))

# 10. training-only lane (unchanged) with L-route leader from the map
S.append("<path d='M 644 186 L 654 186 L 654 310' stroke='%s' stroke-width='1' "
         "stroke-dasharray='2 4' fill='none'/>" % OCH)
S.append(txt(368, 316, "training-only lane — unchanged: Gaussian-CE map target · "
             "committed-coord L2 · conf BCE · 24 fresh-draw epochs, cosine LR → 0",
             9.5, OCH, anchor="start", style="font-style='italic'"))

svg = ("<svg viewBox='0 0 980 340' xmlns='http://www.w3.org/2000/svg' font-family='%s'>" % FONT
       + "".join(S) + "</svg>")

# ---------------- experiment record ----------------
exp = {
    "title": "Deployment-envelope capacity scaling: 3× pretrained trunk depth paid for by int8 FC-head storage",
    "category": "architecture",
    "hypothesis": (
        "The binding constraint is model capacity, demonstrated by exp 25's own pre-registered fork: "
        "convergence-scaled training drove the loss to a genuine plateau (berlin 6.29→4.78, flat for the "
        "last 5 epochs at near-zero LR; prignitz 4.51) yet the metric moved only 5.2% (839.12→797.91 m) "
        "against the 10–25% predicted if optimization were binding — and train-split and eval-split "
        "unfiltered medians are now EQUAL, so the model cannot even fit its training locations. A converged, "
        "non-memorizing, underfitting model has exactly one lever left: make it bigger. The only prior "
        "capacity experiment (exp 8, reverted) scaled a FROM-SCRATCH encoder in the pre-pretrained era; "
        "exp 11 then showed pretrained features are what carry this task, and pretrained capacity has never "
        "been scaled since — the trunk has sat at 190k params (MobileNetV3-Small features[:9]) for 15 "
        "iterations because the 4 MiB deployment gate appeared full (3.30 MB). Fresh probes "
        "(runs/_probe_iter6_quant2.py, _probe_iter6_export.py) break that impasse: int8 dynamic quantization "
        "of ONLY the FC heads (which hold 727k of the 823k params) is metrically inert on the current best "
        "model — median decode shift 0.001 uv ≈ 7 m against 650–800 m medians, conf shift 0.006, "
        "latency fine — while shrinking the export 3.30→1.44 MB. The freed bytes exactly pay for "
        "tripling the pretrained trunk: features[:9]→[:11] (190k→576k ImageNet-pretrained params, "
        "48→96 output channels), with block 9's stride-2 depthwise run at stride 1 and block 10's "
        "depthwise dilated 2 (the standard DeepLab trick) so the 8×8 feature grid every kept head reads "
        "is preserved and all pretrained weights load with unchanged shapes. Dry-run export of the full "
        "candidate: 3,091,446 bytes and 4.8 ms single-thread — both frozen gates pass with margin."),
    "method": (
        "model/model.py: (a) trunk builder loads MobileNetV3-Small features[:11] from a new pretrained "
        "snapshot model/pretrained/mnv3s_features10.pt, sets features[9]'s depthwise stride (2,2)→(1,1) "
        "and features[10]'s depthwise dilation→2/padding→4 — output 96×8×8; all heads "
        "re-width automatically via the existing shape probe. (b) export_onnx exports fp32 to a temp file "
        "then writes the final artifact with onnxruntime quantize_dynamic(op_types=['MatMul','Gemm'], "
        "QInt8) — conv layers stay fp32. model/train.py: only the init-strategy log string changes. "
        "Sampler, losses, decode, calibration, EPOCH_MULT=3, cosine schedule: all untouched; the two new "
        "pretrained blocks land in the existing 1e-4 trunk LR group automatically."),
    "expected_outcome": (
        "If trunk capacity is binding, train and eval errors drop TOGETHER (no memorization gap exists to "
        "reopen — exp 20's fresh-draw sampler is untouched): predicted primary worst-case median "
        "797.91 → 620–720 m (−10 to −22%), broad across areas and buckets since the "
        "underfit is global, with final train losses clearly below exp 25's plateau (berlin ≤ 4.65 vs "
        "4.79, prignitz ≤ 4.37 vs 4.51). Kept iff < 797.91 m. Diagnostic forks if refuted: (a) losses "
        "drop ≥0.15 nats but the metric moves <5% — trunk capacity exonerated; the information "
        "limit of the 128 m footprint or the head's structure becomes the demonstrated bottleneck; (b) "
        "losses stay at the exp-25 plateau despite 3× trunk params — the trunk is not where the "
        "underfit lives (head next); (c) metric regresses with healthy losses — check the saved "
        "<area>_fp32_debug.onnx against the shipped int8 artifact to separate a quantization surprise from "
        "a capacity effect (probe predicts ~7 m, i.e. no effect)."),
    "init_strategy": "pretrained:mobilenet_v3_small IMAGENET1K_V1 features[0..10] (torchvision, BSD-3)",
    "eli5": (
        "Last round we gave the model three times longer to study and it finished everything it could hold "
        "— yet scores barely moved. That means its brain is full: it isn't failing to study, it's out "
        "of room. The drone's flight computer caps the model file at 4 MB and we were already near the cap, "
        "but we found that the biggest part of the file — a huge table of connection strengths — "
        "works just as well stored as cheap 1-byte numbers instead of exact 4-byte ones (we measured: "
        "answers move by ~7 meters on errors of ~700). The space that trick frees pays for a "
        "three-times-bigger image-understanding brain, borrowed from the same well-trained library the "
        "model already uses."),
    "architecture": {"stages": [
        {"name": "Camera frame", "detail": "128×128 px aerial crop, one of 6 simulated lighting conditions", "changed": False},
        {"name": "Rotation fan", "detail": "the crop is copied into its four 90° turns (exact pixel re-arrangements, no blur) and all four copies travel through the same network side by side", "changed": False},
        {"name": "Feature extractor", "detail": "ImageNet-pretrained MobileNetV3-Small — NOW the first 11 blocks instead of 9, tripling the borrowed capacity (576k vs 190k params); the two added blocks skip their usual image-shrinking step and look through a wider spacing instead, so the 8×8 grid the rest of the model reads stays intact and every pretrained weight still fits", "changed": True},
        {"name": "Layout summary", "detail": "a slim extra layer condenses the 8×8 feature grid into a 512-number code that remembers what sits where in the crop; the texture average (96 numbers) is kept alongside", "changed": False},
        {"name": "Lighting gate", "detail": "a tiny network reads the crop's own average brightness together with the 96-number texture summary and outputs one number: how night-like is this shot?", "changed": False},
        {"name": "Probability map", "detail": "two scorers read each of the four turned copies and the gate blends their per-cell guesses; the four resulting heat maps are averaged into one voted map — same mechanics as before, but the scorers' bulky connection tables now fly as compact 1-byte integers instead of 4-byte decimals (measured cost: ~7 m of wobble against ~700 m errors), freeing the file space that pays for the deeper feature extractor", "changed": True},
        {"name": "Decode", "detail": "the heat map's contrast is turned up first (peaks boosted, faint background suppressed), then the answer is the balance point of the sharpened map — committing to the strongest hotspot instead of averaging every faint guess across the whole city", "changed": False},
        {"name": "Confidence", "detail": "the model inspects the shape of its own heat map — one crisp hotspot means sure, a washed-out smear means unsure — and below a tuned bar it says 'no fix' instead of guessing; the bar is set so it still answers at least 40% of the time in every lighting condition", "changed": False},
        {"name": "Output", "detail": "(lat, lon, confidence)", "changed": False},
        {"name": "Training signal", "detail": "unchanged — same position and confidence grading as before", "changed": False, "train_only": True},
        {"name": "Training data", "detail": "unchanged — every pass draws a fresh set of 6,000 places per lighting condition (new headings, new simulator-roll mix), so memorizing individual crops doesn't pay", "changed": False, "train_only": True},
        {"name": "Training schedule", "detail": "unchanged — 24 fresh-draw passes with the cosine glide kept from last round", "changed": False, "train_only": True},
    ]},
    "architecture_svg": svg,
    "implementation_brief": (
        "THREE files are touched: model/model.py, model/train.py (one string), and a NEW generated file "
        "model/pretrained/mnv3s_features10.pt. Nothing else — pipeline/, loop.sh, scoring are frozen.\n"
        "\n"
        "STEP 0 — generate the pretrained snapshot (one-off script, run from repo root):\n"
        "    import torch\n"
        "    from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights\n"
        "    m = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.IMAGENET1K_V1)\n"
        "    sd = {'features.' + k: v for k, v in m.features[:11].state_dict().items()}\n"
        "    torch.save(sd, 'model/pretrained/mnv3s_features10.pt')\n"
        "The IMAGENET1K_V1 checkpoint is already in the torch hub cache (downloaded during design probing), "
        "so this needs no network. Keep the existing mnv3s_features8.pt in place (git history/reverts).\n"
        "\n"
        "STEP 1 — model/model.py:\n"
        "  * PRETRAINED_TRUNK_PATH → Path(__file__).parent / 'pretrained' / 'mnv3s_features10.pt'.\n"
        "  * _build_pretrained_trunk(): build mobilenet_v3_small(weights=None).features[:11]; strip the "
        "'features.' key prefix and load_state_dict(strict=True) exactly as now; THEN apply the dilation "
        "surgery (after loading — weight shapes are unaffected):\n"
        "        dw9 = trunk[9].block[1][0]   # 5x5 depthwise conv of block 9\n"
        "        assert dw9.stride == (2, 2) and dw9.groups == dw9.in_channels\n"
        "        dw9.stride = (1, 1)\n"
        "        dw10 = trunk[10].block[1][0]  # 5x5 depthwise conv of block 10\n"
        "        assert dw10.kernel_size == (5, 5) and dw10.groups == dw10.in_channels\n"
        "        dw10.dilation = (2, 2); dw10.padding = (4, 4)\n"
        "    Update the builder docstring: output is now 96x8x8. NO other forward/TinyLocNet changes: "
        "feat_ch/fmap_hw are probed dynamically, so layout_squeeze (96→8), loc_logits (608→1024), "
        "dark_logits (96→1024), gate (97→...), conf_head (99→...) all re-width themselves.\n"
        "  * export_onnx(model, path): export fp32 with the EXACT current torch.onnx.export call (opset 17, "
        "dynamo=False, input_names=['frame'], output_names=['uvc']) but to a sibling temp file, then:\n"
        "        from onnxruntime.quantization import quantize_dynamic, QuantType   # import inside the fn\n"
        "        quantize_dynamic(tmp_path, path, weight_type=QuantType.QInt8,\n"
        "                         op_types_to_quantize=['MatMul', 'Gemm'])\n"
        "    so the FINAL <out>/models/<area>.onnx is the int8-FC artifact the frozen scorer sees. Keep the "
        "fp32 file beside it renamed to <area>_fp32_debug.onnx (scorer only reads <area>.onnx; the copy is "
        "forensics for the pre-registered fork (c)). Do NOT quantize Conv ops — the probe showed "
        "whole-graph ConvInteger destroys accuracy (decode moves ~half the map) and breaks the 250 ms "
        "latency gate; MatMul/Gemm-only was measured inert (~0.001 uv) and fast (4.8 ms single-thread).\n"
        "  * Append a short exp-26 paragraph to the module docstring (capacity fork from exp 25; int8 FC "
        "storage pays for features[:11]; dilation preserves the 8x8 grid).\n"
        "\n"
        "STEP 2 — model/train.py: change ONLY the info['init'] string to "
        "'pretrained:mobilenet_v3_small IMAGENET1K_V1 features[0..10] (torchvision, BSD-3)'. Everything "
        "else is untouched: CLI (--area --out-dir --data-dir --epochs --max-crops-per-bucket --seed), "
        "EPOCH_MULT=3 with per-step cosine anneal to 0, per-epoch fresh-draw sampler, TRAIN_REALIZATIONS=3, "
        "calibrate_conf_shift (runs on the torch model BEFORE export, so calibration is quantization-"
        "independent by construction; probe measured conf shift 0.006 through int8, well inside the 40% "
        "keep-floor margin). The two new trunk blocks live in model.features, so they automatically join "
        "the 1e-4 trunk LR param group — verify by printing the two group sizes once if in doubt.\n"
        "\n"
        "STEP 3 — smoke test before handing to the harness (no training): build_model(); "
        "sum(p.numel()) must be 1,305,002 (trunk 576,464); trunk(zeros(1,3,128,128)) shape (1,96,8,8); "
        "export_onnx to a temp dir; final file expected ~3,091,446 bytes (assert ≤ 4*1024*1024); load "
        "with onnxruntime (intra_op=1, inter_op=1, CPUExecutionProvider), run a 1x3x128x128 float32 zeros "
        "input, expect output shape (1,3) with u,v in [0,1]; median latency over 20 runs must be far below "
        "250 ms (probe measured 4.8 ms). runs/_probe_iter6_export.py is a working reference for all of "
        "this, including the exact surgery lines.\n"
        "\n"
        "FIXED CONTRACTS (restated): train.py CLI unchanged; one ONNX per area at <out>/models/<area>.onnx "
        "taking 1x3x128x128 float32 in [0,1] and returning [[u, v, conf]] with u,v normalized map coords "
        "and conf in [0,1]; export must pass pipeline/score.py's frozen gates (≤4 MiB, ≤250 ms "
        "single-thread host proxy); conf_shift buffer exported inside the model; never touch pipeline/, "
        "the eval sets, or anything in /FROZEN; never read or evaluate hamburg."),
}

Path("runs/pending_experiment.json").write_text(json.dumps(exp, indent=2))
print("written; svg bytes:", len(svg))
