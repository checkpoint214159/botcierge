# Video demo script

Brief: at most 15 minutes, demo the storefront and staff-panel user stories, both members present. Upload to YouTube and put the link in `readme.txt`.

Format: **[screen]** is what's on screen or what to click. Unmarked lines are narration. Story IDs in brackets are for us, not to be read out. The data each beat needs is in `docs/video_demo_data.md`, with matching case IDs (C1, C2...).

The order follows one booking from start to finish. Dana books a robot, staff check and dispatch it, then Dana tracks it, reports a problem and leaves a review. The catalogue, customer and model pages come last, because they make the most sense once the audience has seen a full order.

Recording tip: keep `demo` logged in on one browser window and `staff` in a private window, so switching sides is a window change, not a log out and log in. Menu names below match the staff navbar (Dashboard, Catalogue, Bookings, Customers).

---

## [intro]

hi im ben, and im manav, welcome to our is2108 project

## [prologue / project scope]

emerging technology robotics, we were imagining the future of B2C RaaS, which would involve customers ordering robots for their tasks (instead of buying one, should they lack the space or expertise in maintenance, or ownership will not provide value).

however, there lies a gap here: customers know what they want but may not be capable to describe it in a way that enables them to make a booking. 

- this requires an intermediary ML recommendation service, to decompose client requirements, budgets and other specifications, into an actionable service we can provide
- service includes delivery of the physical robot and its addons, alongside our custom-trained policies suited for their specific tasks.
- our moat is the byproduct of this comprehensive coverage and convenience: we offer a one-stop solution for task specification and physical robot programming and delivery.

## [features]

### 1. First visit: browsing and signing up

**[screen]** Home page, logged out. Scroll once, then click **Robots**.

Before booking anything, a customer can look around. This is our catalogue: eleven real robots, from a robot vacuum up to Boston Dynamics' Spot. [S02]

**[screen]** Filter platform = Quadruped, then environment = outdoor, then type "patrol" in the keyword box. Clear them and sort by price (low to high), then by rating.

You can filter by the kind of robot, where it works, or a keyword, and sort by daily price or customer rating. Ratings come from real reviews on completed jobs, which we'll show later.

**[screen]** Open **Go2** (C11, it has reviews).

Each robot has its own page with specs (payload, battery, noise level, stair ability), the skill packs that can run on it, and reviews from past customers. [S03]

**[screen]** Click **Register**. Fill in a new account (C1) and choose housing type "HDB".

Signing up asks for your housing type, so later plans start with sensible defaults for your home. [S01]

**[screen]** Switch to the `demo` window. Click the greeting in the navbar to open the profile, change household size and save.

We'll switch to our demo customer, Dana, who already has some history. Dana can update her phone number, housing type and household size here. [S01b]

**[screen]** Click **Addresses**. Add an address with postal code `740123` and show the error. Fix it to C2's Tampines address, save, and set it as default. Then set Home back as default.

Delivery addresses are saved separately, so Dana doesn't retype them on every booking. We price delivery by distance from our depot in Jurong West, using the postal code. A postal code that doesn't exist in Singapore is rejected, because we couldn't price the delivery. [S19]

### 2. Planning a job with the recommendation models

**[screen]** Click **Plan a job**. Type C3's description and fill in the space and constraints (area, rooms, tile floor, pets ticked, budget, dates, hours per day, quiet hours). Submit.

This is the core of Botcierge. Dana doesn't need to know what a "wheeled AMR" or a "coverage policy" is. She describes the chore in her own words [S04], tells us about her space (size, rooms, floor type, pets, children, stairs, fragile items) and can attach a floor plan [S05]. She also sets her budget, date window, hours per day and quiet hours [S06].

**[screen]** Result page. Point at each block in turn: task type with confidence, robot, add-ons, skill pack, itemised quote, warnings.

Five machine learning models run in sequence. The first reads her description and decides it's floor cleaning, with 96% confidence. The second estimates how many robot-hours the job needs. The third picks the type of robot, and our rules choose the cheapest robot of that type that meets her constraints. The fourth picks attachments, and the fifth picks a skill pack, which is the trained behaviour the robot runs. [S07]

The quote is itemised: delivery for her zone, daily rates for the robot and each add-on, and the skill pack fee. Below it we flag risks. Here: pets are present, so the robot slows down; her quiet hours switch off noisy modules; and there's no floor plan yet, so the robot will map the flat on arrival.

**[screen]** Open the **Why this setup** card.

So customers can trust the recommendation, we explain each choice in plain language. [S17] The full robot configuration behind this, which we call policy conditioning, stays staff-only. Customers see a short summary of the skill pack.

**[screen]** Back to **Plan a job**. Type C4's vague description and submit.

