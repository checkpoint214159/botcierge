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
| S05 | As a customer, I want to upload a floor plan and describe my space (area, rooms, floor type, stairs, pets, children, fragile items) so that the robot is matched to my home. | done | M2-M5 input | | | Floor plan can be added here or later on the booking page, where the customer also marks keep-out zones (S20). Stored and passed into conditioning; parsing the image is out of scope. |
| S06 | As a customer, I want to set my budget, date window, hours per day and quiet hours so that the plan respects my constraints. | done | M5 | | | Feasibility and budget checks. |
| S07 | As a customer, I want a recommended robot, attachments, skill pack and itemised quote with flagged risks so that I can decide quickly. | done | M2-M5 | | | `planner.result` |
| S16 | As a customer, I want to be told when the system is unsure what my chore is, and pick the task type myself, so that I don't get a wrong recommendation. | done | M1 | | | Below `CATEGORY_CONFIDENCE_FLOOR` the result page warns and the form has a `category_hint` selector. |
| S17 | As a customer, I want to see why this robot, add-ons and skill pack were chosen so that I can trust the recommendation. | done | M2-M5 | | | "Why this setup" card (`planner.views.explain`). Never shows the staff-only `policy_conditioning` JSON. |

### Browse and account

| ID | Story | Status | ML | Owner | Shot | Notes |
|---|---|---|---|---|---|---|
| S01 | As a customer, I want to create an account with my housing type so that plans are pre-filled for my home. | done | | | | `accounts.register` |
| S01b | As a customer, I want to edit my phone, housing type and household size so that my details stay current. | done | | | | `accounts.profile`, linked from the navbar greeting. Delivery addresses moved to their own page (S19). |
| S02 | As a customer, I want to browse, filter robots by platform, environment and keyword, and sort them by price and rating, so that I can see what's available. | done | | | | `catalog.robot_list` (`sort=price_asc / price_desc / rating`). |
| S03 | As a customer, I want to see a robot's specs, compatible skill packs and reviews so that I can trust it in my home. | done | | | | `catalog.robot_detail` |
| S15 | As a customer, I want to see my saved plans so that I can come back and book later. | done | | | | `planner.my_plans` |

### Epic: Book and pay (S08 + S09 + S19 + S20 -> S10)
One booking page per plan (`orders.booking`): adjust the setup, pick dates, address and floor plan, with a live price sidebar. Saved plans wait in the cart until checkout.

| ID | Story | Status | ML | Owner | Shot | Notes |
|---|---|---|---|---|---|---|
| S08 | As a customer, I want to adjust the recommended robot, attachments and skill pack on a booking page and see the quote update live so that I stay in control. | done | | Manav, Ben (rework) | | `orders.booking` + `booking_quote` (GET JSON for the live sidebar, writes nothing). Replaced the old `planner.swap` page. Only robots marked for the task type (`eligible_robots`) and skill packs for it (`SkillPack.task_categories`) are offered; incompatible attachments are greyed out. Changing the setup saves a new `Recommendation(source=customer)` via `save_customer_edit` (ML row kept, feeds A13/A12); changing only dates or address re-prices in place (`requote`). |
| S09 | As a customer, I want to add my plan to a booking cart and see if a unit is free on my dates so that I can book with confidence. | done | | Manav, Ben (rework) | | Database cart: every PLANNED plan (`orders.cart`), split into ready and needs-details, with a navbar badge (context processor). Remove/restore moves a plan to DRAFT and back. `orders.services.booking_problems` (no robot, past date, no address, no floor plan, no free unit) is shared by the booking page, cart and checkout so they never disagree. Availability is date-based (`free_units`). Delivery fee by postal zone from the Jurong West depot (`planner/pricing.py`). |
| S10 | As a customer, I want to check out with a promo code and pay so that my booking is confirmed. | done | | Manav, Ben (rework) | | `orders.checkout` re-prices, enforces `booking_problems`, previews a promo with GET `?promo=` and pays with POST. `services.create_order` (atomic) creates the Order, items with price snapshots, the delivery address text, a mock paid Payment and the first `OrderStatusEvent`, reserves a unit and sets `Recommendation.is_selected` (feeds A13). |
| S19 | As a customer, I want to save delivery addresses and pick one per booking so that I don't retype my address and delivery is priced correctly. | done | | Ben | | `accounts.Address` (customer FK, one default). `accounts.addresses` page plus edit/delete/set default. Postal code must map to a delivery zone. Booking uses one of the customer's own addresses; the order keeps a text copy. |
| S20 | As a customer, I want to mark keep-out zones on my floor plan so that the robot avoids those areas. | done | | Ben | | Drag rectangles over the uploaded plan on the booking page. Stored as fractions of the image (`TaskRequest.keep_out_zones`), validated server-side (max 20, inside the image) and written into `policy_conditioning.map.keep_out_zones` for staff (A08). |

