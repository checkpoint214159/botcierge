# Demo data for the video

Handoff spec for whoever builds the demo database, whether a person or a Claude session. Case IDs (C1-C7) follow the order they appear in `docs/video_script.md`. "D" means the recording day. Dates are relative, so generate the data close to recording.

## How to build it

- Start from a fresh database: delete `db.sqlite3`, then run `migrate`, `seed_demo`, `seed_review_orders`, `seed_support_tickets`. Most of what the video needs already comes from these.
- Add the rest (C1, C4, C7) in a small management command, `orders/management/commands/seed_video_demo.py`, modelled on `seed_review_orders.py`. It should use the real code path (`decompose` -> booking details -> `create_order` -> `advance_order`), not raw inserts, so prices, status events and unit reservations stay consistent. Make it idempotent with `--reset`, and have it touch only `tester*` accounts and Dana's past orders.
- **Leave "live" cases unseeded.** They happen on camera.
- After seeding, click through the whole script once and fix anything that doesn't match.
- Log the work in `docs/genai_log.md`.

## Accounts

| Who | Login | Notes |
|---|---|---|
| Dana (customer) | `demo` / `demopass123` | From `seed_demo`. Home address in Jurong West, so delivery and checkout work without setup. |
| Staff | `staff` / `staffpass123` | From `seed_demo`. |
| Test customers | `tester1`-`tester4` / `testpass123` | From `seed_review_orders`. They fill the review queue and the ticket queue. |

## Cases

**C1 (S03): Go2 has reviews.** Two or three 4-5 star reviews on Go2, on collected orders by `tester*` accounts. A couple of other robots get a review each, so the catalogue doesn't look empty.

**C2 (S04-S10, S20, live): Dana's main booking.** Nothing to seed. On camera:
- Description: "vacuum and mop my 4-room HDB, my cat sheds a lot". M1 says floor cleaning at 0.96 (checked against the committed model).
- Area 95 m², 4 rooms, tile floor, pets ticked, quiet hours 22:00-08:00. Pick a budget and window so it's within budget and feasible. Expected warnings: pets, quiet hours, no floor plan yet.
- A floor plan image to upload: a simple 4-room HDB layout at `docs/video_assets/floor_plan_hdb.png`, outside `source/` (Pillow can draw it, like `seed_review_orders` does).
- Start dates where a unit is free. `WELCOME10` exists from `seed_demo`.
- Dana's cart should be otherwise empty, so it reads cleanly. Check she has no leftover PLANNED plans.

**C3 (S16, live): vague request.** Nothing to seed. Description: "help me with the house this weekend". M1 says home patrol at 0.36, below the 0.55 threshold. Resubmit with **Tidying**.

**C4 (A02, A13): believable dashboard numbers.** Add collected `tester*` orders spread over the last 4-6 weeks (back-date `created_at` and the payment), so revenue isn't one spike on the recording day. Some should be booked on the models' setup unchanged and some after a customer edit (`save_customer_edit`), so "shipped as suggested" lands around 60-80%, with at least one task type clearly lower. These orders also give the A12 CSV a few rows besides C5.

**C5 (A08, A12): the bad recommendation.** Already seeded by `seed_review_orders`: tester4's elder care order, where a robot vacuum was picked. On camera it's changed to TIAGo with Companion Monitor, which also creates its row in the CSV.

**C6 (A09): ticket queue.** Already seeded by `seed_support_tickets` (urgent, waiting over a day, in progress, resolved, plus a customer draft that stays hidden). Dana's live ticket joins it on camera.

**C7 (S13): a finished job to review.** One COLLECTED order for Dana, Roomba floor cleaning, ended about D-10, **with no review yet**.

## After recording

Re-run `seed_demo` to undo the attachment added on camera, or leave it.
