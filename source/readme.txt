IS2108 Pair Project - Botcierge (robots as a service for homes)

Group number: PPXX   <- TODO

Members (* = group leader)
  * TODO full name, student number, email, contact number
    TODO full name, student number, email, contact number

Demo video (YouTube): TODO

How to run (Windows, PowerShell)
  cd src\botcierge
  python -m venv venv
  venv\Scripts\activate
  pip install -r ..\..\requirements.txt
  python manage.py migrate
  python manage.py seed_demo
  python manage.py runserver

Open http://127.0.0.1:8000/
  Customer login: demo / demopass123
  Staff login:    staff / staffpass123   (staff panel at /staff/)

Machine learning models are pre-trained joblib files in src\botcierge\planner\mlmodels\.
They were trained with scikit-learn 1.9.1; use the pinned versions in requirements.txt.