### Epic: After booking (S11 <-> A07)

| ID | Story | Status | ML | Owner | Shot | Notes |
|---|---|---|---|---|---|---|
| S11 | As a customer, I want to track my booking from confirmed to collected so that I know when the robot arrives and finishes. | done | | Manav, Ben (rework) | | `orders.order_detail`: step tracker plus update log from `OrderStatusEvent`, the shared setup summary built from the order's own line items, links to review (S13), support (S14) and cancel/reschedule (S18). Fed by staff story A07. |
| S12 | As a customer, I want to view my past orders and rebook so that repeat chores are one click. | done | | Ben | | `orders.order_list`: in-progress orders first, finished (collected/cancelled) below, each with photo, dates, address, price and stage. "Book again" (`order_rebook`, POST) copies the plan, spec and booked setup into a new plan starting in 3 days and opens the booking page. |
| S18 | As a customer, I want to cancel or reschedule a booking that hasn't started so that I can change my plans. | done | | Ben | | `orders.services.cancel_order` / `reschedule_order`. Allowed until the day before the start and before dispatch. Cancel refunds in full and frees the unit; reschedule keeps length and price, keeps the unit if free, moves the plan window. Both write an `OrderStatusEvent`. |
| S13 | As a customer, I want to rate and review a completed job so that others can choose well. | done | | Ben | | One review per completed/collected order, not editable after posting (`support.review_new`). Robot and skill pack come from the order. Shown on the order page and the robot's catalogue page. |
| S14 | As a customer, I want to raise a support ticket on an order, save it as a draft until it's ready, have it marked urgent automatically if the robot is already on site, and see replies, so that problems get fixed quickly. | done | | Ben | | One support page (`support.ticket_list`): pick an order, one ticket per order, draft or submit; read-only after submitting (changes by email). Priority URGENT if the order is ON_SITE or RUNNING. Entry points (order page link, old ticket URLs, `/support/`) all redirect here. |

## Staff panel

Custom views under `/staff/`, gated by `staff_required` (`is_staff`). Django admin is not allowed by the brief. Access control (the old A01) is a non-functional requirement, not a story: every `/staff/` view must use the guard.

### Epic: Operate the business

| ID | Story | Status | ML | Owner | Shot | Notes |
|---|---|---|---|---|---|---|
| A02 | As an ops manager, I want a dashboard of bookings, revenue and fleet utilisation so that I can run the business. | stub | | | | |
| A13 | As an ops manager, I want to see the recommendation acceptance rate so that I know whether the models are helping. | todo | ML monitoring | | | Acceptance = ML recs that reached checkout unmodified (`is_selected` and `source=ml`). Shown on the A02 dashboard. |
| A07 | As staff, I want to assign a fleet unit to an order and advance its status so that the customer's tracking page updates. | done | | Manav | | `staffpanel.order_list/order_detail`: assign a free unit, advance one step with an optional note (writes `OrderStatusEvent`); dispatch marks the unit deployed, collection frees it. Needs a unit assigned first. Pairs with S11. |
| A09 | As support staff, I want a ticket queue with replies and status so that issues are resolved. | stub | | | | Urgent tickets first. Must hide drafts (`SupportTicket.Status.DRAFT`); replies are `TicketMessage` rows, shown read-only to the customer on the S14 page. |

### Epic: Manage the catalogue and fleet (A03 + A04 + A05)
Same pattern across all three: list page, one shared add/edit page (`staffpanel/form.html`), list/unlist instead of delete, and a shared tab bar and "Needs attention" panel.

