# Generative AI usage log

The brief requires declaring every use of GenAI with evidence (prompts, history, screenshots) and a reflection. Add a row every time either of us uses a tool. Keep screenshots in `docs/genai_evidence/`.

| Date | Who | Tool | Task | What the AI produced | What we changed / verified |
|---|---|---|---|---|---|
| 2026-11-08 | Ben | Claude (Opus 5.5, claude.ai) | Ideation + initial scaffold | Business model draft, user story backlog, data model, synthetic data generator + training script for 5 models, Django project skeleton, planner vertical slice (intake form, decomposition service, result page), seed data, tests | TODO: list what we reviewed, rewrote and why. Commits co-authored by Claude are marked with a `Co-Authored-By` trailer. |
| 2026-11-08 | Ben | Claude Code (Opus 5.5) | CLAUDE.md + bug fix | Repo guide for the AI assistant; fixed SQLite "database is locked" on double-submitted plans (`transaction_mode: IMMEDIATE`) | TODO |
| 2026-11-11 | (fill in) | GitHub Copilot (Claude Sonnet 5.5) | Backlog review + small stories | Reworked `docs/user_stories.md` (merged epics, new S16/S17/S18/A13/A14, demoted A06/A10/A11, A01 -> NFR); implemented S01b profile page, S02 sorting, S08 swap robot/add-ons (`save_customer_edit`, `build_quote`), S17 "Why this setup" card, with tests | TODO: list what we reviewed and can explain in code review |
| 2026-11-12 | (fill in) | GitHub Copilot (Claude Sonnet 5.5) | S09 cart + S10 checkout | `orders/services.py` (availability, promo, atomic order creation), cart/checkout/confirmation views, forms, templates, tests | TODO: list what we reviewed and can explain in code review |
| 2026-11-12 | (fill in) | GitHub Copilot (Claude Sonnet 5.5) | S11 tracking + A07 staff orders | `advance_order`/`assignable_units` in `orders/services.py`, customer order page, staff order list/detail, tests | TODO: list what we reviewed and can explain in code review |
| 2026-11-13 | Ben | Claude Code (Opus 5.5) | Real robot catalogue + photos | Replaced fictional robots with 11 real products, found freely licensed photos on Wikimedia Commons, added `stock_image`/`image_credit` fields, photo cards on catalogue/detail/result pages | TODO: verify specs against manufacturer sheets |
| 2026-11-14 | Ben | Claude Code (Opus 5.5) | Merge Manav's branch | Merged origin/main (S08 swap, S09-S11, A07) into feat/real-robot-catalogue; resolved the genai_log conflict; ran all 30 tests | Ben chose to keep Manav's versions of overlapping stories and our dark mode/photo work |

## Reflection notes (fill in as we go)
- Advantages:
- Disadvantages / errors caught:
- Where we chose not to use AI:
