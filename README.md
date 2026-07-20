# UAV Low-Light Geolocalization — Autoresearch

Given a geographic bounding box, this repo trains a compact per-area model
that takes a single low-light camera frame from a UAV and returns
`estimate_position(frame) -> (lat, lon, confidence)` — no reference imagery
on the aircraft, no connectivity, targeting an ESP32-P4 companion board.
The interesting part: the model-side code is improved by an **autonomous
research loop** (Karpathy `autoresearch`-style) that designs experiments,
rewrites architecture/loss/training, and keeps or reverts by a single frozen
metric. Full context: `CLAUDE.md`.

## Repo layout

| Path | Status | What |
|---|---|---|
| `pipeline/` | **FROZEN** | bbox-generic fetch (Sentinel-2, open-licensed), 6-bucket synthetic low-light relighting, deterministic train/eval split, §6 scoring with ESP32-P4 deployment gates |
| `areas.yaml` | **FROZEN** | 4 development areas + hamburg blind holdout |
| `model/` | agent-editable | model architecture + training procedure (the loop's playground) |
| `autoresearch/` | mostly frozen | `loop.sh` harness, SQLite schema + logger, gallery renderer, per-iteration agent prompt |
| `FROZEN` | — | the exact list of files the loop may never touch (enforced by `loop.sh` via git revert) |
| `runs/` | generated | per-experiment artifacts (models, metrics, heatmaps, samples) |
| `experiments.sqlite` | generated | full experiment lineage: hypothesis, method, expected outcome, result, conclusion, all metrics |
| `gallery/index.html` | generated | self-refreshing visual lineage (samples + error heatmaps) |

## Quickstart (already proven end-to-end by the bootstrap run)

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python numpy pillow rasterio pystac-client torch onnx onnxruntime pyyaml

# Frozen pipeline — any bbox works, named areas are just presets:
.venv/bin/python -m pipeline.fetch --area berlin          # or: --name x --bbox w,s,e,n
.venv/bin/python -m pipeline.relight --area berlin
.venv/bin/python -m model.train --area berlin --out-dir runs/test --epochs 3
.venv/bin/python -m pipeline.score --areas berlin --model-dir runs/test/models --out runs/test/metrics.json
.venv/bin/python -m autoresearch.gallery                  # open gallery/index.html
```

Bootstrap proving run (commit `15b43a2`): berlin + prignitz through the
unmodified pipeline, naive TinyLocNet baseline → **2926 m** worst-case median
error (target ≤ 20 m; a center-guess on a 7 km box is ~2.9 km, i.e. the
baseline has learned almost nothing — deliberately). All deployment gates
passed. Logged as experiment #1 in `experiments.sqlite`.

## Phase 2 — running the autoresearch loop (run this yourself, separately)

```bash
# once: fetch + relight the remaining areas
for a in munich frankfurt hamburg; do
  .venv/bin/python -m pipeline.fetch --area $a
  .venv/bin/python -m pipeline.relight --area $a
done

# then let it run (each iteration: headless Claude designs ONE experiment,
# edits model/, harness trains 4 areas + scores + logs + keeps/reverts):
./autoresearch/loop.sh 25          # 25 iterations
EPOCHS=15 ./autoresearch/loop.sh 50
SKIP_AGENT=1 ./autoresearch/loop.sh 1   # smoke-test harness without an agent
```

Per iteration the agent must pre-register `title / category / hypothesis /
method / expected_outcome` (written to the run's `experiment.json`); the
harness appends measured `result` and a kept/reverted `conclusion`, logs
everything to SQLite, and commits kept improvements so git history is the
research trail. Every 5 kept improvements it runs the read-only **hamburg
holdout check** (§5) — logged, never fed back into keep/revert, and
`pipeline/score.py` hard-refuses to score hamburg without `--holdout`.

Watch progress: `open gallery/index.html` (auto-refreshes every 30 s), or
`sqlite3 experiments.sqlite "SELECT id,title,primary_metric,kept FROM experiments ORDER BY id DESC LIMIT 10;"`

### Running on RunPod (manual step, v1)

Training is per-area independent; one GPU per experiment is plenty.

1. Create a RunPod GPU pod (any CUDA image with Python ≥ 3.11), put your key
   in `.env` as `RUNPOD_API_KEY` if you later script it (nothing reads it yet).
2. `git clone` this repo onto the pod, run the Quickstart install, and
   `rsync data/` up (or re-run fetch — it's credential-free).
3. Run `./autoresearch/loop.sh` there with `claude` CLI authenticated
   (`CLAUDE_BIN` env var if the binary lives elsewhere). `model/train.py`
   auto-selects cuda > mps > cpu.
4. `rsync` back `experiments.sqlite`, `runs/`, and push the git branch to
   keep lineage local.

## Reference imagery (pipeline data v2) & licensing

Fetching is driven by a **source registry** (`pipeline/sources.yaml`,
frozen): for any bbox, the finest open-licensed source covering it wins,
falling back to global Sentinel-2. The pipeline code stays fully
bbox-generic — regional knowledge is config, not code.

| Source | Covers | Native | License / attribution |
|---|---|---|---|
| [BB-BE DOP20 WMS](https://isk.geobasis-bb.de/mapproxy/dop20c/service/wms?REQUEST=GetCapabilities&SERVICE=WMS) | Brandenburg **+ Berlin** | 20 cm | dl-de/by-2-0 — © GeoBasis-DE/LGB |
| [Bavaria DOP40 WMS](https://geoservices.bayern.de/od/wms/dop/v1/dop40?SERVICE=WMS&REQUEST=GetCapabilities) | Bavaria (Munich) | 40 cm | CC BY 4.0 — © Bayerische Vermessungsverwaltung |
| [Hesse DOP20 WMS](https://www.gds-srv.hessen.de/cgi-bin/lika-services/ogc-free-images.ows?SERVICE=WMS&REQUEST=GetCapabilities) | Hesse (Frankfurt) | 20 cm | dl-de/by-2-0 — © HVBG Hessen |
| [Hamburg DOP WMS](https://geodienste.hamburg.de/wms_dop_zeitreihe_unbelaubt?Service=WMS&Request=GetCapabilities) | Hamburg | 20 cm | dl-de/by-2-0 — © FHH LGV |
| Sentinel-2 L2A (Earth Search STAC → AWS COGs) | global fallback | 10 m | Copernicus — "Contains modified Copernicus Sentinel data" |

Everything is server-resampled to a **1 m/px** reference grid (`target_gsd_m`
in the registry): a 128 px model crop = 128 m ground footprint, matching a
typical UAV camera at ~100 m AGL — so training imagery scale ≈ deployment
imagery scale. No Google/Bing tiles anywhere. Expect roughly 0.5–3 GB of
imagery per area on disk after relighting.

## Validated hardware setup (§9 resolved for bring-up; stretch sensor still open)

**Buy-now, documented-working stack:**

- **Board:** [ESP32-P4-Function-EV-Board](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32p4/esp32-p4-function-ev-board/user_guide.html)
  — Espressif's official P4 dev kit; **ships with a 2 MP MIPI-CSI camera
  module (SC2336)** in the box.
- **Sensor:** SmartSens **SC2336** (2 MP, 1/3", RAW out over MIPI CSI-2;
  SmartSens' "SmartClarity-2" low-light line). Driver ships in Espressif's
  [esp_cam_sensor](https://components.espressif.com/components/espressif/esp_cam_sensor/versions/2.3.0/readme)
  component; the P4's on-chip ISP handles debayer/AWB/denoise
  ([camera driver docs](https://docs.espressif.com/projects/esp-idf/en/stable/esp32p4/api-reference/peripherals/camera_driver.html)),
  and a [community P4+SC2336 example](https://github.com/jeff-cn/esp32-p4-cam) exists.
- **Software path:** esp-video (V4L2-style capture) → esp-dl (quantized CNN
  inference on the P4's PPA/vector unit). Model export here is ONNX, which
  esp-dl's toolchain ingests for int8 quantization.
- For the flight article (vs. dev kit), the same chip + SC2336 module on a
  minimal carrier lands well under the 50 g / 2 W targets of §2.

**Still open (stretch):** a true STARVIS2/IMX585-class starlight sensor on
the P4 has no documented pairing — IMX585 typically wants 4-lane MIPI (P4
has 2) and a custom driver. Path: prove the full system on SC2336 first;
invest in starlight bring-up only if night accuracy turns out sensor-limited.
(The [ams MIRA220 NIR example](https://github.com/ams-OSRAM/esp32_p4_MIPI_DSI_CSI_mira220)
shows third-party sensor bring-up on the P4 is feasible.)

## Adding a new deployment area

`.venv/bin/python -m pipeline.fetch --name myarea --bbox 9.10,48.70,9.20,48.76`
then relight/train/score as above — nothing in the pipeline knows about
specific areas. Only add entries to `areas.yaml` if it should become part of
the frozen evaluation set (that's a human decision, not the loop's).
