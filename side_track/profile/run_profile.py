"""Call the already-deployed Modal trainer with the instrumented train.py,
for one area, at the real training recipe (epochs=8 -> 24 actual epochs).
Isolated from the live repo: model/model.py is read unmodified, train.py
comes from this side_track scratch file -- nothing here touches the
working tree the autoresearch loop is using for iter 61.
"""
import json
import pathlib
import sys

import modal

AREA = sys.argv[1] if len(sys.argv) > 1 else "berlin"
EPOCHS = int(sys.argv[2]) if len(sys.argv) > 2 else 8
CROPS = int(sys.argv[3]) if len(sys.argv) > 3 else 6000

fn = modal.Function.from_name("lowlight-train", "train_area")
res = fn.remote(
    AREA,
    pathlib.Path("model/model.py").read_text(),
    pathlib.Path("side_track/profile/train_instrumented.py").read_text(),
    EPOCHS, CROPS,
)
if not res.get("ok"):
    sys.stderr.write("profiling run failed on the GPU:\n" + (res.get("log") or "") + "\n")
    sys.exit(1)

info_list = json.loads(res["train_info"])
out = pathlib.Path("side_track/profile") / f"{AREA}_train_info.json"
out.write_text(json.dumps(info_list, indent=2))
print(f"wrote {out}")
print(json.dumps(info_list[-1], indent=2))
