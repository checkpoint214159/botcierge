# User stories / backlog

Status: **done** = working, **stub** = model + URL exist, view is a placeholder, **todo** = nothing yet, **stretch** = only if time allows.
ML = story directly consumes model output (needed for the ML criterion).
Owner = who builds it (fill in). Shot = wireframe/screenshot for the report is done.

Story IDs are stable because `TODO(<id>)` markers in the code refer to them. New stories get new IDs rather than renumbering.

## Storefront (customer)

### Epic: Plan a job (S04 + S05 + S06 -> S07)
One flow, three input stories, then the output stories. Together they form the ML pipeline (M1-M5).

| ID | Story | Status | ML | Owner | Shot | Notes |
|---|---|---|---|---|---|---|
| S04 | As a customer, I want to describe my chore in my own words so that I don't need to know robot jargon. | done | M1 | | | Text -> task category. |
| S05 | As a customer, I want to upload a floor plan and describe my space (area, rooms, floor type, stairs, pets, children, fragile items) so that the robot is matched to my home. | done | M2-M5 input | | | Floor plan stored, passed into conditioning. Parsing the image is out of scope. |
| S06 | As a customer, I want to set my budget, date window, hours per day and quiet hours so that the plan respects my constraints. | done | M5 | | | Feasibility and budget checks. |
| S07 | As a customer, I want a recommended robot, attachments, skill pack and itemised quote with flagged risks so that I can decide quickly. | done | M2-M5 | | | `planner.result` |
| S16 | As a customer, I want to be told when the system is unsure what my chore is, and pick the task type myself, so that I don't get a wrong recommendation. | done | M1 | | | Below `CATEGORY_CONFIDENCE_FLOOR` the result page warns and the form has a `category_hint` selector. |
| S17 | As a customer, I want to see why this robot, add-ons and skill pack were chosen so that I can trust the recommendation. | done | M2-M5 | | | "Why this setup" card (`planner.views.explain`). Never shows the staff-only `policy_conditioning` JSON. |

### Browse and account

| ID | Story | Status | ML | Owner | Shot | Notes |
|---|---|---|---|---|---|---|
| S01 | As a customer, I want to create an account with my housing type so that plans are pre-filled for my home. | done | | | | `accounts.register` |
| S01b | As a customer, I want to edit my phone, address and housing type so that my details stay current. | done | | | | `accounts.profile`, linked from the navbar greeting. |
| S02 | As a customer, I want to browse, filter robots by platform, environment and keyword, and sort them by price and rating, so that I can see what's available. | done | | | | `catalog.robot_list` (`sort=price_asc / price_desc / rating`). |
| S03 | As a customer, I want to see a robot's specs, compatible skill packs and reviews so that I can trust it in my home. | done | | | | `catalog.robot_detail` |
| S15 | As a customer, I want to see my saved plans so that I can come back and book later. | done | | | | `planner.my_plans` |

### Epic: Book and pay (S08 -> S09 -> S10)

| ID | Story | Status | ML | Owner | Shot | Notes |
|---|---|---|---|---|---|---|
| S08 | As a customer, I want to swap the robot or attachments and see the quote update so that I stay in control. | done | | | | `planner.swap`. Saves a new `Recommendation(source=customer)` via `save_customer_edit`; the ML row is kept. This is the feedback signal for A08/A12 and retraining. Swaps respect the same hard constraints and add-on compatibility. |
| S09 | As a customer, I want to add my plan to a booking cart and see if a unit is free on my dates so that I can book with confidence. | done | | | | Session cart (`orders.cart`) holds one `Recommendation` id. Availability is date-based (`orders.services.free_units`): units not in maintenance/retired and with no overlapping non-cancelled booking. |
| S10 | As a customer, I want to check out with a promo code and pay so that my booking is confirmed. | done | | | | Done: `orders.checkout` + `services.create_order` (atomic) create Order, items, mock paid Payment, first `OrderStatusEvent`, assign and reserve a unit, set `Recommendation.is_selected` (feeds A13). Promo codes validated and applied as a percentage discount. |

### Epic: After booking (S11 <-> A07)

