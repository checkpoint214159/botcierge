# Generative AI usage log

The brief requires declaring every use of GenAI with evidence (prompts, history, screenshots) and a reflection. Add a row every time either of us uses a tool. Keep screenshots in `docs/genai_evidence/`.

| Date | Who | Tool | Task | What the AI produced | What we changed / verified |
|---|---|---|---|---|---|
| 2026-11-08 | Ben | Claude (Opus 5.5, claude.ai) | Ideation + initial scaffold | Business model draft, user story backlog, data model, synthetic data generator + training script for 5 models, Django project skeleton, planner vertical slice (intake form, decomposition service, result page), seed data, tests | TODO: list what we reviewed, rewrote and why. Commits co-authored by Claude are marked with a `Co-Authored-By` trailer. |
| 2026-11-08 | Ben | Claude Code (Opus 5.5) | CLAUDE.md + bug fix | Repo guide for the AI assistant; fixed SQLite "database is locked" on double-submitted plans (`transaction_mode: IMMEDIATE`) | TODO |
| 2026-11-13 | Ben | Claude Code (Opus 5.5) | Real robot catalogue + photos | Replaced fictional robots with 11 real products, found freely licensed photos on Wikimedia Commons, added `stock_image`/`image_credit` fields, photo cards on catalogue/detail/result pages | TODO: verify specs against manufacturer sheets |

## Reflection notes (fill in as we go)
- Advantages:
- Disadvantages / errors caught:
- Where we chose not to use AI:
