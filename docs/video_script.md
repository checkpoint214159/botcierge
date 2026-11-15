# Video demo script

Brief: at most 15 minutes, demo the storefront and staff-panel user stories, both members present. Upload to YouTube and put the link in `readme.txt`.

Format: **[screen]** is what's on screen or what to click. Unmarked lines are narration. Story IDs in brackets are for us, not to be read out. Case IDs (C1, C2...) point to the data each step needs in `docs/video_demo_data.md`, numbered in script order.

The aim is the overall flow, not every story. We follow one booking from start to finish: Dana asks for help, the models plan the job, she books and pays, staff check and dispatch the robot, she gets help while it's in her home, and she reviews it afterwards. We close on the staff pages that show how the models are doing. Minor stories are left out on purpose (list at the bottom).

Before recording: log `demo` in on one browser window and `staff` in a private window, so switching sides is a window change. Start already logged in as Dana; we don't show sign-up.

---

## [intro]

hi im ben, and im manav, welcome to our is2108 project

## [prologue / project scope]

With the emerging field of robotics, we were imagining the future of B2C RaaS, which would involve customers ordering robots for their tasks (instead of buying one, should they lack the space or expertise in maintenance, or ownership will not provide value).

however, there lies a gap here: customers know what they want but may not be capable to describe it in a way that enables them to make a booking. 

- this requires an intermediary ML recommendation service, to decompose client requirements, budgets and other specifications, into an actionable service we can provide
- service includes delivery of the physical robot and its addons, alongside our custom-trained policies suited for their specific tasks.
- our moat is the byproduct of this comprehensive coverage and convenience: we offer a one-stop solution for task specification and physical robot programming and delivery.

## [features]

### 1. Asking for help (storefront)

**[screen]** Dana's window, home page. Click **Robots**, scroll the catalogue briefly, open **Go2** and scroll past its specs to the reviews (C1).

This is Dana, a customer. She can browse our catalogue of real robots, each with its specs, the skill packs it runs and reviews from past customers. [S02, S03] But most customers don't know which robot they need, so the main way in is to just describe the chore.

**[screen]** Click **Plan a job**. Type C2's description, fill in the home details (area, rooms, tile floor, pets) and the constraints (budget, dates, hours per day, quiet hours). Submit.

Dana describes the chore in her own words, tells us about her home, and sets her budget, dates and quiet hours. [S04, S05, S06]

**[screen]** Result page. Point at the task type and confidence, then the robot, attachments, skill pack, itemised quote and warnings.

Behind this, five machine learning models run in sequence. One reads her description and recognises floor cleaning, with 96% confidence. One estimates the hours the job needs, one picks the type of robot, one picks attachments, and one picks the skill pack, which is the trained behaviour the robot runs. Business rules then pick the cheapest robot that fits and build the quote. [S07]

She gets an itemised quote and plain-language warnings: she has pets, so the robot slows down, and her quiet hours switch off noisy modules.

**[screen]** Open the **Why this setup** card.

And she can see why each choice was made, so she can trust it. [S17]

**[screen]** Quick cut: a new plan with C3's vague description. Show the "we're not sure" warning, pick **Tidying** and resubmit.

If the request is too vague, the model says it's unsure instead of guessing, and lets her pick the task type herself. [S16]

### 2. Booking and paying (storefront)

**[screen]** Back to the C2 result. Click **Book this**. On the booking page, switch the robot and watch the price sidebar update. Point at a greyed-out attachment.

The booking page lets Dana adjust anything the models chose, and the price updates live. [S08] Only robots and attachments that fit the job are offered. Her changes are saved separately from the model's suggestion, which matters later.

**[screen]** Upload C2's floor plan and drag a keep-out rectangle over the fragile corner. Pick dates and save.

She uploads her floor plan and marks areas the robot must stay out of. [S20]

**[screen]** Cart, then **Checkout**. Enter `WELCOME10` and pay. Show the confirmation.

The plan goes into her cart, where we check a unit is actually free on her dates [S09], and she checks out with a promo code [S10]. Paying reserves a specific robot unit for her.

### 3. Checking the plan before the robot ships (staff)

**[screen]** Switch to the staff window. **Dashboard**. Sweep across the four panels and stop on the **Recommendations shipped as suggested** tile (C4).