| ID | Story | Status | ML | Owner | Shot | Notes |
|---|---|---|---|---|---|---|
| S11 | As a customer, I want to track my booking from confirmed to collected so that I know when the robot arrives and finishes. | stub | | | | Timeline from `OrderStatusEvent`. Fed by staff story A07. |
| S12 | As a customer, I want to view my past orders and rebook so that repeat chores are one click. | stub | | | | |
| S18 | As a customer, I want to cancel or reschedule a booking that hasn't started so that I can change my plans. | todo | | | | Release the reserved `FleetUnit`; write an `OrderStatusEvent`. Needs a cancellation rule (e.g. until the day before). |
| S13 | As a customer, I want to rate and review a completed job so that others can choose well. | stub | | | | One review per completed order. |
| S14 | As a customer, I want to raise a support ticket on an order, which is marked urgent automatically if the robot is already on site, and see replies, so that problems get fixed quickly. | stub | | | | Priority URGENT if order is ON_SITE or RUNNING. |

## Staff panel

Custom views under `/staff/`, gated by `staff_required` (`is_staff`). Django admin is not allowed by the brief. Access control (the old A01) is a non-functional requirement, not a story: every `/staff/` view must use the guard.

### Epic: Operate the business

| ID | Story | Status | ML | Owner | Shot | Notes |
|---|---|---|---|---|---|---|
| A02 | As an ops manager, I want a dashboard of bookings, revenue and fleet utilisation so that I can run the business. | stub | | | | |
| A13 | As an ops manager, I want to see the recommendation acceptance rate so that I know whether the models are helping. | todo | ML monitoring | | | Acceptance = ML recs that reached checkout unmodified (`is_selected` and `source=ml`). Shown on the A02 dashboard. |
| A07 | As staff, I want to assign a fleet unit to an order and advance its status so that the customer's tracking page updates. | stub | | | | Writes `OrderStatusEvent`. Pairs with S11. |
| A09 | As support staff, I want a ticket queue with replies and status so that issues are resolved. | stub | | | | Urgent tickets first. |

### Epic: Manage the catalogue and fleet (A03 + A04 + A05)
Same CRUD pattern across all three; build one and reuse it.

| ID | Story | Status | ML | Owner | Shot | Notes |
|---|---|---|---|---|---|---|
| A03 | As staff, I want to add, edit and deactivate robot models so that the catalogue stays current. | stub | | | | |
| A04 | As staff, I want to manage fleet units (status, depot, service date) so that inventory is accurate. | stub | | | | |
| A05 | As staff, I want to manage add-ons and skill packs, including compatibility and default conditioning, so that recommendations only use valid combos. | todo | | | | New labels also need `ml/taxonomy.py` + `catalog/taxonomy.py` + retraining. |

### Epic: Human-in-the-loop ML (A08 -> A12)

| ID | Story | Status | ML | Owner | Shot | Notes |
|---|---|---|---|---|---|---|
| A08 | As staff, I want to inspect each task request's ML output and full policy conditioning, and override it before dispatch, so that bad recommendations are caught. | stub | M1-M5 | | | Show `policy_conditioning` JSON; override saves `Recommendation(source=staff)`. |
| A14 | As staff, I want low-confidence and risk-flagged recommendations listed first so that I review the riskiest ones before dispatch. | todo | M1-M5 | | | Sort/filter the A08 list using `category_confidence` and `edge_cases`. |
| A12 | As staff, I want to export overridden recommendations as labelled data so that the models can be retrained. | stretch | ML | | | CSV export of `source=customer/staff` rows. Closes the retraining loop. |

### Low priority (stretch)

| ID | Story | Status | ML | Owner | Shot | Notes |
|---|---|---|---|---|---|---|
| A11 | As staff, I want to manage promo codes so that I can run campaigns. | stretch | | | | Worth doing only if S10 applies promos (model exists). |
| A06 | As staff, I want to view and deactivate customer accounts and see their history so that I can support them. | stretch | | | | |
| A10 | As staff, I want to hide inappropriate reviews so that the storefront stays clean. | stretch | | | | |

## Remarks
- Report needs a wireframe or screenshot per story. Tick the Shot column once built.
- The ML criterion grades "complexity of the associated user stories": S04-S08 + S16/S17 + A08/A13/A14/A12 form the ML loop (predict, explain, let a human correct, measure, retrain).
- Removed as a story: old A01 (staff guard), now a non-functional requirement above.
- Fill in Owner for each story. The brief bans AI generating the whole app, so each of us must be able to explain our own stories in the code review.
