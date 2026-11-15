# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Botcierge: IS2108 (NUS) pair project, a Django web app for renting home robots as a service. A customer describes a chore, and ML models plus business rules pick a robot, add-ons, a skill pack and a quote. Coursework constraints from the brief:
- **Django admin is banned.** `django.contrib.admin` is removed from `INSTALLED_APPS` on purpose. All staff tooling goes in the custom `staffpanel` app under `/staff/`, gated by `staff_required` (`is_staff`).
- `source/` is the submission root and is zipped as-is. Keep everything the app needs to run inside it.
- Every GenAI use must be logged in `docs/genai_log.md`. Commits co-authored by Claude carry a `Co-Authored-By` trailer.
- Backlog and story status (S01–S15 customer, A01–A12 staff) live in `docs/user_stories.md`. Branch per story (`feat/S09-cart`), PR into `main`.
- **The brief bans AI generating the whole app, and there is a code review.** Claude wrote the docs, data model, seed data, ML pipeline and the planner slice. The remaining stories (S08–S14 cart/checkout/tracking/reviews/tickets, A02–A12 staff panel) are for the two students to build *with* AI assistance. As of 2026-11-14, Manav has first versions of S08 swap, S09 cart, S10 checkout, S11 tracking and A07 staff orders (`orders/services.py`, `planner.views.swap`, made with Copilot); Ben is reworking S08–S11 into a single booking page. `docs/user_stories.md` was restructured into epics in that merge, so check story IDs there. Don't implement a whole backlog item unprompted. Work at the scope the user asks for, explain the code so they can defend it in review, and remind them to log the use.
- **Working mode (agreed 2026-11-13, revised 2026-11-14).** Default: the students write the web app code; Claude explains, gives short snippets and reviews. Exception (2026-11-14): for Ben's S08–S12 booking rework, Claude builds templates and wires views in small, reviewable steps at Ben's direction. Ben makes the design decisions, tests each step in the browser and reports what breaks. Keep each step small enough for him to read and defend in review, and log each round in `docs/genai_log.md`. ML (`source/ml/`, synthetic data, training), debugging, docs and CLAUDE.md edits are unrestricted.
- **The business must read as B2C:** households and owner-run small premises renting robots per job or week. Avoid "client" and "enterprise" framing in copy and docs.
- Grading weights are roughly 50% e-commerce breadth/depth, 20% ML (sklearn classification/regression in joblib driving a business decision) and 30% UI.
- Use function-based views (the course style, Lecture 13), not CBVs.
- Customers see a friendly skill-pack summary. The full `policy_conditioning` JSON is staff-only.
- Known open items: M4 still scores ~99% because its labels come from simple rules (M1 now trains on hand-written requests in `source/ml/seed_requests/` and scores 0.954 on held-out ones, likely optimistic). Market sizing and competitor names in `docs/business_model.md` are TODO; don't invent numbers without a source.

## After pulling (setup for a teammate or their agent)

Verified on 2026-11-14 from a fresh clone: migrate, both seed commands and all 89 tests pass, and retraining reproduces the committed models exactly. From `source/src/botcierge/`:

```
pip install -r ..\..\requirements.txt   # same pinned versions (scikit-learn 1.9.1 for the joblib models)
python manage.py migrate                # new migrations fill in robot/skill pack task types and order review fields
python manage.py seed_demo              # catalogue, fleet, demo/staff users (re-run is safe)
python manage.py seed_review_orders     # 12 test orders for the A08 review queue
python manage.py seed_support_tickets   # 7 test tickets on those orders for the A09 queue (one is a hidden customer draft)
python manage.py test                   # expect 102 tests OK
```

