# Measuring Spec2Ship on real tickets

The goal is real numbers: the same kind of ticket done by hand and with Spec2Ship, measured the same way.
Record one row per ticket per mode in [`evaluation-template.csv`](evaluation-template.csv).

## Choosing tickets

- **How many:** 2–3 real tickets. Each needs a BA document (PDF, DOCX or MD) and a Figma frame, and should touch both
  the UI and the API or database.
- **Size:** each should take roughly 0.5 to 2 days by hand. Smaller tickets do not show the analysis cost, and
  larger ones take too long to compare.
- **Fair comparison:** pick tickets of similar size, or have two developers of similar level each take the same
  ticket in a different mode. If one developer does both modes on the same ticket, the second attempt benefits from
  the first, so note the order.

## What to measure

| Metric | How | Manual | Spec2Ship |
|---|---|---|---|
| `analysis_hours` | From opening the BA to an agreed task list (requirements, mapping, plan). | Clock time. | From `/spec2ship` to approval; see `history` in `state.json` and the `approved_at` field. |
| `implementation_hours` | From the first code change to all tasks done. | Clock time. | From handoff to the last `cc:完了`; see the timestamps in `state.json` `history`. |
| `review_findings` | Defects found in code review before merge, counted by severity. | Reviewer notes. | `/spec2ship-review` plus the human reviewer. Count only defects confirmed by the human reviewer. |
| `missed_requirements` | Requirements in the BA that were not implemented or were implemented wrongly, found by QA or the BA after delivery. | QA/BA check against the BA. | Same check. The RTM shows which requirements Spec2Ship planned. |
| `requirements_total` | The number of requirements the BA confirms for the ticket. | BA. | BA. Compare with the `requirements_in_scope` RTM metric. |
| `open_questions_raised` | Ambiguities raised to the BA before implementation. | Count. | `ambiguities` in `requirements.json`. |
| `rework_hours` | Time spent fixing review and QA findings. | Clock time. | Clock time. |
| `tests_added` | New automated tests. | Count. | Count; also see the evidence in `verification.json`. |

Write down the model and the Claude Code version for every Spec2Ship row. Results depend on the model.

## Collecting Spec2Ship numbers

After a run, the run workspace holds:
- `.spec2ship/state.json`: `history` lists every state change with a timestamp, and `approval.approved_at` is the
  approval time.
- `.spec2ship/reports/rtm.md` and `report.md`: requirement counts, which requirements are verified or only
  implemented, and how many acceptance criteria have evidence.
- `.spec2ship/analysis/requirements.json`: the requirements and their `ambiguities` (open questions).

## Reporting

For each ticket, give:
- the two rows side by side (manual, Spec2Ship);
- a short note on what Spec2Ship got wrong, such as wrong citations, missed screens or a plan that needed edits
  before approval;
- what the developer had to do by hand.

Report failures as well as successes. A blocked or abandoned run is a result.
