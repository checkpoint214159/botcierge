# Demo data for the video

Handoff spec for whoever builds the demo database, whether a person or a Claude session. Case IDs (C1...) match `docs/video_script.md`. "D" means the recording day. Dates are relative, so the data has to be generated close to recording.

## How to build it

- Add a management command, `orders/management/commands/seed_video_demo.py`, modelled on `seed_review_orders.py`. It should go through the real code path (`decompose` -> booking details -> `create_order`, then `advance_order` / `cancel_order` for later states), not raw inserts. That way prices, status events, unit reservations and recommendations are consistent. Make it idempotent with `--reset`, and have it touch only the accounts it creates plus `demo`'s orders, plans and tickets.
- Start from a fresh database: delete `db.sqlite3`, then run `migrate`, `seed_demo`, `seed_review_orders`, `seed_video_demo`.
- **Leave the "live" cases unseeded.** The script creates them on camera, so the seed must not create them. Check the preconditions instead (for example, that the username is free).
- After seeding, check every case below in the browser and fix any mismatch, for example a flag that doesn't appear. The ML outputs quoted here were probed on 2026-11-15 and match the committed models.
- Log the work in `docs/genai_log.md` and add a test that the command runs.

## Accounts

| Who | Login | Notes |
|---|---|---|
| Dana (main customer) | `demo` / `demopass123` | From `seed_demo`. Home address: Blk 123 Jurong West St 41, 640123 (West, S$29 delivery). All storefront cases below belong to Dana unless stated. |
| Staff | `staff` / `staffpass123` | From `seed_demo`. |
| Test customers | `tester1`-`tester4` / `testpass123` | From `seed_review_orders`. They fill the A08 queue and block units for C5d. |

## Storefront cases

**C1 (S01, live): registration.** Precondition: no user `alex` exists. On camera: username `alex`, housing type HDB.

**C2 (S19, live): addresses.** First attempt uses postal code `740123`. Sector 74 doesn't exist, so the form rejects it; verify the form error is clear. Then add "Mum's place, Blk 201 Tampines St 21, #04-88, 520201" (East, S$69). Precondition: Dana has only the Home address, so the add is visible.

**C3 (S04-S08, S10, S20, live): main booking.** Precondition: none. On camera:
- Description: "vacuum and mop my 4-room HDB, my cat sheds a lot". M1 says floor_cleaning at 0.96.
- Area 95 m², 4 rooms, tile floor, pets ticked, quiet hours 22:00-08:00.
- Budget and window: pick values so the plan stays **within budget** and **feasible**. Leave the floor plan empty at the planning step, so the "no floor plan" warning shows.
- Expected warnings: pets, quiet hours, no floor plan.
- Needed: a floor plan image for upload on the booking page. Put a simple 4-room HDB plan at `docs/video_assets/floor_plan_hdb.png`, which is outside `source/`. Pillow can draw it the way `seed_review_orders` does.
- Pick start dates that still leave a free unit after C5d.
- `WELCOME10` exists from `seed_demo`.

**C4 (S16, live): low confidence.** Description: "help me with the house this weekend". M1 says home_patrol at 0.36, below the 0.55 floor. On camera, resubmit with the task type hint **Tidying**. Other fields: defaults.

**C5 (S09, S15): cart states.** Pre-seed these PLANNED plans for Dana, each with a different task type so they're easy to tell apart:
- **C5a, ready:** window cleaning ("clean all the windows in my condo, the glass is filthy"), Home address, floor plan uploaded, start D+10.
- **C5b, needs a floor plan:** "the kids' room is a disaster, toys everywhere" (tidying), address set, no floor plan, start D+12.
- **C5c, start date passed:** pool cleaning, start D-2, otherwise complete.
- **C5d, no free unit:** event serving with BellaBot, start D+7 for 1 day. Book all 3 BellaBot units for D+7 to testers (extra `tester*` orders), so the cart shows "No BellaBot is free...". Keep C3's robot (Roomba or PUDU) free on its dates.
- **C5e, removed:** one plan in DRAFT, so "Restore" can be shown.

All of these should also appear on "My plans" (S15).

**C11 (S02, S03): ratings and reviews.** Give Go2 at least 2 reviews and give three or four other robots one or two reviews each, with different ratings, so sorting by rating visibly reorders the list. Reviews need completed or collected orders, so attach them to past orders of `tester*` accounts, and of Dana for C13b.

**C12 (S14): ticket with a reply.** On one of Dana's finished orders (C13b), seed a submitted ticket (status OPEN or IN_PROGRESS, priority NORMAL) and one staff `TicketMessage` reply. A09 isn't built, so write the reply directly.

**C13 (S12, S13): finished orders for Dana.**
- **C13a:** COLLECTED, Roomba floor cleaning, ended D-10, **no review yet**. Used for the live review and "Book again".
- **C13b:** COLLECTED, ended D-20, already reviewed (4 or 5 stars). Holds C12's ticket.
- **C13c:** CANCELLED with a full refund (`cancel_order`), originally for D+3, cancelled D-5.

**C14 (S18): reschedule.** CONFIRMED, approved, not dispatched, lawn care, starts D+6 for 2 days. The unit must also be free a week later, so the reschedule keeps it.

**C15 (S18): cancel.** CONFIRMED, not dispatched, tidying, starts D+9.

**C16 (S11, S14 fallback, S18 boundary): running order.** RUNNING, started D-1, ends D+1, with the full status event log and staff notes on each step ("Driver Ali, ETA 2pm", "Mapping done, 4 rooms"). No ticket on it. If the live C3 flow fails on camera, raise the urgent ticket here instead. Cancel and reschedule should not be offered.

## Staff cases

**C8 (A08): bad recommendation to fix.** Already in `seed_review_orders`: tester4's elder care order, where a robot vacuum was picked. On camera, change it to TIAGo with Companion Monitor and approve.

**C9 (A08): follow-up.** Any other pending order from `seed_review_orders`, for example tester2's lawn order. The follow-up note is typed on camera. tester3's pool order is already in the follow-up tab, so that tab isn't empty before the demo.

**C10 (A07): dispatch refused.** Any order still "to review". The dispatch attempt is refused on camera.

**Dana's C3 order:** appears in the A08 queue after the live checkout. Staff approve it, assign a unit and advance it to On site, all on camera.

**C17 (A04): fleet states.**
- One unit with `last_serviced` 120 days ago, so it shows as service due.
- One unit in MAINTENANCE and one RETIRED, so the status counts aren't all "available".
- At least one RESERVED unit (from orders) for the refused maintenance change.

**A03 / A05:** no seed needed. Unlisting the Winbot and adding `uv_lamp` happen live. Re-run `seed_demo` after recording to undo catalogue edits, or relist the Winbot on camera.

## If A02 / A13 / A09 get built before recording

The data above already supports them if the seed also has:
- Collected orders spread over the last 4 to 6 weeks, so revenue and booking charts aren't one spike (A02).
- A mix of orders paid on the model's recommendation unchanged (`source=ml`, `is_selected`) and on customer-edited ones (`source=customer`), so the acceptance rate isn't 0% or 100% (A13).
- Tickets in several states for the queue (A09): at least one URGENT (C3 live, or seeded on C16), two NORMAL OPEN, one RESOLVED, and one DRAFT that must **not** appear in the staff queue.
