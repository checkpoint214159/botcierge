# Logical data model

Physical model = Django models in each app. Auth uses Django's built-in `User` (staff = `is_staff`).

```
User 1─1 CustomerProfile
User 1─* TaskRequest 1─1 TaskSpec
                    1─* Recommendation *─1 RobotModel
                                       *─* AddOn
                                       *─1 SkillPack *─* RobotModel
RobotModel 1─* FleetUnit
User 1─* Order *─1 Recommendation
            1─* OrderItem  (robot | addon | skill_pack | service; robot lines get a FleetUnit)
            1─* OrderStatusEvent
            1─1 Payment
            *─1 PromoCode
Order 1─1 Review
User 1─* SupportTicket *─1 Order (optional)
                      1─* TicketMessage
```

| App | Model | Purpose |
|---|---|---|
| accounts | CustomerProfile | Housing type, contact, address |
| catalog | RobotModel | Catalogue entry for a real product: manufacturer, daily rate, capabilities, photo (staff upload or seeded static photo) with credit |
| catalog | FleetUnit | Physical unit = inventory (available / reserved / deployed / maintenance / retired) |
| catalog | AddOn | Attachment with daily rate and platform compatibility |
| catalog | SkillPack | Robot policy as a product; `default_conditioning` JSON |
| planner | TaskRequest | Customer input: chore text, space, constraints, floor plan |
| planner | TaskSpec | Decomposition: category, subtasks, edge cases, robot-hours, feasibility |
| planner | Recommendation | Robot + add-ons + skill pack + conditioning + quote; `source` = ml / customer / staff |
| orders | Order, OrderItem, OrderStatusEvent, Payment, PromoCode | Booking, line items, tracking timeline, mock payment |
| support | Review, SupportTicket, TicketMessage | After-sales |
