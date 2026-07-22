"""Not frozen (harness tooling, invoked by loop.sh only).

Fingerprints the model's *backbone identity* from the source that will
actually run, so a demanded pivot can be checked against the code instead of
against the diff or the design agent's self-report.

Why this exists: loop.sh's original post-implementation backbone gate asked
whether the diff contained a REMOVED line matching `mobilenet_v3_small`. Two
independent holes let a pivot keep the champion's backbone anyway:

  1. It only ran when plateaucheck happened to name the "Feature extractor"
     stage, and plateaucheck prints nothing until a stage has been frozen for
     PATIENCE rounds. A short streak -- or an agent that renamed the stage --
     skipped the gate entirely.
  2. Even when it ran, one removed line mentioning the backbone satisfied it.
     Editing `features[:9]` -> `features[:10]`, or rewording a docstring,
     deleted a line matching the pattern and added another just like it.

Experiments through #40 shipped `pretrained:mobilenet_v3_small` through a
demanded pivot five times. The gate never looked at the resulting code.

The rule enforced here: after a demanded pivot, NONE of the champion's
backbone identifiers may still appear in model/. Not re-tuned, not wrapped in
a dispatcher, not kept as one branch of an ensemble -- gone.

Usage:
  python -m autoresearch.backbonecheck --fingerprint FILE [FILE...]
      Print a canonical backbone fingerprint for the given sources.
  python -m autoresearch.backbonecheck --champion FILE [FILE...] \
                                       --candidate FILE [FILE...]
      Print, one per line, every champion backbone identifier still present
      in the candidate sources. Empty output means the pivot is clean.

Exit code is always 0; loop.sh decides what to do with the output.
"""
import re
import sys
from pathlib import Path

# Backbone constructors an agent might import as a trunk (torchvision names,
# plus the handful of timm spellings that differ). Matched as whole
# identifiers so mobilenet_v3_small and mobilenet_v3_large stay distinct --
# swapping small for large IS a different backbone and should pass.
BACKBONE_RE = re.compile(
    r"\b("
    r"mobilenet_v2|mobilenet_v3_small|mobilenet_v3_large|"
    r"mnasnet\d+_\d+|"
    r"resnet\d+|resnext\d+_\w+|wide_resnet\d+_\d+|"
    r"efficientnet_b\d|efficientnet_v2_[sml]|"
    r"shufflenet_v2_x\d+_\d+|"
    r"squeezenet1_[01]|"
    r"regnet_[xy]_\w+|"
    r"convnext_(?:tiny|small|base|large)|"
    r"vit_[bhl]_\d+|swin_[tsbv]\w*|maxvit_t|"
    r"densenet\d+|vgg\d+(?:_bn)?|alexnet|googlenet|inception_v3"
    r")\b"
)
# A checked-in weights blob is part of the backbone's identity too: reusing
# model/pretrained/mnv3s_features8.pt is reusing the backbone whatever the
# surrounding code is called.
WEIGHTS_RE = re.compile(r"pretrained/([\w.\-]+\.(?:pt|pth|bin|safetensors))\b")


def _read(paths: list[str]) -> str:
    out = []
    for p in paths:
        if p == "-":
            out.append(sys.stdin.read())
            continue
        f = Path(p)
        if f.exists():
            out.append(f.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(out)


def identifiers(src: str) -> set[str]:
    """Backbone identifiers present in `src`.

    Line comments are stripped: a backbone named only in a trailing comment
    is history, not code that runs. Docstrings are deliberately NOT stripped
    -- an identifier left in prose still counts, which can only ever make the
    check stricter, never let a real reuse through.
    """
    code = re.sub(r"#[^\n]*", "", src)
    return set(BACKBONE_RE.findall(code)) | set(WEIGHTS_RE.findall(code))


def fingerprint(src: str) -> str:
    names = sorted(identifiers(src))
    return ",".join(names) if names else "scratch"


def _split_args(argv: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    current = None
    for a in argv:
        if a.startswith("--"):
            current = a[2:]
            groups.setdefault(current, [])
        elif current:
            groups[current].append(a)
    return groups


def main(argv: list[str]) -> int:
    groups = _split_args(argv)
    if "fingerprint" in groups:
        print(fingerprint(_read(groups["fingerprint"])))
        return 0
    if "champion" in groups and "candidate" in groups:
        champ = identifiers(_read(groups["champion"]))
        cand = identifiers(_read(groups["candidate"]))
        for name in sorted(champ & cand):
            print(name)
        return 0
    print(__doc__.strip().splitlines()[0], file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