If a description is too vague, the model isn't confident, and we say so instead of guessing.

**[screen]** Show the "we're not sure" warning (about 36%). Pick task type **Tidying** from the selector and resubmit.

Here it's only 36% sure, below our threshold, so the page warns Dana and lets her pick the task type herself. That choice skips the first model, and the rest of the pipeline runs as normal. [S16]

**[screen]** Navbar: **My plans**.

Every plan is saved, so Dana can come back and book later. [S15]

### 3. Booking and paying

**[screen]** From the C3 result, click **Book this**. The booking page opens with the live price sidebar.

Each plan gets one booking page. Dana can adjust anything the models chose, and the price on the right updates as she goes. [S08]

**[screen]** Open the robot dropdown to show only floor-cleaning robots are offered. Switch to PUDU CC1 and watch the sidebar. Show a greyed-out attachment that doesn't fit the robot. Untick or tick an add-on. Change the skill pack.

Only robots marked as suitable for this task type are offered, and attachments that don't fit the chosen robot are greyed out, so she can't build something we can't deliver. When she changes the setup we save it as a new recommendation and keep the model's original. That lets staff see what was changed, and it's data we can retrain on later.

**[screen]** Change the delivery address from Home (West) to the Tampines address (East). The delivery fee goes from S$29 to S$69. Switch back.

Changing the address re-prices delivery by zone. [S19]

**[screen]** Upload C3's floor plan image. Drag two rectangles over the fragile area and the pet bowls.

Dana uploads her floor plan and drags keep-out zones over areas the robot must avoid. They're saved with the plan and passed to the robot's configuration, and staff see them when they review the order. [S20]

**[screen]** Pick dates. Save. Go to the **Cart** (point at the navbar badge).

Saved plans wait in the cart. [S09]

**[screen]** Cart with C5's plans: one ready, one needing a floor plan, one whose start date has passed, and one where no unit is free. Point at each message. Remove one plan, then restore it.

The cart checks every plan before checkout. One is ready. One still needs a floor plan. One has a start date that has passed. And for this one, every unit of that robot is already booked on those dates, so we say so now, not after payment. The same checks run on the booking page, the cart and checkout, so they never disagree.

**[screen]** Click **Checkout** on the C3 plan. Enter `WELCOME10`, apply, and show the discount line. Pay.

At checkout, Dana can apply a promo code. [S10] Payment is simulated. Paying creates the order with a snapshot of every price, reserves a specific unit of the robot, and records the first status update.

**[screen]** Confirmation page, then click through to the order page. It shows Confirmed.

### 4. Staff: the dashboard and checking plans before the robot ships

**[screen]** Switch to the `staff` window. **Dashboard** at `/staff/`. Point at the four panels in turn: Bookings, Support, Business (last 30 days), Catalogue and fleet.

Now the staff side. The Django admin was off-limits, so the whole staff panel is our own, and every page checks that the user is staff.

The dashboard is where the ops manager starts the day. [A02] The bookings panel shows what's waiting for review, what ships today and tomorrow, and what's out with customers. The support panel shows tickets to answer, how many are urgent and how long the oldest has waited. The business panel shows revenue and paid bookings over the last 30 days, revenue by day and by task type, refunds and the average rating. The last panel shows fleet utilisation (the share of units reserved or out on a job), units by status, units due for service and any catalogue problems.

**[screen]** Point at the **Recommendations shipped as suggested** tile in the Business panel.

This tile tells us whether the models are actually helping: the share of booked orders where neither the customer nor our review changed the robot, attachments or skill pack. [A13] We'll see the breakdown on the models page later.

**[screen]** **Bookings → Review before dispatch**. Show the groups by ship day (Overdue, Ships today, Ships tomorrow...) and the risk flags on each row.

Customers pay straight away, but before a robot leaves the depot, a person checks what the models decided. [A08] The queue is grouped by ship day, soonest first, and within a day the most expensive orders come first, because more is at stake. Each row shows why it might need a closer look: the model was unsure, the customer changed the setup, the robot isn't listed for that task type, or the job is over budget or might not finish in time.

**[screen]** Click **Riskiest first**. The groups change to "N things to check".

When staff are short on time, they can flip the queue to riskiest first. [A14] Orders with the most warnings come to the top, so the shakiest recommendations get checked while there's still time to call the customer. The arrow keys and "next" follow whichever order is chosen. Switch back to **By ship day**.

