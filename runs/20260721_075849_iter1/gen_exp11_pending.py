"""Generate runs/pending_experiment.json for exp 11 (pretrained MNV3-Small trunk),
including the architecture SVG drawn in the shared visual language of
archive/arch_svg_reference.py (helpers copied, not imported — the archive
module writes to the DB on import)."""
import json
import math

INK, MUT, FAINT, ACC, OCH = "#111111", "#6b6a60", "#9b998c", "#8c2f1f", "#8a6a1e"
FONT = "Palatino,Georgia,serif"
IC = 112
LOSS_Y = 292


def txt(x, y, s, size=10, color=MUT, w=400, anchor="middle", style=""):
    return (f"<text x='{x:.0f}' y='{y:.0f}' font-family='{FONT}' font-size='{size}' "
            f"fill='{color}' font-weight='{w}' text-anchor='{anchor}' {style}>{s}</text>")


def cap(xc, y, name, sub=None, color=MUT, name_color=None):
    out = [txt(xc, y, name, 10.5, name_color or (INK if color == MUT else color), 600)]
    if sub:
        out.append(txt(xc, y + 12, sub, 9.5, name_color if name_color == ACC else color))
    return "".join(out)


def harrow(x1, x2, y, label=None, color=FAINT):
    out = [f"<line x1='{x1}' y1='{y}' x2='{x2 - 5}' y2='{y}' stroke='{color}' stroke-width='1'/>",
           f"<path d='M {x2},{y} l -6,-3 v 6 Z' fill='{color}'/>"]
    if label:
        out.append(txt((x1 + x2) / 2, y - 6, label, 9, FAINT, style="font-style='italic'"))
    return "".join(out)


def leader(x1, y1, x2, y2, color):
    return (f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='{color}' "
            f"stroke-width='1' stroke-dasharray='2 4'/>")


def slab(x, s, d, color=INK, yc=None):
    yc = IC if yc is None else yc
    y = yc - s / 2
    dx, dy = d, d * 0.55
    out = [
        f"<polygon points='{x},{y} {x+dx},{y-dy} {x+dx+s},{y-dy} {x+s},{y}' "
        f"fill='#00000010' stroke='{color}' stroke-width='1'/>",
        f"<polygon points='{x+s},{y} {x+dx+s},{y-dy} {x+dx+s},{y-dy+s} {x+s},{y+s}' "
        f"fill='#0000001c' stroke='{color}' stroke-width='1'/>",
        f"<rect x='{x}' y='{y}' width='{s}' height='{s}' fill='#00000006' "
        f"stroke='{color}' stroke-width='1.2'/>",
    ]
    return "".join(out), s + dx


def imgsq(x, s, color=INK):
    y = IC - s / 2
    out = [f"<rect x='{x}' y='{y}' width='{s}' height='{s}' fill='#00000008' "
           f"stroke='{color}' stroke-width='1.4'/>"]
    n = 6
    for i in range(1, n):
        out.append(f"<line x1='{x + i * s / n:.0f}' y1='{y}' x2='{x + i * s / n:.0f}' "
                   f"y2='{y + s}' stroke='{color}' stroke-width='0.4' opacity='0.3'/>")
        out.append(f"<line x1='{x}' y1='{y + i * s / n:.0f}' x2='{x + s}' "
                   f"y2='{y + i * s / n:.0f}' stroke='{color}' stroke-width='0.4' opacity='0.3'/>")
    for (a, b, o) in ((1, 2, .35), (3, 1, .5), (2, 4, .4), (4, 3, .3), (0, 4, .25), (4, 0, .3)):
        out.append(f"<rect x='{x + a * s / n:.0f}' y='{y + b * s / n:.0f}' "
                   f"width='{s / n:.0f}' height='{s / n:.0f}' fill='{color}' opacity='{o * 0.35}'/>")
    return "".join(out), s


def bar(x, h, color=INK, ticks=9, yc=None):
    yc = IC if yc is None else yc
    y = yc - h / 2
    out = [f"<rect x='{x}' y='{y}' width='7' height='{h}' fill='none' "
           f"stroke='{color}' stroke-width='1.2'/>"]
    for i in range(1, ticks):
        out.append(f"<line x1='{x}' y1='{y + i * h / ticks:.1f}' x2='{x + 7}' "
                   f"y2='{y + i * h / ticks:.1f}' stroke='{color}' stroke-width='0.5' opacity='0.5'/>")
    return "".join(out), 7