This is our own staff panel; the Django admin wasn't allowed. The dashboard shows today's bookings, support load, revenue and fleet use at a glance. [A02] This tile shows how often the models' setup ships unchanged, which tells us whether they're actually helping. [A13]

**[screen]** **Bookings → Review before dispatch**. Show the queue grouped by ship day with risk flags. Click **Riskiest first**.

Customers pay straight away, but before any robot leaves the depot, a person checks what the models decided. [A08] Orders are grouped by ship day, and each one shows why it might need a closer look. Staff can also put the riskiest first. [A14]

**[screen]** Open C5 (the elder care order). Point at the model outputs and confidences, then the robot it chose: a robot vacuum. Click **Change setup**, choose TIAGo with Companion Monitor, save, approve.

Here's why this step exists. This customer wants a companion for their grandmother, and the models picked a robot vacuum. It's technically allowed, but it's wrong. Staff correct it before it ships, and the customer still pays what they agreed.

**[screen]** Open Dana's order. Point at her keep-out zone on the floor plan and the robot configuration. Approve.

Dana's order is fine. Staff can see her floor plan with the keep-out zone and the full configuration the robot will run, then approve it.

### 4. Dispatching (staff)

**[screen]** **Bookings → Orders**, open Dana's order. Assign a unit. Advance to **Dispatched** with the note "Driver Ali, ETA 2pm", then to **On site, mapping**.

Staff assign a robot unit and move the order along step by step. An order can't be dispatched until it has passed review. [A07]

### 5. While the robot is in her home (storefront ↔ staff)

**[screen]** Dana's window. Open the order: the tracker and update log.

Dana sees each step as it happens, including the driver note. [S11]

**[screen]** Click **Get help**, write "The robot keeps bumping into the shoe rack by the door", submit. Point at **Urgent**.

Something's not right, so she raises a ticket. Because the robot is in her home right now, it's marked urgent automatically. [S14]

**[screen]** Staff window. **Customers → Support tickets** (C6). Show urgent tickets at the top. Open Dana's, type a reply, **Send reply**.

Staff work through tickets urgent first, then by how long they've waited. [A09]

**[screen]** Dana's window, refresh. Show the reply.

The reply shows up on Dana's side.

### 6. After the job (storefront)

**[screen]** **My orders**. Open the finished order C7, click **Leave a review**, give 4 stars and submit. Then open the robot's page to show it.

When a job is done, Dana can rate it, and the review appears on the robot's page for the next customer. [S13] From her orders she can also rebook a past job in one click, or reschedule or cancel one that hasn't started.

### 7. Keeping the catalogue and models in sync (staff)

**[screen]** Staff window. **Catalogue → Robots**, glance at the list. Then **Attachments**: add "UV sterilising lamp", code `uv_lamp`, for wheeled base. Save.

Staff manage robots, fleet units, attachments and skill packs from the same kind of page. [A03, A04, A05] Let's add a new attachment.

**[screen]** **Catalogue → Recommendation models**. Scroll the model cards, then point at `uv_lamp` marked "not learned".

This page shows what each model does, how well it scored, and what it knows. [A15] Our new lamp can be booked straight away, but the models won't recommend it until we retrain, and this page tells staff that.

**[screen]** Scroll to the acceptance table by task type. Then click **Download changes as training data (CSV)** and show C5's row.

Here's the acceptance rate by task type, lowest first, which shows where the models need better data. [A13] And every change made by customers or staff, like the elder care fix we just made, downloads as labelled training data for the next retrain. [A12]

So that's the full loop: the models recommend, the customer adjusts, staff correct before dispatch, we measure how the models are doing, and every correction feeds the next round of training.

## [outro]

(to write)

---

## What's shown and what's left out

Shown: S02, S03, S04, S05, S06, S07, S16, S17, S08, S20, S09, S10, S11, S14, S13; A02, A13, A08, A14, A07, A09, A03-A05 (briefly), A15, A12. S12 and S18 get one spoken line, with no demo.

Left out on purpose (all built, and the report covers them): S01 register, S01b profile, S19 addresses, S15 my plans, S12 rebook and S18 cancel/reschedule (no demo), A04 fleet details, A06 customer accounts, A10 hiding reviews, A11 promo codes. Also cart edge cases (no free unit, missing floor plan) and the follow-up path in review.