- **Fresh database:** delete `db.sqlite3` first if you want exactly the demo state. It's gitignored, so nobody else's data comes with the pull.
- **Keeping an existing database:** the migrations convert it in place. `seed_demo` resets seeded catalogue fields (names, prices, robot and skill pack task types) to the seed values, so any staff-panel edits to seeded rows are overwritten.
- **Old orders:** after the migration they start as "to review", and A07 dispatch now refuses until an order is approved at `/staff/review/`.
- **`seed_review_orders`:** books test orders for `tester1`-`tester4` (password `testpass123`) with ship days relative to today. Use `--reset` to rebook a fresh set; it only touches those four accounts. Running it again without `--reset` adds more orders, and some get skipped once units run out.
- **No retraining needed:** the committed joblib files are current. Only retrain after changing `source/ml/` (`python generate_data.py` then `python train_models.py` from `source/ml/`). The output is deterministic (seed 2108), so the files come out identical.
- **Where things live now** (since Manav's S08-S11/A07 versions):
  - Booking: `orders/views.py` booking/cart/checkout and `orders/services.py`. The old `planner.swap` page is gone.
  - Staff catalogue: `/staff/robots/`, `/fleet/`, `/addons/`, `/skill-packs/`.
  - Recommendation models page: `/staff/recommendation-models/`.
  - Review before dispatch: `/staff/review/`, logic in `orders/review.py`.
  - Support queue: `/staff/tickets/`, logic in `support/queue.py`. Staff reply drafts live on `SupportTicket.reply_draft` (never shown to the customer).
  - Dashboard: `/staff/`, one function per panel in `staffpanel/dashboard.py`.
  - Both staff queues share `staffpanel/queue.py` and the `queue_list.html` / `_queue_nav.html` templates.
  - ML monitoring (A13 acceptance rate, A12 CSV of human changes): `planner/monitoring.py`, shown on `/staff/recommendation-models/`.
  - Promo codes `/staff/promos/`, customer accounts `/staff/customers/`, review hiding `/staff/customer-reviews/`.
  - Story status is in `docs/user_stories.md`.

## Commands

Run Django commands from `source/src/botcierge/` (that is where `manage.py` is). The platform is Windows/PowerShell. The venv lives at the repo root.

```
pip install -r source\requirements.txt      # pinned; the joblib models need scikit-learn 1.9.1
python manage.py migrate
python manage.py seed_demo                  # catalogue, fleet, promo code, demo users (--reset to wipe catalogue first)
python manage.py seed_review_orders         # 12 test orders (tester1-4 / testpass123) across task types and ship days for the A08 review queue (--reset to rebook)
python manage.py seed_support_tickets       # test tickets on those orders for the A09 support queue (--reset to replace)
python manage.py runserver
python manage.py test                       # all tests
python manage.py test planner               # one app
python manage.py test planner.tests.DecomposerTests.test_tight_budget_is_flagged   # one test
```

Demo logins: `demo / demopass123` (customer) and `staff / staffpass123` (staff panel at `/staff/`).

Retrain the ML models (from `source/ml/`, which is inside the submission zip on purpose so markers see the training code): `python generate_data.py` then `python train_models.py`. Generated CSVs in `source/ml/data/` are gitignored. The output joblib files are written straight into `source/src/botcierge/planner/mlmodels/` and are committed.

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

**Label vocabulary is duplicated and must stay in sync:** `source/ml/taxonomy.py` (training) and `source/src/botcierge/catalog/taxonomy.py` (Django `choices`). The models predict these exact strings. Task categories and platforms are fixed in code: a new one means editing both files, retraining, and updating `seed_demo`, `TASK_PLATFORMS` and `SUBTASK_TEMPLATES`. Which robots can be booked for a task type is per robot (`RobotModel.task_categories`, staff-editable in A03, seeded from `TASK_PLATFORMS` by platform); `eligible_robots()` uses it, while M2 still predicts a platform as trained. Add-on and skill pack codes are rows staff can create (A05, `/staff/addons/`, `/staff/skill-packs/`); the ML only recommends a code after it is added to `source/ml/taxonomy.py` and retrained, and `/staff/recommendation-models/` shows which codes each model knows. Skill packs are offered on the booking page by `SkillPack.task_categories` (seeded from `TASK_SKILL_PACKS`).

**Apps:** `accounts` (registration, `CustomerProfile`), `catalog` (`RobotModel`, `AddOn`, `SkillPack`, `FleetUnit`, plus the `seed_demo` command), `planner` (above), `orders` (`Order`/`OrderItem`/`OrderStatusEvent`/`Payment`/`PromoCode`), `support` (`Review`, `SupportTicket`/`TicketMessage`), `staffpanel` (no models). The models in orders, support and staffpanel are complete, but many views are stubs that render `coming_soon.html` with a story ID. Stubs are marked `TODO(<story id>)`.

**Templates/forms:** project-level `templates/` (per-app subfolders, `base.html`) and local Bootstrap 5 in `static/vendor/` (no CDN). Forms mix in `config/form_mixins.py::BootstrapFormMixin` and render fields through `templates/partials/field.html`.

**Tests** that touch the decomposer call `call_command("seed_demo")` in `setUpTestData`, because recommendations depend on catalogue rows.

Design docs in `docs/`: `data_model.md`, `ml_models.md`, `business_model.md`.
