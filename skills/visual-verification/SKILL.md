---
name: visual-verification
description: Auto mode. Take a browser screenshot of every screen in design/screens.json and compare it with the Figma reference using `spec2ship.py visual-compare`. Use in the verification step of /spec2ship-auto.
---

# Visual verification (auto mode)

Goal: the app at each `route` looks like its Figma frame. The comparison is a deterministic pixel check
(`visual-compare`), so its PASS counts as evidence; your own visual impression does not.

1. **Start the app** with the project's dev or preview command from `analysis/repository-analysis.json`, in the
   background (`run_in_background`), and wait until the URL responds. Never use production URLs.
2. **Screenshot every screen** with Playwright, viewport width = the frame `width`, height = frame `height`, device
   scale factor 1, full page, animations disabled, after network idle. Save to
   `.spec2ship/verification/screens/<id>.png`. Prefer the screenshot script the plan added (for example
   `e2e/screenshots.spec.ts` run with `npx playwright test e2e/screenshots.spec.ts`); otherwise run a short Playwright
   script. Record the command with `S2S record-check --name screenshots --layer visual ...`.
3. **Compare:** `S2S visual-compare`. It scales each screenshot to the frame width, counts pixels that differ by
   more than the tolerance, and writes `verification/visual.json`, one `visual:<id>` check per screen, and a diff image
   `verification/screens/<id>.diff.png` (red = different).
4. **Read the result:**
   - `MATCH` → visual part done.
   - `NO MATCH` → open the reference, the screenshot and the diff image for each failing screen and describe the
     concrete differences (missing element, spacing, size, color, copy, font). These become the fix-round tasks.
   - `NOT_RUN` (missing screenshot or Pillow) → fix the cause; never treat it as a pass.
5. Stop the dev server when done.

Never lower `--threshold`, crop screenshots, or edit the reference PNGs to reach a match.
