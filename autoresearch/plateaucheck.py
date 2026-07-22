"""Not frozen (harness tooling, invoked by loop.sh only).

Diagnoses *what the pivot mechanism was missing*: loop.sh's PATIENCE
preamble told a plateaued design agent to "pick a design family absent
from the last N experiments" from a suggested list (dispatcher, learned
relighting, coordinate parameterization, ...) — but nothing checked
whether the resulting design actually changed anything structural. An
agent could pick "dispatcher + lighting specialists" off the list, bolt it
onto the same frozen pretrained trunk and descriptor every prior attempt
also left untouched, and technically comply. Experiments #30-34 all did
exactly this: nine straight rounds where "Feature extractor" and "Layout
summary" never appear as `"changed": true` in any kept experiment's
architecture_svg stage list, while dispatcher/loss/sampling satellites
around them kept churning.

This computes, per stage name, how many of the MOST RECENT consecutive
development experiments (since the last kept one) left that stage
unchanged — a streak, not just "ever touched since the last kept" — so a
stage that was touched once early in a long losing streak and then never
revisited again still gets flagged as frozen. Excludes the two stage
names that are the genuinely frozen harness contract (Camera frame,
Output) since those are outside the search space by design, not evidence
of an unexamined assumption.

Usage: python -m autoresearch.plateaucheck <last_kept_id>
Prints nothing if no stage has been frozen for >= PATIENCE rounds;
otherwise prints a directive block for loop.sh to inject into the pivot
preamble. Exit code is always 0 (advisory, never blocks the loop).
"""
import json
import sys

from autoresearch.db import connect

PATIENCE = 4  # mirrors loop.sh's PATIENCE default; restated here since this
              # runs as its own process, not sourced by the shell script
HARNESS_CONTRACT_STAGES = {"Camera frame", "Output"}


def frozen_streaks(conn, since_kept_id: int) -> dict[str, int]:
    rows = conn.execute(
        "SELECT arch_json FROM experiments WHERE id > ? AND kind='development' "
        "AND arch_json IS NOT NULL ORDER BY id DESC",
        (since_kept_id,),
    ).fetchall()
    streak: dict[str, int] = {}
    alive: set[str] | None = None
    for (raw,) in rows:
        try:
            stages = json.loads(raw).get("stages", [])
        except (TypeError, json.JSONDecodeError):
            continue
        stagemap = {s.get("name"): bool(s.get("changed"))
                    for s in stages if s.get("name")}
        if alive is None:
            alive = set(stagemap) - HARNESS_CONTRACT_STAGES
        for name in list(alive):
            if stagemap.get(name, False):
                alive.discard(name)
            else:
                streak[name] = streak.get(name, 0) + 1
    return streak


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: plateaucheck.py <last_kept_id>", file=sys.stderr)
        return 0
    since_kept_id = int(sys.argv[1])
    conn = connect()
    streak = frozen_streaks(conn, since_kept_id)
    frozen = sorted(((n, c) for n, c in streak.items() if c >= PATIENCE),
                     key=lambda x: -x[1])
    if not frozen:
        return 0
    print("These parts of the design have not changed in ANY of the last "
          f"{frozen[0][1]} experiments:")
    for name, cnt in frozen:
        print(f"  - {name} (unchanged {cnt} rounds running)")
    print(
        "A genuine pivot MUST change at least one of these — the ones "
        "closest to the model's actual representational capacity "
        "(feature extraction, descriptor construction, decode) count far "
        "more than a training-signal or output-adjacent tweak. Adding a "
        "new satellite module (a gate, a head, an auxiliary loss, a "
        "sampler) around an unquestioned backbone is NOT a pivot, even if "
        "it comes from the suggested list below and even if it trains a "
        "new component from scratch — the backbone itself is the thing "
        "that has gone unexamined."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
