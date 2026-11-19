"""Auto mode: idea -> requirements -> Figma design -> plan -> Harness work -> tests -> visual match, without prompts.

The developer authorizes a whole auto run once, by typing /spec2ship-auto (the UserPromptSubmit hook records that
intent, like /spec2ship-approve). Plans are then approved automatically for that run only, and every approval is
labeled as automatic. The run ends when the tests pass and every screen matches its Figma frame, when the fix-round
limit is reached (BLOCKED), or when something needs the developer (BLOCKED).
"""
from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path
from typing import Any

from .common import Spec2ShipError, now_iso, read_json, write_json

AUTO_INTENT_FILE = ".auto-intent.json"
AUTO_INTENT_MAX_AGE_MIN = 30
LOOP_FILE = ".auto-loop.json"
DEFAULT_MAX_ROUNDS = 3
DEFAULT_THRESHOLD = 0.92
# Per-channel difference (0-255) under which two pixels count as equal. Figma and the browser rasterize text and
# anti-aliasing differently, so exact equality is never reached.
PIXEL_TOLERANCE = 40
MAX_CONTINUATIONS = 60          # Stop-hook continuations per run
MAX_SAME_STATE_CONTINUATIONS = 6  # consecutive continuations with no state change -> give up and let the turn end
SCREENS_FILE = Path("design") / "screens.json"
TERMINAL = ("COMPLETED", "BLOCKED")


# ------------------------------------------------------------------ authorization

def record_intent(ws: Path, prompt: str) -> None:
    write_json(ws / AUTO_INTENT_FILE, {"at": now_iso(), "prompt": prompt.strip()[:500]})


def consume_intent(ws: Path) -> dict[str, Any]:
    if os.environ.get("SPEC2SHIP_REQUIRE_APPROVAL_INTENT", "1") == "0":
        return {"at": now_iso(), "prompt": "(intent check disabled)"}
    p = ws / AUTO_INTENT_FILE
    if not p.exists():
        raise Spec2ShipError(
            "No developer authorization for auto mode. The developer must type /spec2ship:spec2ship-auto <idea> "
            "themselves (the UserPromptSubmit hook records it). Claude must not start auto mode on its own."
        )
    data = read_json(p)
    p.unlink()
    at = _dt.datetime.fromisoformat(data["at"])
    age = (_dt.datetime.now(_dt.timezone.utc) - at).total_seconds() / 60
    if age > AUTO_INTENT_MAX_AGE_MIN:
        raise Spec2ShipError(f"Auto-mode authorization is {age:.0f} minutes old; type /spec2ship:spec2ship-auto again.")
    return data


def new_auto(intent: dict[str, Any], max_rounds: int, threshold: float) -> dict[str, Any]:
    if max_rounds < 0:
        raise Spec2ShipError("--max-rounds must be 0 or more")
    if not 0 < threshold <= 1:
        raise Spec2ShipError("--threshold must be in (0, 1]")
    return {"authorized_at": intent["at"], "authorized_prompt": intent.get("prompt", ""), "max_rounds": max_rounds,
            "threshold": threshold, "approvals": 0}


# ------------------------------------------------------------------ next step

def next_step(ws: Path, st: dict[str, Any]) -> str:
    """One-line instruction for the agent: what auto mode does next (used by the Stop hook and `status`)."""
    s = st["state"]
    has = lambda rel: (ws / rel).exists()  # noqa: E731
    if s == "INIT":
        return "run `preflight` (step 2 of /spec2ship-auto)"
    if s == "PREFLIGHT":
        return "run `parse-ba` and `repo-analyze` (step 3)"
    if s in ("ANALYSIS", "REQUIREMENT_REVIEW"):
        if not has("analysis/requirements.json"):
            return "write analysis/requirements.json from the idea, resolving open questions as recorded assumptions (step 3)"
        if not has(str(SCREENS_FILE)):
            return "draw the screens in Figma with the figma-design skill and write design/screens.json (step 4)"
        if not has("analysis/figma-context.json"):
            return "capture the drawn frames into analysis/figma-context.json (step 4)"
        if not has("mappings/figma-mapping.json"):
            return "map requirements to the drawn frames (step 5)"
        return "write planning/tasks.json with the fullstack-planning skill, then run `plan-review` (step 6)"
    if s == "PLANNING":
        return "finish planning/tasks.json and run `plan-review` (step 6)"
    if s == "PLAN_REVIEW":
        return "run `approve --auto` (step 7)"
    if s == "APPROVED":
        return "run `handoff`, then Harness `harness-work all` (step 8)"
    if s == "EXECUTION":
        return "let Harness finish the tasks; when done, `transition REVIEW` (step 8)"
    if s == "REVIEW":
        return "`transition VERIFICATION`, run the project checks and the visual check (step 9)"
    if s == "VERIFICATION":
        return "finish checks, evidence and `visual-compare`; then COMPLETED, or start a fix round (steps 9-10)"
    return f"state {s}"


# ------------------------------------------------------------------ Stop hook

