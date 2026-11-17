---
name: requirement-mapping
description: Map Spec2Ship requirements to captured Figma nodes with confidence and evidence, and surface BA/Figma conflicts. Use after requirements.json and figma-context.json exist.
---

# Requirement ↔ Figma mapping

Output: `.spec2ship/mappings/figma-mapping.json` (schema `schemas/figma-mapping.schema.json`).

1. For each requirement with UI impact (`type: ui` or `frontend` in `layers`), find the screens/components/states in
   `figma-context.json` that realize it. `relation`: screen | component | state | flow | content.
2. `evidence` must point at something observable in the captured node: matching texts, component names, states,
   annotations. `confidence`: high (explicit text/structure match), medium (name/layout match), low (plausible guess).
   Confidence never replaces developer review.
3. Only cite node ids present in `figma-context.json`. The validator rejects others.
4. Requirements without a design go to `unmapped_requirements` with a reason: `no_ui` (backend-only),
   `design_missing`, `figma_unavailable`, `unclear`.
   When `figma-context.json` has `status: "unavailable"` (no Figma URL, or the bridge could not be read), write
   `mappings: []` and list every UI requirement as `figma_unavailable`; backend-only ones stay `no_ui`.
5. Design elements with no requirement go to `unmapped_nodes` (possible missing requirement or out-of-scope design).
6. **Conflicts**: when the design contradicts the BA (different fields, rules, flows, copy that changes behavior),
   add a `conflicts[]` entry and an ambiguity (`kind: conflict`, `blocking: true` if behavior differs) on the
   requirement. The BA defines business behavior; Figma defines visual intent; the developer decides conflicts.
7. Run `spec2ship.py validate --stage plan`.
