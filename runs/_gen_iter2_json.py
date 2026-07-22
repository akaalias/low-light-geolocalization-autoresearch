import json

svg = open("runs/_iter2_fig.svg").read()

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
    {"name": "Training signal", "detail": "position and confidence grading at the crop centre are unchanged; NEW: during practice only, each of the 64 cells of the 8×8 feature grid must ALSO point out on the map where its own 16 m patch of ground sits (graded with the same kind of Gaussian-bump target, at the patch's true position = crop centre + rotated cell offset) — 64 graded answers per crop instead of one; this extra quiz head is deleted before export, so the flying network is byte-identical in shape to the previous experiment", "changed": True, "train_only": True},
    {"name": "Training data", "detail": "each pass still draws a fresh 6,000 locations per bucket (fresh headings and simulator-roll mix, kept from the previous experiment); each practice image comes from one of three independently rolled versions of the lighting simulator", "changed": False, "train_only": True},
]

exp = {
    "title": "Train-only per-patch place supervision: every feature cell places its own patch, the flying decode is untouched",
    "category": "loss",
    "hypothesis": (
        "The binding constraint is still the held-out-location generalization gap the exp-18 probe measured "
        "(train-split crops 267-400 m median vs eval-split 708-1153 m, ~3x, in every bucket), and after exp 20 "
        "the error profile is flat across lighting and areas (metros 656-839 m, prignitz 449-539 m; night is no "
        "longer the worst bucket anywhere) -- lighting is solved as a differentiator, transfer to unseen terrain "
        "is the whole game. Exp 20 removed repetition-driven whole-crop memorization on the DATA side (kept, "
        "1054.87 -> 839.12 m). The remaining untried side is the SUPERVISION density: the trunk's features are "
        "trained through exactly one grade per crop -- a single whole-crop Gaussian-CE at the crop centre -- so "
        "nothing ever demands that each local feature column be location-predictive on its own; the cheapest fit "
        "is whole-crop gestalt, which the probe shows failing to transfer. Exps 4 and 18 both made per-patch "
        "localization the INFERENCE mechanism and were reverted; their joint lesson (recorded in exp 19's design) "
        "is that the whole-crop arrangement signal must stay intact at decode time -- but neither ever tested "
        "per-patch supervision as a training-only regularizer under the kept whole-crop decode, which is standard "
        "deep-supervision practice and is exactly the configuration their failures leave open. A dense auxiliary "
        "head (one shared 1x1 conv 48->1024 on the identity-turn feature grid) that makes each of the 64 feature "
        "columns predict its OWN Gaussian-CE map field at its patch's true ground position multiplies the "
        "supervision 64x per crop, and -- combined with exp 20's single-exposure sampling, where a location is "
        "seen only ~1-2 times -- can only be satisfied by local cues that transfer between locations. At eval, "
        "~76% of eval crops contain SOME train-seen terrain at a known offset (exp 19's geometry analysis); "
        "locally location-predictive feature columns put that partial familiarity into the 8x8 layout code the "
        "kept head already reads spatially -- delivering exp 18's intended benefit through the decode that works, "
        "instead of the per-patch fusion that failed."
    ),
    "method": (
        "model/model.py: add aux_patch_head = nn.Conv2d(48, GRID_K*GRID_K, 1) and a forward_train() that returns "
        "(out, logits, aux_logits) where aux_logits [N,1024,8,8] is the aux head applied to the identity-rotation "
        "slice of the trunk feature map; forward() and the ONNX export are byte-for-byte unchanged (the aux head "
        "is not traced, so exported size stays 3.30 MiB). Add aux_patch_loss(): per-patch Gaussian-CE (same "
        "GRID_K/TARGET_SIGMA_CELLS formula as loss_fn) against each patch's true map uv. model/train.py: "
        "sample_epoch additionally returns per-crop patch targets [N,64,2] computed as (cx,cy) + R(angle) @ d for "
        "each feature cell's crop-plane offset d = ((j+0.5)*16-64, (i+0.5)*16-64) px, with the numerically "
        "verified rotation R(angle) = [[cos,-sin],[sin,cos]] (angle in degrees exactly as passed to extract_crop; "
        "verified against extract_crop at 0/90/30/217 deg). Training loss becomes loss_fn(...) + 0.5 * "
        "aux_patch_loss(...). Nothing else changes: same epochs, sampling, calibration, export."
    ),
    "expected_outcome": (
        "If dense per-patch supervision closes even a quarter of the ~3x train/eval generalization gap, the "
        "worst-case median drops from 839.12 m to roughly 700-760 m. Pre-registered prediction: primary metric "
        "<= 780 m, with the improvement broad-based across the three metro areas (the top ~10 cells all sit at "
        "656-839 m) rather than concentrated in one bucket; coverage roughly unchanged (calibration path "
        "untouched). Failure mode to watch: the aux gradient distorting the trunk against the whole-crop "
        "objective -- weight 0.5 on the patch-mean CE keeps the main loss dominant; if the metric worsens, the "
        "conclusion is that trunk features cannot serve both objectives at this capacity, closing the "
        "deep-supervision branch of the exp-4/18 family for good."
    ),
    "init_strategy": "pretrained:mobilenet_v3_small IMAGENET1K_V1 features[0..8] (torchvision, BSD-3) — unchanged",
    "eli5": (
        "Until now the model got one graded question per practice photo: 'where is the CENTER of this photo on "
        "the map?' A student can pass that test by memorizing whole photos -- which fails on parts of the city "
        "held back from practice. Now, during practice only, every small tile of the photo also gets its own "
        "graded question: 'where does THIS tile sit on the map?' -- 64 grades per photo instead of one. To score "
        "well the network must learn what roads, buildings and field edges actually look like from above, "
        "knowledge that transfers to never-practiced places. On the real flight nothing changes: the extra quiz "
        "machinery is thrown away before takeoff and the aircraft carries exactly the same network as before."
    ),
    "architecture": {"stages": stages},
    "architecture_svg": svg,
    "implementation_brief": (
        "Scope: model/model.py and model/train.py only. Do not touch pipeline/, areas.yaml, or anything in "
        "/FROZEN. Never touch or evaluate the hamburg area.\n\n"
        "FIXED CONTRACTS (restate, do not break):\n"
        "1. train.py CLI: python -m model.train --area A --out-dir D [--data-dir P] [--epochs N] "
        "[--max-crops-per-bucket M] [--seed S]; writes <out>/models/<area>.onnx and appends a dict to "
        "<out>/train_info.json.\n"
        "2. ONNX export (model.py docstring): one ONNX per area taking 1x3x128x128 float32 in [0,1], returning "
        "[[u, v, conf]] (u,v normalized map coords, conf in [0,1]); must pass pipeline/score.py gates "
        "(<= 4 MiB, host latency proxy <= 250 ms). export_onnx traces forward(dummy) -- forward() must remain "
        "EXACTLY as it is today so the exported graph (and file size, currently 3.30 MiB) is unchanged; the new "
        "aux head must be reachable only via forward_train and therefore absent from the ONNX.\n"
        "3. Keep the C4 stack order [x, r90, r180, r270] (rotation-major) -- the identity block is the first N "
        "rows of the 4N stack.\n\n"
        "model/model.py changes:\n"
        "a. Module constant AUX_PATCH_WEIGHT = 0.5 near DECODE_BETA.\n"
        "b. In TinyLocNet.__init__, after self.conf_head: self.aux_patch_head = nn.Conv2d(feat_ch, "
        "grid_k * grid_k, 1)  (feat_ch is 48; head is train-only, never in forward()).\n"
        "c. New method forward_train(self, x): identical computation to forward(x, return_logits=True) but "
        "additionally computes fmap_id = the first n rows of the trunk feature map (the identity rotation of the "
        "C4 stack, i.e. fmap[:n] where n = x.shape[0]) and aux_logits = self.aux_patch_head(fmap_id)  "
        "[N, grid_k*grid_k, 8, 8]; returns (out, logits, aux_logits). Implement by refactoring the shared body "
        "into a private helper so forward() and forward_train() cannot drift apart -- but forward()'s signature, "
        "outputs, and traced graph must be unchanged (verify: export still ~3.30 MiB, and "
        "onnx graph contains no aux_patch_head weights).\n"
        "d. New function aux_patch_loss(aux_logits, patch_uv):\n"
        "   n, kk, h, w = aux_logits.shape          # [N, 1024, 8, 8]\n"
        "   z = aux_logits.permute(0, 2, 3, 1).reshape(n * h * w, kk)   # row-major (i=row, j=col)\n"
        "   t = patch_uv.reshape(n * h * w, 2)\n"
        "   then exactly loss_fn's Gaussian-CE block: du = (cell_u - t[:,0:1])*k, dv likewise, "
        "g = exp(-(du^2+dv^2)/(2*TARGET_SIGMA_CELLS^2)), normalize, ce = -(g * log_softmax(z)).sum(1).mean(); "
        "return ce. CRITICAL: patch_uv's 64-per-crop ordering must be row-major to match the permute -- index "
        "k = i*8 + j with i the fmap ROW (image y) and j the COLUMN (image x).\n"
        "e. Update the module docstring with a short exp-21 note: per-patch place supervision is train-only deep "
        "supervision; the deployed graph is unchanged.\n\n"
        "model/train.py changes:\n"
        "a. Import aux_patch_loss (and AUX_PATCH_WEIGHT) from model.model.\n"
        "b. In sample_epoch: alongside ys, build ys_patch. Precompute once (module level or top of function) the "
        "64x2 float array D of crop-plane offsets in px, ROW-MAJOR over the 8x8 feature grid: for i in range(8) "
        "(row, image y), for j in range(8) (col, image x): D[i*8+j] = ((j+0.5)*16 - 64, (i+0.5)*16 - 64)  "
        "# (dx, dy). For each sampled crop with center (cx, cy) and heading angle deg (the same value passed to "
        "extract_crop): th = radians(angle); R = [[cos th, -sin th], [sin th, cos th]]; map offsets Dm = D @ R.T "
        "(i.e. map_dx = cos*dx - sin*dy, map_dy = sin*dx + cos*dy). This sign convention was verified "
        "numerically against pipeline.dataset.extract_crop at angles 0/90/30/217: a marker at map offset m "
        "appears in the crop at offset d with m = R(angle) @ d. Patch targets: "
        "u_k = (cx + Dm[k,0]) / meta['width'], v_k = (cy + Dm[k,1]) / meta['height']. Append the [64,2] float32 "
        "array to ys_patch in the SAME loop iteration that appends to xs/ys, so ordering stays aligned. Return "
        "(x, y, y_patch) with y_patch = torch.tensor(np.stack(ys_patch), dtype=torch.float32)  [N, 64, 2]. "
        "(~18 MB at 36k crops -- fine.)\n"
        "c. In train_area's epoch loop: unpack x, y, y_patch = sample_epoch(...); inside the minibatch loop take "
        "ypb = y_patch[idx].to(device) alongside yb; call out, logits, aux_logits = model.forward_train(xb); "
        "loss = loss_fn(out, logits, yb) + AUX_PATCH_WEIGHT * aux_patch_loss(aux_logits, ypb). Keep del x, y "
        "(add y_patch) at epoch end.\n"
        "d. calibrate_conf_shift is untouched (it calls model(xb) -- still valid).\n"
        "e. In the info dict add: \"aux_patch_supervision\": True, \"aux_patch_weight\": 0.5. Keep the existing "
        "init string and other keys.\n"
        "f. Do NOT change epochs, max-crops default (6000), LRs, seeds/rng usage (epoch_rng draws must stay in "
        "the same order: note ys_patch construction must not consume extra rng draws -- it is deterministic "
        "geometry from already-drawn cx, cy, angle), uint8 tensor scheme, or the calibration/export sequence.\n\n"
        "Sanity checks the implementer should run before finishing (cheap, no training): (1) "
        "model.forward_train(torch.zeros(2,3,128,128)) returns shapes (2,3), (2,1024), (2,1024,8,8); (2) "
        "aux_patch_loss on those aux_logits with a valid patch_uv tensor returns a finite scalar ~= "
        "log(1024)-ish; (3) export_onnx on a fresh model produces a file within 1% of 3.30 MiB and "
        "onnxruntime runs it; (4) the D-matrix probe: for angle=90, D[0]=( -56,-56) maps to Dm=(56,-56)."
    ),
}

with open("runs/pending_experiment.json", "w") as f:
    json.dump(exp, f, indent=1)
print("written", len(json.dumps(exp)), "bytes")
