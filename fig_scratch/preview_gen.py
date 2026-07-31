import json, sys
sys.path.insert(0, "fig_scratch")
from run_middle import composite

mid = json.load(open("fig_scratch/middle_v2_4.json"))["middle_svg"]
open("fig_scratch/preview_4.svg", "w").write(composite(mid))
print("ok")