def gridsq(x, s, n, color=INK, bumps=(), yc=None, lw=1.2):
    yc = IC if yc is None else yc
    y = yc - s / 2
    out = [f"<rect x='{x}' y='{y}' width='{s}' height='{s}' fill='none' "
           f"stroke='{color}' stroke-width='{lw}'/>"]
    for i in range(1, n):
        out.append(f"<line x1='{x + i * s / n:.1f}' y1='{y}' x2='{x + i * s / n:.1f}' "
                   f"y2='{y + s}' stroke='{color}' stroke-width='0.45' opacity='0.5'/>")
        out.append(f"<line x1='{x}' y1='{y + i * s / n:.1f}' x2='{x + s}' "
                   f"y2='{y + i * s / n:.1f}' stroke='{color}' stroke-width='0.45' opacity='0.5'/>")
    for (gx, gy, o) in bumps:
        out.append(f"<rect x='{x + gx * s / n:.1f}' y='{y + gy * s / n:.1f}' "
                   f"width='{s / n:.1f}' height='{s / n:.1f}' fill='{color}' fill-opacity='{o}'/>")
    return "".join(out), s


BUMP = ((5, 2, .55), (4, 2, .28), (5, 1, .28), (6, 2, .18), (5, 3, .18), (2, 5, .12), (1, 6, .1))


def crosspt(x, y, color, r=7):
    return (f"<line x1='{x - r}' y1='{y}' x2='{x + r}' y2='{y}' stroke='{color}' stroke-width='1.4'/>"
            f"<line x1='{x}' y1='{y - r}' x2='{x}' y2='{y + r}' stroke='{color}' stroke-width='1.4'/>"
            f"<circle cx='{x}' cy='{y}' r='{r * 0.55:.1f}' fill='none' stroke='{color}' stroke-width='1.4'/>"
            f"<circle cx='{x}' cy='{y}' r='1.5' fill='{color}'/>")


def converge(gx, gs, tx, color, n=8):
    out = []
    y0 = IC - gs / 2
    for gyy in range(n):
        for gxx in range(n):
            if (gxx + gyy) % 2:
                continue
            sx, sy = gx + (gxx + 0.5) * gs / n, y0 + (gyy + 0.5) * gs / n
            out.append(f"<line x1='{sx:.0f}' y1='{sy:.0f}' x2='{tx}' y2='{IC}' "
                       f"stroke='{color}' stroke-width='0.55' opacity='0.4'/>")
    out.append(crosspt(tx, IC, color))
    return "".join(out)


def gauge(x, yc, color=MUT, r=14):
    a = math.radians(55)
    return (f"<path d='M {x - r},{yc} A {r} {r} 0 0 1 {x + r},{yc}' fill='none' "
            f"stroke='{color}' stroke-width='1.2'/>"
            f"<line x1='{x}' y1='{yc}' x2='{x + (r - 3) * math.cos(a):.1f}' "
            f"y2='{yc - (r - 3) * math.sin(a):.1f}' stroke='{color}' stroke-width='1.4'/>"
            f"<circle cx='{x}' cy='{yc}' r='1.6' fill='{color}'/>")


def kernel_proj(x1, s1, x2, s2, color, y1c=None, y2c=None):
    y1c = IC if y1c is None else y1c
    y2c = IC if y2c is None else y2c
    k = max(5, s1 * 0.30)
    kx, ky = x1 + s1 * 0.60, y1c - s1 / 2 + s1 * 0.18
    c = max(3, s2 * 0.14)
    cx, cy = x2 + s2 * 0.22, y2c - s2 / 2 + s2 * 0.26
    out = [f"<rect x='{kx:.1f}' y='{ky:.1f}' width='{k:.1f}' height='{k:.1f}' "
           f"fill='none' stroke='{color}' stroke-width='0.9'/>",
           f"<rect x='{cx:.1f}' y='{cy:.1f}' width='{c:.1f}' height='{c:.1f}' "
           f"fill='{color}' fill-opacity='0.5' stroke='none'/>"]
    for (px, py) in ((kx, ky), (kx + k, ky), (kx, ky + k), (kx + k, ky + k)):
        out.append(f"<line x1='{px:.1f}' y1='{py:.1f}' x2='{cx + c / 2:.1f}' "
                   f"y2='{cy + c / 2:.1f}' stroke='{color}' stroke-width='0.55' "
                   f"opacity='0.45'/>")
    return "".join(out)