**[screen]** Open the first order. Press → a few times to step through, then go to C8 (tester4's elder care order).

Staff can step through the queue one order at a time with the arrow keys. Each order shows the customer's request, every model's output with its confidence, the risk flags, the floor plan with the keep-out zones, the full robot configuration, and the setup history.

Here's a case the review exists for. This customer wants a companion for their grandmother, but they didn't need anything carried, so the rules picked the cheapest suitable robot: a robot vacuum. That's technically valid but obviously wrong.

**[screen]** Click **Change setup**. Choose TIAGo and the Companion Monitor skill pack. Save. Show the adjustment line.

Staff change the setup. We save it as a staff correction and rebuild the order with an adjustment line, so the customer pays exactly what they agreed to.

**[screen]** Approve it. Open C9 and choose **Needs follow-up**. Submit with an empty note to show it's required, then add a note. Show the three tabs (To review / Needs follow-up / Approved, not dispatched).

Approving tells the customer their plan was checked. If something needs the customer's input, staff flag it for follow-up. The note is required, so whoever emails the customer knows what to ask, and it stays internal.

**[screen]** Find Dana's new order (C3) in the queue, open it and point at the keep-out zones on her floor plan. Approve it.

### 5. Staff: dispatching

**[screen]** **Bookings → Orders**. Filter by status. Open an order that's still "to review" (C10) and try to dispatch it. Show the refusal.

The orders page is where staff run each job. [A07] An order can't be dispatched until it has been reviewed.

**[screen]** Open Dana's approved order. Assign a free unit. Advance to **Dispatched** with the note "Driver Ali, ETA 2pm". Advance to **On site, mapping**.

Staff assign a specific unit from the fleet and move the order forward one step at a time, with an optional note. Dispatching marks the unit as deployed, and collection frees it again.

### 6. Customer and staff: tracking and support

**[screen]** Switch to the `demo` window. Open the order.

Every step staff take shows up for the customer. [S11] Dana sees a progress tracker from confirmed to collected, an update log with the staff notes, and a summary of exactly what she booked.

**[screen]** Click **Get help**. The support page opens with this order selected. Type a message ("The robot keeps bumping into the shoe rack by the door"), save it as a draft. Then reopen it, finish the message and submit. Point at the **Urgent** priority.

If something goes wrong, Dana raises a support ticket on the order. [S14] She can save it as a draft and send it when it's ready. Because the robot is in her home right now, the ticket is marked urgent automatically. After submitting it's read-only.

**[screen]** Switch to `staff`. **Customers → Support tickets**. Show the tabs (to answer / in progress / resolved), the two urgent tickets at the top (Dana's and an older seeded one), and a "Waiting over a day" flag further down. Point out that C19's customer draft isn't in the list.

On the staff side, the ticket queue works like the review queue. [A09] Urgent tickets come first, then the ones that have waited longest. Tickets customers haven't sent yet never appear here.

**[screen]** Open Dana's ticket. Type a reply and click **Save draft**. Then finish it and click **Send reply**. The ticket moves to "in progress". Back in the list, open C20 (the ticket with a half-written staff draft), finish it and click **Send and resolve**.

Staff can save a reply as a draft, which the customer can't see yet, or send it. The first reply moves the ticket to in progress, and "send and resolve" closes it in one step. Each reply records which staff member wrote it.

**[screen]** Switch to `demo` and refresh the support page. Show the reply under Dana's ticket.

The reply shows up on Dana's support page.

### 7. Customer: order history, reviews and changes

**[screen]** **My orders**. Point at in-progress orders at the top and finished ones below.

Dana's order history puts orders in progress first, with collected and cancelled ones below. [S12]

**[screen]** Open the collected order C13a and click **Leave a review**. Give 4 stars and a comment, then submit. Show it on the order page, then open the robot's catalogue page and show it there.

Once a job is finished, she can rate it. [S13] It's one review per order, and it can't be edited afterwards, so the ratings reflect what customers said at the time. The review appears on the order and on the robot's public page, and it feeds the rating sort we saw earlier.

**[screen]** On the same order, click **Book again**. The booking page opens with the same setup, three days out.

Repeat chores are one click: "Book again" copies the plan and the setup she actually booked into a new plan and opens the booking page.

**[screen]** Open the upcoming order C14. **Reschedule**: move it by a week and show the new dates and the update log entry. Open C15 and **Cancel**: show the refund note and the Cancelled status. Then open the running order C16 and point out that both buttons are gone.

Plans change. Until the day before the start, and before the robot is dispatched, Dana can reschedule: same length, same price, and we keep her unit if it's free. Or she can cancel for a full refund, which frees the unit for someone else. [S18] Once the robot has left the depot, these options are gone.

### 8. Staff: managing the catalogue and fleet

**[screen]** Switch to `staff`. **Catalogue → Robots**. Show the units and live orders per robot.

Staff keep the catalogue up to date. [A03] Each robot shows how many units we have and how many live orders use it.

**[screen]** Edit Go2: show the task types chips and add one, then save. Then **Unlist** the Winbot. Point at the **Needs attention** panel ("No active robot is marked for window cleaning"). Use **View the shop** to show the catalogue without the Winbot. Relist it.

Staff choose which task types each robot can be booked for, and that controls what the booking page offers. Robots are never deleted, because past orders point at them. We unlist them instead. When a change leaves a gap, like no robot left for window cleaning, the "Needs attention" panel flags it on every catalogue page and on the dashboard.

**[screen]** **Catalogue → Fleet units**. Filter by status and show the counts. Point at C17's "service due" unit. Try to set a reserved unit to maintenance and show the refusal. Set a free unit to maintenance.

Each physical unit is tracked with its status, depot and last service date. [A04] Units are flagged for service after 90 days. A unit that's booked can't be pulled for maintenance, because that would break a customer's order. Only orders move units into reserved or deployed.

**[screen]** **Catalogue → Attachments**: add "UV sterilising lamp" with code `uv_lamp`, compatible with wheeled base. **Skill packs**: open Companion Monitor and show the task types, compatible robots (chip picker) and default configuration JSON. Type broken JSON and save to show the error, then undo.

Attachments and skill packs work the same way. [A05] Staff control which robots each one fits and the default configuration each skill pack starts from, and the form checks that configuration before saving. This keeps recommendations to combinations we can actually deliver.

### 9. Staff: promotions, customer accounts and reviews

**[screen]** **Bookings → Promo codes**. Point at WELCOME10's times used and discount given (Dana's checkout is in there). Click add: code `cny20`, 95%, and save to show the "Between 1% and 90%" error. Change to 20% with an end date and save. It shows as `CNY20`. Turn it off, then on.

Staff run promotions here. [A11] Each code shows how often it's been used and how much discount it has given, including Dana's booking from earlier. Codes are stored in capitals and capped at 90% off. They can be switched off or given an end date, but never renamed or deleted, because past orders point at them.

**[screen]** **Customers → Accounts**. Search "Dana" and open her account: orders, tickets, reviews and addresses on one page. Go back, open `alex` (from C1) and **Deactivate**. Show the message, then reactivate.

When a customer calls, staff can see their whole history on one page: bookings, spend, tickets, reviews and addresses. [A06] Staff can deactivate an account so it can't log in. Any live orders on it still go ahead, and the page warns about them. Staff accounts are never listed here.

**[screen]** **Customers → Reviews**. Click the "2 stars or fewer" tab. **Hide** C18's review. Then use **View the shop** to open Go2 and show the review is gone and the average has changed. Show the "hidden" tab.

Staff can hide inappropriate reviews. [A10] Hiding removes the review from the robot's page and from its average rating, and it can be shown again later.

### 10. Staff: the recommendation models

**[screen]** **Catalogue → Recommendation models**. Scroll through the five cards, then the coverage table. Point at `uv_lamp` marked "not learned".

Staff can see what each model decides, how it scored on held-out data, when it was trained and what it takes as input. [A15] The coverage table shows which task types, robot types, attachments and skill packs each model knows. The lamp we just added can be booked right away, but the models won't recommend it until we retrain. This page tells staff when a catalogue change needs a retrain.

**[screen]** Scroll to the acceptance tiles and the per-task-type table.

Here's the acceptance rate from the dashboard, broken down. [A13] We split it into recommendations the customer kept, ones our review kept, and ones shipped exactly as suggested. The table lists task types lowest first, because that's where the models need better training data. The elder care order we fixed earlier counts against its task type here.

**[screen]** Click **Download changes as training data (CSV)** and open the file. Point at the row for C8: the request features, what the models suggested and what staff chose.

Every change customers and staff make is exported as labelled training data. [A12] Each row has the request, what the models suggested and what was actually chosen, which gives us corrected labels for the robot, attachment and skill pack models. We add it to the training set by hand and retrain.

That's the full loop: the models recommend, the customer adjusts, staff correct before dispatch, we measure how often the models were right, and every correction becomes training data for the next round.

## [outro]

(to write)

---

## Coverage check

All stories are done on `main` as of 2026-11-15.

| Story | Section |
|---|---|
| S01, S01b, S19, S02, S03 | 1 |
| S04, S05, S06, S07, S16, S17, S15 | 2 |
| S08, S09, S10, S19 (zone pricing), S20 | 3 |
| A02, A13 (tile), A08, A14 | 4 |
| A07 | 5 |
| S11, S14, A09 | 6 |
| S12, S13, S18 | 7 |
| A03, A04, A05 | 8 |
| A11, A06, A10 | 9 |
| A15, A13 (breakdown), A12 | 10 |
