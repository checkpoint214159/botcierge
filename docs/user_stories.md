# User stories / backlog

Status: **done** = working in the scaffold, **stub** = model + URL exist, view is a placeholder, **todo** = nothing yet.
ML = story directly consumes model output (needed for the ML criterion).

## Storefront (customer)

| ID | Story | Status | ML | Notes |
|---|---|---|---|---|
| S01 | As a customer, I want to create an account with my housing type so that plans are pre-filled for my home. | done | | `accounts.register`. Profile edit page (S01b) todo. |
| S02 | As a customer, I want to browse and filter robots by platform, environment and keyword so that I can see what's available. | done | | `catalog.robot_list`. Add sorting by price/rating. |
| S03 | As a customer, I want to see a robot's specs, compatible skill packs and reviews so that I can trust it in my home. | done | | `catalog.robot_detail` |
| S04 | As a customer, I want to describe my chore in my own words so that I don't need to know robot jargon. | done | M1 | Text -> task category. Low confidence prompts the customer to pick a type. |
| S05 | As a customer, I want to upload a floor plan and describe my space (area, rooms, floor type, stairs, pets, children, fragile items) so that the robot is matched to my home. | done | M2-M5 input | Floor plan stored, passed into conditioning. Parsing the image is out of scope. |
| S06 | As a customer, I want to set my budget, date window, hours per day and quiet hours so that the plan respects my constraints. | done | M5 | Feasibility and budget checks. |
| S07 | As a customer, I want a recommended robot, attachments, skill pack and itemised quote with flagged risks so that I can decide quickly. | done | M2-M5 | `planner.result` |
| S08 | As a customer, I want to swap the robot or attachments and see the quote update so that I stay in control. | todo | | Save as new `Recommendation(source=customer)`. This is the feedback signal for retraining. |
| S09 | As a customer, I want to add my plan to a booking cart and see if a unit is free on my dates so that I can book with confidence. | stub | | Session cart; check `FleetUnit` availability. |
| S10 | As a customer, I want to check out with a promo code and pay so that my booking is confirmed. | stub | | Mock payment. Creates Order, OrderItems, Payment, first status event; reserves a unit. |
| S11 | As a customer, I want to track my booking from confirmed to collected so that I know when the robot arrives and finishes. | stub | | Timeline from `OrderStatusEvent`. |
| S12 | As a customer, I want to view my past orders and rebook so that repeat chores are one click. | stub | | |
| S13 | As a customer, I want to rate and review a completed job so that others can choose well. | stub | | One review per completed order. |
| S14 | As a customer, I want to raise a support ticket on an order and see replies so that problems get fixed. | stub | | Auto-urgent if robot is on site. |
| S15 | As a customer, I want to see my saved plans so that I can come back and book later. | done | | `planner.my_plans` |

## Admin panel (staff)

Custom views under `/staff/`. Django admin is not allowed by the brief.

| ID | Story | Status | ML | Notes |
|---|---|---|---|---|
| A01 | As staff, I want a separate login-protected panel so that customers can't see internal data. | done (guard) | | `staff_required` decorator, `is_staff` users. |
| A02 | As an ops manager, I want a dashboard of bookings, revenue, fleet utilisation and recommendation acceptance rate so that I can run the business. | stub | ML monitoring | Acceptance = ML recs that reached checkout unmodified. |
| A03 | As staff, I want to add, edit and deactivate robot models so that the catalogue stays current. | stub | | |
| A04 | As staff, I want to manage fleet units (status, depot, service date) so that inventory is accurate. | stub | | |
| A05 | As staff, I want to manage add-ons and skill packs, including compatibility and default conditioning, so that recommendations only use valid combos. | todo | | |
| A06 | As staff, I want to view and deactivate customer accounts and see their history so that I can support them. | todo | | |
| A07 | As staff, I want to assign a fleet unit to an order and advance its status so that the customer's tracking page updates. | stub | | Writes `OrderStatusEvent`. |
| A08 | As staff, I want to inspect each task request's ML output and full policy conditioning, and override it before dispatch, so that bad recommendations are caught. | stub | M1-M5 | Show `policy_conditioning` JSON; override saves `Recommendation(source=staff)`. |
| A09 | As support staff, I want a ticket queue with replies and status so that issues are resolved. | stub | | |
| A10 | As staff, I want to hide inappropriate reviews so that the storefront stays clean. | todo | | |
| A11 | As staff, I want to manage promo codes so that I can run campaigns. | todo | | |
| A12 | As staff, I want to export overridden recommendations as labelled data so that the models can be retrained. | todo | ML | Stretch. CSV export. |

## Remarks
- Report needs a wireframe or screenshot per story. Screenshot each page once it's built.
- The ML criterion grades "complexity of the associated user stories": S04-S08 + A02/A08/A12 form the ML loop (predict, let human correct, measure, retrain).
