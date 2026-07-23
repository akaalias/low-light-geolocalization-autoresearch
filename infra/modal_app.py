"""Modal serverless GPU training for the autoresearch loop.

The laptop stays the single source of truth and single git writer; this is a
STATELESS remote trainer — it holds only data/ (a Volume) + the frozen pipeline
(baked into the image) + a persistent render-cache Volume, trains whatever
model/ code the laptop pushes as function args, and returns the ONNX +
train_info. It touches no git, so the old two-writer divergence cannot recur.

Deploy:   modal deploy infra/modal_app.py
Call:     via infra/modal_client.py (loop.sh's REMOTE_BACKEND=modal path)
Data:     one-time  ->  modal volume put lowlight-data data/<area> <area>
"""
import modal

app = modal.App("lowlight-train")

# Frozen pipeline + config baked in; training deps installed. model/ is NOT
# baked — it changes every experiment and is passed in as function args.
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch>=2.4", "torchvision>=0.19", "numpy", "rasterio",
        "pillow", "onnx", "onnxruntime", "pyyaml", "affine",
    )
    .add_local_dir("pipeline", "/repo/pipeline")
    .add_local_file("areas.yaml", "/repo/areas.yaml")
)

data_vol = modal.Volume.from_name("lowlight-data", create_if_missing=True)
cache_vol = modal.Volume.from_name("lowlight-render-cache", create_if_missing=True)


@app.function(
    image=image,
    gpu="A100",
    timeout=5400,
    volumes={"/repo/data": data_vol, "/repo/render_cache": cache_vol},
)
def train_area(area: str, model_py: str, train_py: str, epochs: int, crops: int) -> dict:
    """Train one area on the GPU; return {ok, onnx bytes, train_info} or {ok:False, log}."""
    import os
    import pathlib
    import subprocess

    m = pathlib.Path("/repo/model")
    m.mkdir(parents=True, exist_ok=True)
    (m / "__init__.py").write_text("")
    (m / "model.py").write_text(model_py)
    (m / "train.py").write_text(train_py)

    out = "/tmp/out"
    env = dict(os.environ, PYTHONPATH="/repo", RENDER_CACHE="/repo/render_cache",
               OMP_NUM_THREADS="8", MKL_NUM_THREADS="8", PYTHONUNBUFFERED="1")
    # Stream (do NOT capture) so render + per-epoch progress is visible live in
    # `modal app logs` — a blind capture once hid a 20-min run entirely.
    r = subprocess.run(
        ["python", "-u", "-m", "model.train", "--area", area, "--out-dir", out,
         "--data-dir", "/repo/data", "--epochs", str(epochs),
         "--max-crops-per-bucket", str(crops)],
        cwd="/repo", env=env,
    )
    cache_vol.commit()  # persist any newly-rendered relight realizations
    if r.returncode != 0:
        return {"ok": False, "log": "training failed on the GPU — see `modal app logs lowlight-train`"}
    onnx = pathlib.Path(f"{out}/models/{area}.onnx").read_bytes()
    info = pathlib.Path(f"{out}/train_info.json").read_text()
    return {"ok": True, "onnx": onnx, "train_info": info}
