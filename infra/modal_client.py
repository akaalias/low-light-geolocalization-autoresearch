"""Call the deployed Modal trainer for one area and write results to out-dir.

Produces the SAME layout as local model.train (models/<area>.onnx +
train_info.json), so loop.sh's merge/score steps are unchanged.

Usage: python infra/modal_client.py <area> <local-out-dir> <epochs> <max-crops-per-bucket>
"""
import pathlib
import sys

import modal


def main():
    area, out_dir, epochs, crops = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    fn = modal.Function.from_name("lowlight-train", "train_area")
    res = fn.remote(area,
                    pathlib.Path("model/model.py").read_text(),
                    pathlib.Path("model/train.py").read_text(),
                    epochs, crops)
    if not res.get("ok"):
        sys.stderr.write("modal train failed on the GPU:\n" + (res.get("log") or "") + "\n")
        sys.exit(1)
    out = pathlib.Path(out_dir)
    (out / "models").mkdir(parents=True, exist_ok=True)
    (out / "models" / f"{area}.onnx").write_bytes(res["onnx"])
    (out / "train_info.json").write_text(res["train_info"])
    print(f"modal train OK: {area}")


if __name__ == "__main__":
    main()