def stop_decision(ws: Path, st: dict[str, Any]) -> dict[str, Any] | None:
    """Hook output that keeps an auto run going after each reply, or None to let the turn end."""
    auto = st.get("auto")
    if not auto or st["state"] in TERMINAL:
        return None
    p = ws / LOOP_FILE
    loop = read_json(p) if p.exists() else {"run_id": st["run_id"], "total": 0, "same": 0, "last_state": None}
    if loop.get("run_id") != st["run_id"]:
        loop = {"run_id": st["run_id"], "total": 0, "same": 0, "last_state": None}
    loop["same"] = loop["same"] + 1 if loop.get("last_state") == st["state"] else 1
    loop["last_state"] = st["state"]
    loop["total"] += 1
    write_json(p, loop)
    if loop["total"] > MAX_CONTINUATIONS or loop["same"] > MAX_SAME_STATE_CONTINUATIONS:
        why = (f"{MAX_CONTINUATIONS} automatic continuations" if loop["total"] > MAX_CONTINUATIONS
               else f"{MAX_SAME_STATE_CONTINUATIONS} continuations without leaving {st['state']}")
        return {"systemMessage": f"Spec2Ship auto mode paused after {why}. Run /spec2ship:spec2ship-status, fix what "
                                 "is stuck, then tell Claude to continue the auto run."}
    return {"decision": "block",
            "reason": (f"Spec2Ship auto mode is still running (state {st['state']}). Do not stop and do not ask the "
                       f"developer. Next: {next_step(ws, st)}. Follow /spec2ship:spec2ship-auto. If something truly "
                       "needs the developer, run `transition BLOCKED --reason ...` and stop.")}


# ------------------------------------------------------------------ visual comparison

def _load_rgb(path: Path):
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        raise Spec2ShipError("Visual comparison needs Pillow: `pip install pillow`.") from None
    if not path.exists():
        raise Spec2ShipError(f"Screenshot not found: {path}")
    return Image.open(path).convert("RGB")


def compare_images(design: Path, actual: Path, diff_out: Path | None = None) -> dict[str, Any]:
    """Similarity of a browser screenshot to a Figma export, in [0, 1].

    The actual screenshot is scaled to the design width (Figma exports often use 2x). Both images are compared on the
    design's area; rows missing from the shorter image count as different. A pixel matches when every channel is
    within PIXEL_TOLERANCE.
    """
    from PIL import Image, ImageChops  # type: ignore

    d = _load_rgb(design)
    a = _load_rgb(actual)
    if a.width != d.width:
        a = a.resize((d.width, max(1, round(a.height * d.width / a.width))), Image.BILINEAR)
    h = max(d.height, a.height)
    canvas_d = Image.new("RGB", (d.width, h), (255, 0, 255))
    canvas_a = Image.new("RGB", (d.width, h), (0, 255, 0))
    canvas_d.paste(d, (0, 0))
    canvas_a.paste(a, (0, 0))
    diff = ImageChops.difference(canvas_d, canvas_a)
    mask = diff.convert("L").point(lambda v: 255 if v > PIXEL_TOLERANCE else 0)
    # convert("L") averages channels; also catch a single channel far off
    for band in diff.split():
        mask = ImageChops.lighter(mask, band.point(lambda v: 255 if v > PIXEL_TOLERANCE else 0))
    total = d.width * h
    bad = total - mask.histogram()[0]
    score = 1 - bad / total if total else 0.0
    if diff_out is not None:
        diff_out.parent.mkdir(parents=True, exist_ok=True)
        overlay = Image.blend(canvas_d, Image.new("RGB", canvas_d.size, (255, 255, 255)), 0.6)
        overlay.paste((255, 0, 0), mask=mask)
        overlay.save(diff_out)
    return {"score": round(score, 4), "design_size": [d.width, d.height], "actual_size_scaled": [a.width, a.height],
            "differing_pixels": bad, "compared_pixels": total}


def load_screens(ws: Path) -> list[dict[str, Any]]:
    p = ws / SCREENS_FILE
    if not p.exists():
        raise Spec2ShipError(f"{SCREENS_FILE} is missing; the figma-design step writes it.")
    data = read_json(p)
    screens = data.get("screens") or []
    if not screens:
        raise Spec2ShipError(f"{SCREENS_FILE} lists no screens.")
    return screens


def compare_all(ws: Path, root: Path, threshold: float) -> dict[str, Any]:
    results = []
    for s in load_screens(ws):
        ref = Path(s["reference"])
        ref = ref if ref.is_absolute() else ws / ref
        act = Path(s.get("actual") or f"verification/screens/{s['id']}.png")
        act = act if act.is_absolute() else ws / act
        rec: dict[str, Any] = {"screen": s["id"], "route": s.get("route"), "node_id": s.get("node_id"),
                               "reference": str(ref), "actual": str(act)}
        try:
            rec.update(compare_images(ref, act, ws / "verification" / "screens" / f"{s['id']}.diff.png"))
            rec["status"] = "PASS" if rec["score"] >= threshold else "FAIL"
        except Spec2ShipError as e:
            rec.update({"status": "NOT_RUN", "error": str(e)})
        results.append(rec)
    ok = all(r["status"] == "PASS" for r in results)
    out = {"schema_version": "1.0", "at": now_iso(), "threshold": threshold, "pixel_tolerance": PIXEL_TOLERANCE,
           "ok": ok, "screens": results}
    write_json(ws / "verification" / "visual.json", out)
    return out
