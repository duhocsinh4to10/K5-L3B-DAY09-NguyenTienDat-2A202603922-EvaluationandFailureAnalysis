"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item
from lab9.graders import GRADERS


def _is_bad_number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and (math.isnan(v) or math.isinf(v))


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate."""
    problems: list[str] = []

    if pr.get("evaluator_failures"):
        problems.append(f"evaluator_failures non-empty ({len(pr['evaluator_failures'])})")
    if base.get("evaluator_failures"):
        problems.append("baseline has evaluator_failures")

    pr_metrics = pr.get("metrics") or {}
    for k, v in pr_metrics.items():
        if v is None or _is_bad_number(v):
            problems.append(f"metric {k!r} is {v!r}")
    for m in spec.get("metrics") or []:
        mid = m["id"]
        if mid not in pr_metrics or pr_metrics[mid] is None or _is_bad_number(pr_metrics[mid]):
            problems.append(f"spec metric {mid!r} missing or invalid in PR metrics")

    pr_manifest = pr.get("manifest") or {}
    base_manifest = base.get("manifest") or {}
    pr_rows = pr.get("rows") or []
    base_rows = base.get("rows") or []

    expected_count = int(pr_manifest.get("items") or 0) * len(pr_manifest.get("seeds") or [])
    if len(pr_rows) != expected_count:
        problems.append(f"row count {len(pr_rows)} != manifest items*seeds ({expected_count})")
    if len(pr_rows) != len(base_rows):
        problems.append(f"PR row count {len(pr_rows)} != baseline row count {len(base_rows)}")
    if list(pr_manifest.get("seeds") or []) != list(base_manifest.get("seeds") or []):
        problems.append("manifest seeds differ from baseline")
    if pr_manifest.get("items") != base_manifest.get("items"):
        problems.append("manifest items count differs from baseline")

    pr_pairs = [(r.get("item_id"), r.get("seed")) for r in pr_rows]
    base_pairs = [(r.get("item_id"), r.get("seed")) for r in base_rows]
    if len(set(pr_pairs)) != len(pr_rows):
        problems.append("duplicate (item_id, seed) rows in PR")
    if set(pr_pairs) != set(base_pairs):
        problems.append("(item_id, seed) set of PR differs from baseline")

    base_by_pair = {(r.get("item_id"), r.get("seed")): r for r in base_rows}
    row_metric_ids = [
        m["id"]
        for m in (spec.get("metrics") or [])
        if m["id"] in GRADERS or any(m["id"] in r for r in base_rows) or any(m["id"] in r for r in pr_rows)
    ]
    for r in pr_rows:
        pair = (r.get("item_id"), r.get("seed"))
        for mid in row_metric_ids:
            val = r.get(mid)
            if val is None or _is_bad_number(val):
                problems.append(f"row {pair} has missing/NaN value for {mid!r}")
        if pair in base_by_pair:
            pr_slices = sorted(r.get("slices") or [])
            base_slices = sorted(base_by_pair[pair].get("slices") or [])
            if pr_slices != base_slices:
                problems.append(f"slice tags for {pair} differ from baseline: {pr_slices} != {base_slices}")

    if pr_rows and not problems:
        for m in spec.get("metrics") or []:
            mid = m["id"]
            if mid in row_metric_ids and mid in pr_metrics and isinstance(pr_metrics[mid], (int, float)):
                vals = [r.get(mid) for r in pr_rows if isinstance(r.get(mid), (bool, int, float))]
                if len(vals) == len(pr_rows) and vals:
                    expected_val = sum(vals) if m.get("kind") == "safety" else round(sum(vals) / len(vals), 4)
                    if abs(float(pr_metrics[mid]) - float(expected_val)) > 1e-3:
                        problems.append(f"metric {mid!r}={pr_metrics[mid]} disagrees with row aggregate {expected_val}")

    if base_spec is not None:
        if spec.get("eval_set_version") == base_spec.get("eval_set_version"):
            spec_metrics = {m["id"]: m for m in (spec.get("metrics") or [])}
            for bm in base_spec.get("metrics") or []:
                mid = bm["id"]
                if mid not in spec_metrics:
                    problems.append(f"ratchet: metric {mid!r} removed from spec")
                    continue
                pm = spec_metrics[mid]
                if bm.get("blocking") and not pm.get("blocking"):
                    problems.append(f"ratchet: metric {mid!r} became non-blocking")
                bth = bm.get("threshold") or {}
                pth = pm.get("threshold") or {}
                if "min" in bth and ("min" not in pth or pth["min"] < bth["min"]):
                    problems.append(f"ratchet: metric {mid!r} min loosened ({pth.get('min')} < {bth['min']})")
                if "max" in bth and ("max" not in pth or pth["max"] > bth["max"]):
                    problems.append(f"ratchet: metric {mid!r} max loosened ({pth.get('max')} > {bth['max']})")
                if "max_increase" in bth and ("max_increase" not in pth or pth["max_increase"] > bth["max_increase"]):
                    problems.append(f"ratchet: metric {mid!r} max_increase loosened")
                if bth.get("no_significant_drop") and not pth.get("no_significant_drop"):
                    problems.append(f"ratchet: metric {mid!r} dropped no_significant_drop")

            spec_slices = {(s["name"], s["metric"]): s for s in (spec.get("slices") or [])}
            for bs in base_spec.get("slices") or []:
                skey = (bs["name"], bs["metric"])
                if skey not in spec_slices:
                    problems.append(f"ratchet: slice {skey} removed from spec")
                    continue
                ps = spec_slices[skey]
                if bs.get("blocking") and not ps.get("blocking"):
                    problems.append(f"ratchet: slice {skey} became non-blocking")
                if "min" in bs and ("min" not in ps or ps["min"] < bs["min"]):
                    problems.append(f"ratchet: slice {skey} min loosened ({ps.get('min')} < {bs['min']})")
                if "max" in bs and ("max" not in ps or ps["max"] > bs["max"]):
                    problems.append(f"ratchet: slice {skey} max loosened ({ps.get('max')} > {bs['max']})")
                if bs.get("no_significant_drop") and not ps.get("no_significant_drop"):
                    problems.append(f"ratchet: slice {skey} dropped no_significant_drop")

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked: list[str] = []
    lines: list[str] = []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices") or []:
        name, metric = s["name"], s["metric"]
        sid = f"slice:{name}/{metric}"
        a = per_item(pr, metric, slice_name=name)
        b = per_item(base, metric, slice_name=name)
        val = round(sum(a.values()) / len(a), 4) if a else None
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in s and val > s["max"]:
            verdict = "fail"
        elif "min" in s and val < s["min"]:
            verdict = "fail"
        if s.get("no_significant_drop") and val is not None:
            keys = sorted(set(a) & set(b))
            if keys:
                d, lo, hi = stats.paired_bootstrap(
                    [a[k] for k in keys],
                    [b[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000),
                    rng=bs.get("rng", 2027),
                )
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        if verdict != "ok" and s.get("blocking"):
            blocked.append(sid)
        th_info = {k: s[k] for k in ("min", "max", "no_significant_drop") if k in s}
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if s.get("blocking") else "warn")
        lines.append(f"  {sid:<22} {val!s:<8} {json.dumps(th_info):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