def build_svg():
    b = [txt(8, 26, "INFERENCE PATH — WHAT FLIES", 9, FAINT, 600, "start",
             "letter-spacing='1.8'"),
         txt(8, LOSS_Y - 34, "TRAINING SIGNALS — NEVER FLY", 9, OCH, 600, "start",
             "letter-spacing='1.8'")]

    # frozen input
    g, _ = imgsq(26, 54, FAINT)
    b.append(g)
    b.append(txt(53, IC - 40, "128²×3", 9, FAINT))
    b.append(txt(53, IC + 48, "camera frame", 10.5, MUT, 600))
    b.append(txt(53, IC + 60, "one night exposure", 9.5, FAINT))
    b.append(txt(53, IC + 73, "frozen contract", 8.5, FAINT, style="font-style='italic'"))
    b.append(harrow(86, 108, IC))

    # CHANGED: pretrained MobileNetV3-Small trunk — 5 slabs, red
    sizes = [(46, 7), (34, 9), (25, 12), (18, 16), (17, 21)]
    x, faces = 112, []
    for s, d in sizes:
        g, w = slab(x, s, d, ACC)
        b.append(g)
        faces.append((x, s))
        x += w + 12
    x -= 12
    b.append(kernel_proj(26, 54, faces[0][0], faces[0][1], ACC))
    for (x1, s1), (x2, s2) in zip(faces, faces[1:]):
        b.append(kernel_proj(x1, s1, x2, s2, ACC))
    trunk_mid = (112 + x) / 2
    b.append(cap(trunk_mid, IC + 58, "MobileNetV3-Small encoder — ImageNet-pretrained",
                 "stem + 8 inverted-residual blocks · depthwise conv + squeeze-excite",
                 name_color=ACC))
    b.append(txt(135, IC - 36, "64²×16", 9, FAINT))
    b.append(txt(x - 18, IC - 34, "8²×48", 9, FAINT))

    # unchanged head: layout squeeze slab (raised) + GAP bar
    trunk_end, trunk_s = faces[-1]
    sq_x, sq_yc = 408, 84
    g, _ = slab(sq_x, 17, 21, INK, yc=sq_yc)
    b.append(g)
    b.append(kernel_proj(trunk_end, trunk_s, sq_x, 17, MUT, y2c=sq_yc))
    b.append(cap(421, 46, "1×1 conv → 8²×8 layout code",
                 "keeps what sits WHERE in the crop"))
    gap_x, gap_yc = 428, 158
    b.append(f"<line x1='{trunk_end + trunk_s}' y1='{IC + 9}' x2='{gap_x - 3}' "
             f"y2='{gap_yc - 10}' stroke='{FAINT}' stroke-width='0.8'/>")
    b.append(f"<path d='M {gap_x},{gap_yc - 8} l -6,-1.5 3,5.5 Z' fill='{FAINT}'/>")
    g, _ = bar(gap_x, 40, ticks=7, yc=gap_yc)
    b.append(g)
    b.append(txt(gap_x + 3, gap_yc + 34, "48-d GAP", 10.5, INK, 600))
    b.append(txt(gap_x + 3, gap_yc + 46, "texture average — as before", 9.5, MUT))

    # concat fan into FC logits bar (unchanged)
    fc_x, fc_h = 500, 92
    for (sy0, sy1, sn) in ((71, 92, 4), (gap_yc - 20, gap_yc + 20, 4)):
        for i in range(sn):
            ya = sy0 + (i + 0.5) * (sy1 - sy0) / sn
            for j in range(4):
                yb = IC - fc_h / 2 + (j + 0.5) * fc_h / 4
                b.append(f"<line x1='{sq_x + 17 if sy0 < 100 else gap_x + 7}' y1='{ya:.1f}' "
                         f"x2='{fc_x}' y2='{yb:.1f}' stroke='{FAINT}' "
                         f"stroke-width='0.5' opacity='0.4'/>")
    g, _ = bar(fc_x, fc_h, ticks=15)
    b.append(g)
    b.append(txt(467, 66, "512 ⊕ 48 = 560", 9, FAINT, style="font-style='italic'"))
    b.append(cap(fc_x + 4, IC + 84, "FC 560 → 1024 logits", "softmax"))
    b.append(harrow(fc_x + 14, fc_x + 38, IC))

    # probability field + soft-argmax decode (unchanged)
    gx = fc_x + 40
    g, gs = gridsq(gx, 76, 8, INK, BUMP)
    b.append(g)
    b.append(cap(gx + 38, IC + 56, "probability field", "32×32 cells over the map"))
    tx = gx + gs + 96
    b.append(converge(gx, gs, tx, INK))
    b.append(cap((gx + gs + tx) / 2 + 4, IC - 54, "soft-argmax over ALL cells",
                 "answer = Σ probability · cell-center"))
    b.append(txt(tx + 18, IC - 18, "frozen contract", 8.5, FAINT, anchor="start",
                 style="font-style='italic'"))
    b.append(txt(tx + 18, IC - 2, "(u, v, conf)", 13, MUT, 600, "start"))
    b.append(txt(tx + 18, IC + 12, "position fix + confidence", 9, FAINT, anchor="start"))

    # confidence branch (unchanged)
    cx0 = gap_x + 3
    ex = tx + 46
    b.append(leader(cx0, gap_yc + 52, cx0, 216, FAINT))
    b.append(gauge(cx0, 230, MUT))
    b.append(txt(cx0, 248, "confidence 0–1", 9, MUT))
    b.append(f"<path d='M {cx0 + 18},230 H {ex} V {IC + 26}' fill='none' "
             f"stroke='{FAINT}' stroke-width='0.8'/>")
    b.append(f"<path d='M {ex},{IC + 20} l -3,6 h 6 Z' fill='{FAINT}'/>")
    b.append(txt((cx0 + ex) / 2, 224, "may abstain instead of guessing", 8.5, FAINT,
                 style="font-style='italic'"))

    # training lane: pretrained-init note (red) + unchanged losses (ochre)
    b.append(leader(trunk_mid - 60, IC + 68, 60, LOSS_Y - 20, ACC))
    b.append(txt(68, LOSS_Y - 12, "trunk weights arrive from ImageNet (1.2M real photos) — not random",
                 10, ACC, 600, "start"))
    b.append(txt(68, LOSS_Y, "fine-tuned gently: trunk lr 1e-4 · fresh heads lr 1e-3 · BSD-3 licensed",
                 9.5, ACC, 400, "start"))
    tiny, _ = gridsq(586, 22, 6, OCH, ((3, 2, .6),), yc=LOSS_Y - 12, lw=1)
    b.append(leader(gx + 38, IC + 76, 608, LOSS_Y - 16, OCH))
    b.append(tiny)
    b.append(txt(616, LOSS_Y - 12, "Gaussian-CE + decode L2 + conf BCE — all unchanged",
                 10, OCH, 600, "start"))
    b.append(txt(616, LOSS_Y, "head, decode and training recipe identical to kept exp 10",
                 9.5, OCH, 400, "start"))
    b.append(txt(968, 26, "red = this experiment: an ImageNet-pretrained trunk replaces the from-scratch encoder",
                 9.5, ACC, 400, "end", "font-style='italic'"))
    return ("<svg viewBox='0 0 980 340' xmlns='http://www.w3.org/2000/svg' role='img'>"
            + "".join(b) + "</svg>")


