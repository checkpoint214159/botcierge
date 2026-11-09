# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Botcierge: IS2108 (NUS) pair project, a Django web app for renting home robots as a service. A customer describes a chore, and ML models plus business rules pick a robot, add-ons, a skill pack and a quote. Coursework constraints from the brief:
- **Django admin is banned.** `django.contrib.admin` is removed from `INSTALLED_APPS` on purpose. All staff tooling goes in the custom `staffpanel` app under `/staff/`, gated by `staff_required` (`is_staff`).
- `source/` is the submission root and is zipped as-is. Keep everything the app needs to run inside it.
- Every GenAI use must be logged in `docs/genai_log.md`. Commits co-authored by Claude carry a `Co-Authored-By` trailer.
- Backlog and story status (S01–S15 customer, A01–A12 staff) live in `docs/user_stories.md`. Branch per story (`feat/S09-cart`), PR into `main`.
- **The brief bans AI generating the whole app, and there is a code review.** Claude wrote the docs, data model, seed data, ML pipeline and the planner slice. The remaining stories (S08–S14 cart/checkout/tracking/reviews/tickets, A02–A12 staff panel) are for the two students to build *with* AI assistance. Don't implement a whole backlog item unprompted. Work at the scope the user asks for, explain the code so they can defend it in review, and remind them to log the use.
- **The business must read as B2C:** households and owner-run small premises renting robots per job or week. Avoid "client" and "enterprise" framing in copy and docs.
- Grading weights are roughly 50% e-commerce breadth/depth, 20% ML (sklearn classification/regression in joblib driving a business decision) and 30% UI.
- Use function-based views (the course style, Lecture 13), not CBVs.
- Customers see a friendly skill-pack summary. The full `policy_conditioning` JSON is staff-only.
- Known open items: M1 and M4 score ~100% because the synthetic data is too clean (a planned fix is LLM-paraphrased descriptions in `ml/generate_data.py`). Market sizing and competitor names in `docs/business_model.md` are TODO; don't invent numbers without a source.

## Commands

Run Django commands from `source/src/botcierge/` (that is where `manage.py` is). The platform is Windows/PowerShell. The venv lives at the repo root.

```
pip install -r source\requirements.txt      # pinned; the joblib models need scikit-learn 1.9.1
python manage.py migrate
python manage.py seed_demo                  # catalogue, fleet, promo code, demo users (--reset to wipe catalogue first)
python manage.py runserver
python manage.py test                       # all tests
python manage.py test planner               # one app
python manage.py test planner.tests.DecomposerTests.test_tight_budget_is_flagged   # one test
```

Demo logins: `demo / demopass123` (customer) and `staff / staffpass123` (staff panel at `/staff/`).

Retrain the ML models (from `ml/`): `python generate_data.py` then `python train_models.py`. Generated CSVs in `ml/data/` are gitignored. The output joblib files are written straight into `source/src/botcierge/planner/mlmodels/` and are committed.

Build the submission zip: `python scripts/package_submission.py PP01`. It needs `docs/PP01.docx` to exist and writes `dist/PP01.zip`, leaving out venv, `.git`, `db.sqlite3` and media.

There is no linter or formatter configured.

## Architecture

**Core flow (planner app):** `TaskRequest` (customer input) → `planner/decomposer.py::decompose()` → `TaskSpec` (1:1, the ML analysis) + `Recommendation` (robot, add-ons, skill pack, `policy_conditioning` JSON, quote). `decompose()` is one atomic transaction that chains five models with rules in between:
1. **M1** (TF-IDF + LogReg): description → task category. Skipped when the customer sets `category_hint`. Below `CATEGORY_CONFIDENCE_FLOOR` the UI tells the customer it is unsure.
2. **M5** (GBR): robot-hours. Not used for `TIME_BASED_CATEGORIES` (elder care, patrol, serving), where effort is the booked window.
3. **M2** (RF): platform. `choose_robot()` then picks the cheapest active `RobotModel` of that platform that meets the hard constraints, and falls back to any platform.
4. **M3** (multi-output RF): add-ons, filtered by `AddOn.fits(robot.platform)`.
5. **M4** (RF): skill pack code.
6. Rules build the quote (`DELIVERY_FEE` + daily rates × days + skill pack flat fee), the edge-case warnings and the conditioning dict.

Each joblib file is a bundle dict `{"model", "features", "labels", "metrics"}`, loaded once per process through `lru_cache` from `settings.ML_MODEL_DIR`. M2–M5 share one structured feature row. Column order comes from the bundle's `features`.

**Label vocabulary is duplicated and must stay in sync:** `ml/taxonomy.py` (training) and `source/src/botcierge/catalog/taxonomy.py` (Django `choices`). The models predict these exact strings, so a new category, platform, add-on or skill pack means editing both files, retraining, and usually updating `seed_demo` and `SUBTASK_TEMPLATES` in the decomposer.

**Apps:** `accounts` (registration, `CustomerProfile`), `catalog` (`RobotModel`, `AddOn`, `SkillPack`, `FleetUnit`, plus the `seed_demo` command), `planner` (above), `orders` (`Order`/`OrderItem`/`OrderStatusEvent`/`Payment`/`PromoCode`), `support` (`Review`, `SupportTicket`/`TicketMessage`), `staffpanel` (no models). The models in orders, support and staffpanel are complete, but many views are stubs that render `coming_soon.html` with a story ID. Stubs are marked `TODO(<story id>)`.

**Templates/forms:** project-level `templates/` (per-app subfolders, `base.html`) and local Bootstrap 5 in `static/vendor/` (no CDN). Forms mix in `config/form_mixins.py::BootstrapFormMixin` and render fields through `templates/partials/field.html`.

**Tests** that touch the decomposer call `call_command("seed_demo")` in `setUpTestData`, because recommendations depend on catalogue rows.

Design docs in `docs/`: `data_model.md`, `ml_models.md`, `business_model.md`.
