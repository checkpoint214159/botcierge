IS2108 Pair Project - Botcierge (home robots rented per job)

Group number: PP38

Group members (* = group leader) 
    Benjamin Goh En Yang* | A0320447L | contact: 86137633 | email: benjamin_en_yang.goh@u.nus.edu
    Manav Kontu           | A0321347L | contact: 91789178 | email: manavk@u.nus.edu

Demo video (YouTube): https://youtu.be/6XT8CO5QGNw


HOW TO RUN (Windows, PowerShell; tested with Python 3.14)

  cd src\botcierge
  python -m venv venv
  venv\Scripts\activate
  pip install -r ..\..\requirements.txt
  python manage.py migrate
  python manage.py seed_demo
  python manage.py runserver

Then open http://127.0.0.1:8000/

  Customer login:  demo  / demopass123
  Staff login:     staff / staffpass123   (staff panel at /staff/)

seed_demo must run before anything else: it creates the robot catalogue, fleet units,
add-ons, skill packs, a promo code and the two logins above. It is safe to run again.


OPTIONAL: TEST DATA FOR THE STAFF QUEUES

  python manage.py seed_review_orders       # 12 paid orders to work through at /staff/review/
  python manage.py seed_support_tickets     # 7 support tickets on those orders at /staff/tickets/

Run these after seed_demo. They book orders for test customers tester1 to tester4
(password testpass123) with ship days counted from today. Add --reset to either command
to replace the test data with a fresh set.


SPECIAL NOTES

- The Django admin is not used. All staff tools are under /staff/ (log in as staff).
- Payments are simulated: checkout records a mock card payment, no real gateway is called.
- The machine learning models are pre-trained joblib files in src\botcierge\planner\mlmodels\.
  They were trained with scikit-learn 1.9.1, so install the pinned versions in
  requirements.txt; a different scikit-learn version may fail to load them.
- Automated tests: python manage.py test   (from src\botcierge)


ML TRAINING CODE (optional, not needed to run the app)

The training code is in ml\ so it can be inspected. To regenerate the synthetic data and
retrain all five models (output is deterministic and overwrites the committed joblib files):

  cd ml
  python generate_data.py
  python train_models.py