EXP = {
    "title": "ImageNet-pretrained MobileNetV3-Small trunk replaces the from-scratch encoder",
    "category": "architecture",
    "hypothesis": (
        "The binding constraint is the quality of the conv features themselves, and no "
        "within-dataset signal can fix it: exp 8 showed more from-scratch capacity does not "
        "help, exp 9 showed a direct place-discrimination objective (InfoNCE) on from-scratch "
        "features does not help, and exp 10's layout-aware head — which finally lets the head "
        "read WHERE features sit — was kept but recovered only 1.2%, implying the features it "
        "reads carry little discriminative content. All ten experiments trained the encoder "
        "from random init on ~36k synthetic relit crops of ONE area — far too little visual "
        "diversity to learn the general edge/corner/texture/junction vocabulary that makes "
        "local patterns separable. CLAUDE.md §3/§9 explicitly reserves permissively-licensed "
        "pretrained init as an open call, and it is the one family in the plateau-rule list "
        "never tried. Swapping the from-scratch 4-conv stack for the first 9 feature blocks of "
        "ImageNet-pretrained MobileNetV3-Small (195k params, BSD-3, output 8x8x48 — the exact "
        "spatial grid the kept exp-10 head already reads) imports a feature vocabulary learned "
        "from 1.2M real photographs; low/mid-level features are the standard transferable "
        "layer even across large domain gaps (ground-level photos -> overhead relit imagery)."
    ),
    "method": (
        "model/model.py: replace the 4x stride-2 conv stack with MobileNetV3-Small "
        "features[0..8] re-implemented in plain PyTorch with torchvision-identical state-dict "
        "keys (torchvision is not installed); load the verbatim IMAGENET1K_V1 tensors from "
        "model/pretrained/mnv3s_features8.pt with strict=True; bake ImageNet mean/std "
        "normalization into forward() as buffers so the [0,1] ONNX input contract is "
        "unchanged. Head adapts only in width (layout squeeze 48->8, FC 560->1024, conf "
        "48->1); GRID_K, losses, decode, export contract all unchanged. model/train.py: "
        "two-tier fine-tuning LR (trunk 1e-4, fresh heads 1e-3) so early large head gradients "
        "do not destroy the transferred features; log init strategy per §9. Verified: strict "
        "load OK, ONNX 2.94 MiB (< 4 MiB gate), latency proxy 0.53 ms (< 250 ms gate), "
        "torch/ONNX parity 6e-8, untrained decode sits at the map center (bounded downside)."
    ),
    "expected_outcome": (
        "If feature quality is the binding constraint, worst-case median error drops clearly "
        "below the kept 2299.74 m — plausibly 1,200–2,100 m, with bright buckets improving "
        "most (their texture becomes separable first) and the probability field finally "
        "committing to real modes. Downside tightly bounded: head/loss/decode are unchanged "
        "and an uninformative field still decodes near the map center (~3.2 km floor), so a "
        "null lands near 2.3–2.4 km. A null would be decisive: with features (pretrained AND "
        "contrastive), capacity, data scale, supervision form, rotation handling, and pooling "
        "all ruled out, the remaining suspects are lighting-conditional structure (dispatcher "
        "+ specialists) and the information content of the relit imagery itself (learned "
        "relighting) — the only untried families."
    ),
    "init_strategy": "pretrained:mobilenet_v3_small IMAGENET1K_V1 features[0..8] (torchvision, BSD-3)",
    "eli5": (
        "Until now the model's 'eyes' started out completely blind: they had to learn to see "
        "edges, corners and textures using only pictures of the one training area — like "
        "learning to read from a single book. This experiment swaps in eyes that were already "
        "trained on 1.2 million everyday photographs, so they arrive knowing how to see, and "
        "we only gently retune them to our night-time aerial views. Everything after the eyes "
        "— the part that guesses the position on the map — stays exactly the same. If the "
        "guesses were bad because the eyes were weak, this should help a lot; if not, we have "
        "learned the eyes were never the problem."
    ),
    "architecture": {"stages": [
        {"name": "Camera frame",
         "detail": "128×128 px aerial crop, one of 6 simulated lighting conditions",
         "changed": False},
        {"name": "Feature extractor",
         "detail": "ImageNet-pretrained MobileNetV3-Small (first 9 blocks, 195k params) replaces the from-scratch 4-layer CNN — it arrives already knowing edges, corners and textures from 1.2M real photos and is gently fine-tuned to this area",
         "changed": True},
        {"name": "Layout summary",
         "detail": "a slim extra layer condenses the 8×8 feature grid into a 512-number code that remembers what sits where in the crop; the texture average (now 48 numbers) is kept alongside",
         "changed": False},
        {"name": "Probability map",
         "detail": "scores every cell of a 32×32 grid over the map: “how likely did the photo come from here?” — reading the layout code together with the texture average",
         "changed": False},
        {"name": "Decode",
         "detail": "answer = balance point of the whole heat map (weighted average of all 1,024 cells)",
         "changed": False},
        {"name": "Confidence",
         "detail": "separate 0–1 score; low means the model abstains rather than guessing",
         "changed": False},
        {"name": "Output",
         "detail": "(lat, lon, confidence)",
         "changed": False},
    ]},
}

EXP["architecture_svg"] = build_svg()

with open("runs/pending_experiment.json", "w") as f:
    json.dump(EXP, f, indent=2, ensure_ascii=False)
print("wrote runs/pending_experiment.json,", len(EXP["architecture_svg"]), "bytes of SVG")