| ID | Story | Status | ML | Owner | Shot | Notes |
|---|---|---|---|---|---|---|
| A03 | As staff, I want to add, edit and deactivate robot models so that the catalogue stays current. | done | | Ben | | `staffpanel.robot_list/robot_edit/robot_toggle`. Unlist instead of delete (orders point at robots). Shows units and live orders per robot. Staff set which task types each robot can be booked for (`RobotModel.task_categories`), which drives `eligible_robots()` on the booking page and the planner's fallback. |
| A04 | As staff, I want to manage fleet units (status, depot, service date) so that inventory is accurate. | done | | Ben | | `staffpanel.fleet_list/fleet_edit`. Filters, status counts, next order, service due after 90 days. Reserved/deployed are set by orders only; a booked unit can't go to maintenance or retired. |
| A05 | As staff, I want to manage add-ons and skill packs, including compatibility and default conditioning, so that recommendations only use valid combos. | done | | Ben | | `staffpanel.addon_*` / `skillpack_*`. Codes are free-form but locked after creation. Skill packs carry task types (booking page uses them), robots and default conditioning JSON; multi-value fields use a searchable chip picker (`static/js/chip_select.js`). Sync issues (`catalog/checks.py`) show on every catalogue page. New codes are offered to customers at once but only recommended after retraining (see A15). |

### Epic: Human-in-the-loop ML (A08 -> A12)

| ID | Story | Status | ML | Owner | Shot | Notes |
|---|---|---|---|---|---|---|
| A08 | As staff, I want to review each paid order's ML output and full policy conditioning before dispatch, then approve it, flag it for follow-up or change the setup, so that bad recommendations are caught before a robot ships. | done | M1-M5 | Ben | | `staffpanel.review_list` / `review_detail`, logic in `orders/review.py`. Queue = confirmed orders not yet reviewed, grouped by ship day, biggest order first within a day; tabs for follow-up and approved. One-at-a-time view with ← / → keys: request, model outputs with confidences, risk flags, floor plan with keep-out zones, conditioning JSON, setup history. Approve tells the customer it was checked; follow-up needs a note and stays internal (staff email the customer). Change setup saves `Recommendation(source=staff)` and rebuilds the order lines with an adjustment line so the customer pays the same. Dispatch (A07) is blocked until approved. Never blocks the customer. Test data: `python manage.py seed_review_orders`. |
| A15 | As an ops manager, I want to see what each recommendation model decides, how it scored and which catalogue items it knows so that I know when a catalogue change needs a retrain. | done | M1-M5 | Ben | | `staffpanel.ml_models` at `/staff/recommendation-models/` (`planner/ml_registry.py`). Cards per model (algorithm, metrics, trained date, inputs) and coverage: live / not learned / switched off per task type, platform, attachment and skill pack. Named "recommendation models" so staff don't confuse them with skill packs. |
| A14 | As staff, I want low-confidence and risk-flagged recommendations listed first so that I review the riskiest ones before dispatch. | todo | M1-M5 | | | Sort/filter the A08 list using `category_confidence` and `edge_cases`. |
| A12 | As staff, I want to export overridden recommendations as labelled data so that the models can be retrained. | stretch | ML | | | CSV export of `source=customer/staff` rows. Closes the retraining loop. |

### Low priority (stretch)

| ID | Story | Status | ML | Owner | Shot | Notes |
|---|---|---|---|---|---|---|
| A11 | As staff, I want to manage promo codes so that I can run campaigns. | stretch | | | | S10 already applies promo codes (`PromoCode` model, WELCOME10 seeded), so this is only the staff CRUD. |
| A06 | As staff, I want to view and deactivate customer accounts and see their history so that I can support them. | stretch | | | | |
| A10 | As staff, I want to hide inappropriate reviews so that the storefront stays clean. | stretch | | | | |

## Remarks
- Report needs a wireframe or screenshot per story. Tick the Shot column once built.
- The ML criterion grades "complexity of the associated user stories": S04-S08 + S16/S17 + A08/A13/A14/A12/A15 form the ML loop (predict, explain, let a human correct, inspect, measure, retrain). Customer edits on the booking page (S08) are already logged as `source=customer` recommendations.
- Removed as a story: old A01 (staff guard), now a non-functional requirement above.
- Owner is filled in for stories built since the S08-S11 rework (Manav built the first S08-S11 and A07). Fill in the planner stories (S01-S07, S15-S17), which Claude built as the starting slice. The brief bans AI generating the whole app, so each of us must be able to explain our own stories in the code review.
