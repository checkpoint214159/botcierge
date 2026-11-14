# Botcierge

IS2108 AY26/27 S1 pair project. Robots-as-a-service for homes: describe a chore, get the right robot, attachments, skill pack and quote.

## Layout
```
docs/                  business model, user stories, data model, ML notes, GenAI log (report goes here as PPXX.docx)
source/                what gets zipped for submission
  ml/                  synthetic data generator + model training (writes joblib into the app)
  readme.txt           required by the brief
  requirements.txt
  src/botcierge/       Django project (manage.py)
    config/            settings, root urls
    accounts/          sign-up, customer profile
    catalog/           robots, fleet units, add-ons, skill packs, seed_demo command
    planner/           task intake -> decomposition (ML) -> recommendation
    orders/            cart, checkout, tracking (stubs)
    support/           reviews, tickets (stubs)
    staffpanel/        custom staff panel (stubs; Django admin is banned)
scripts/package_submission.py   builds dist/PPXX.zip without .git / venv
```

## Run locally
Windows PowerShell, from the repo root:
```
python -m venv venv
venv\Scripts\activate
pip install -r source\requirements.txt
cd source\src\botcierge
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```
macOS/Linux: `source venv/bin/activate` instead.

Logins: `demo / demopass123` (customer), `staff / staffpass123` (staff panel at `/staff/`).

Tests: `python manage.py test`

## Retrain the models
```
cd ml
python generate_data.py
python train_models.py
```

## Working agreement
- Branch per story (`feat/S09-cart`), PR into `main`, the other person reviews.
- Every GenAI use goes in `docs/genai_log.md` with evidence. The code review checks we understand everything.
- Backlog and status live in `docs/user_stories.md`.
