"""A02: the ops manager's dashboard. Four panels, each a summary with links to the page that does the work:

1. Catalogue and fleet: what can be rented and how busy the fleet is.
2. Business: revenue from paid bookings, refunds, average order, ratings.
3. Bookings: what needs review, what ships soon, what is out with customers.
4. Support: tickets waiting for an answer.

Each panel is one function returning a plain dict, so the template stays simple and each number
can be explained (and tested) on its own.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from catalog.checks import catalogue_issues
from catalog.models import AddOn, FleetUnit, RobotModel, SkillPack
from catalog.taxonomy import TASK_CATEGORY_CHOICES
from orders.models import Order, Payment
from support import queue as tickets
from support.models import Review, SupportTicket

SERVICE_INTERVAL_DAYS = 90  # a unit not serviced for this long is flagged (also used by A04)
WINDOW_DAYS = 30   # "recent" for the business panel
CHART_DAYS = 14    # daily revenue bars
OUT_WITH_CUSTOMER = [Order.Status.DISPATCHED, Order.Status.ON_SITE, Order.Status.RUNNING]
F = FleetUnit.Status


def _pct(part, whole):
    return round(100 * part / whole) if whole else 0


def fleet_panel():
    counts = {s: 0 for s in F.values}
    for row in FleetUnit.objects.values("status").annotate(n=Count("id")):
        counts[row["status"]] = row["n"]
    in_service = sum(n for s, n in counts.items() if s != F.RETIRED)
    busy = counts[F.RESERVED] + counts[F.DEPLOYED]
    due = timezone.localdate() - timedelta(days=SERVICE_INTERVAL_DAYS)
    issues = catalogue_issues()
    return {
        "robots_listed": RobotModel.objects.filter(is_active=True).count(),
        "robots_unlisted": RobotModel.objects.filter(is_active=False).count(),
        "addons": AddOn.objects.filter(is_active=True).count(),
        "skill_packs": SkillPack.objects.filter(is_active=True).count(),
        "units": in_service,
        "status_rows": [(label, counts[code], _pct(counts[code], in_service))
                        for code, label in F.choices if code != F.RETIRED],
        # utilisation: units that are booked (reserved) or out with a customer (deployed)
        "utilisation": _pct(busy, in_service),
        "service_due": FleetUnit.objects.exclude(status=F.RETIRED)
        .filter(Q(last_serviced__lt=due) | Q(last_serviced__isnull=True)).count(),
        "issues": issues[:3], "issue_count": len(issues),
    }


def business_panel():
    now = timezone.now()
    since = now - timedelta(days=WINDOW_DAYS)
    paid = Payment.objects.filter(status=Payment.Status.PAID, paid_at__gte=since)
    # SQLite sums decimals as floats, so round back to cents
    revenue = (paid.aggregate(s=Sum("amount"))["s"] or Decimal("0")).quantize(Decimal("0.01"))
    n_paid = paid.count()
    refunded = Payment.objects.filter(status=Payment.Status.REFUNDED, paid_at__gte=since)

    # daily revenue for the bar chart, oldest day first (days with no sales show as empty bars)
    today = timezone.localdate()
    days = [today - timedelta(days=i) for i in range(CHART_DAYS - 1, -1, -1)]
    by_day = {d: Decimal("0") for d in days}
    for p in Payment.objects.filter(status=Payment.Status.PAID, paid_at__gte=now - timedelta(days=CHART_DAYS)):
        d = timezone.localdate(p.paid_at)
        if d in by_day:
            by_day[d] += p.amount
    top_day = max(by_day.values()) or 1
    daily = [{"day": d, "amount": a, "height": max(2, round(100 * a / top_day)) if a else 0} for d, a in by_day.items()]

    # revenue by task type, from the plan each paid order was booked from
    labels = dict(TASK_CATEGORY_CHOICES)
    by_type = {}
    for o in (Order.objects.filter(payment__in=paid)
              .select_related("recommendation__task_request__spec")):
        spec = getattr(o.recommendation.task_request, "spec", None) if o.recommendation else None
        key = labels.get(spec.task_category, "Other") if spec else "Other"
        by_type[key] = by_type.get(key, Decimal("0")) + o.total
    top_type = max(by_type.values(), default=0) or 1
    types = [{"label": k, "amount": v, "width": round(100 * v / top_type)}
             for k, v in sorted(by_type.items(), key=lambda kv: -kv[1])]

    reviews = Review.objects.filter(is_visible=True, created_at__gte=since)
    return {
        "window": WINDOW_DAYS, "revenue": revenue, "orders": n_paid,
        "average": (revenue / n_paid).quantize(Decimal("0.01")) if n_paid else Decimal("0"),
        "refunds": refunded.count(), "refunded": refunded.aggregate(s=Sum("amount"))["s"] or Decimal("0"),
        "daily": daily, "chart_days": CHART_DAYS, "types": types,
        "rating": reviews.aggregate(a=Avg("rating"))["a"], "rating_count": reviews.count(),
    }


def bookings_panel():
    today = timezone.localdate()
    confirmed = Order.objects.filter(status=Order.Status.CONFIRMED)
    upcoming = (confirmed.filter(start_date__gte=today).select_related("customer", "recommendation__robot_model")
                .order_by("start_date", "-total")[:5])
    return {
        "to_review": confirmed.filter(review_status=Order.Review.PENDING).count(),
        "follow_up": confirmed.filter(review_status=Order.Review.REJECTED).count(),
        "overdue": confirmed.filter(start_date__lt=today).count(),
        "ships_today": confirmed.filter(start_date=today).count(),
        "ships_tomorrow": confirmed.filter(start_date=today + timedelta(days=1)).count(),
        "out": Order.objects.filter(status__in=OUT_WITH_CUSTOMER).count(),
        "to_collect": Order.objects.filter(status=Order.Status.COMPLETED).count(),
        "cancelled": Order.objects.filter(status=Order.Status.CANCELLED,
                                          created_at__gte=timezone.now() - timedelta(days=WINDOW_DAYS)).count(),
        "upcoming": upcoming,
    }


def support_panel():
    counts = tickets.tab_counts()
    waiting = tickets.ticket_queue("open")
    week_ago = timezone.now() - timedelta(days=7)
    return {
        "to_answer": counts["open"], "in_progress": counts["in_progress"],
        "urgent": sum(1 for t in waiting if t.priority == SupportTicket.Priority.URGENT),
        "drafted": SupportTicket.objects.exclude(status=SupportTicket.Status.DRAFT).exclude(reply_draft="").count(),
        "resolved_week": SupportTicket.objects.filter(status__in=[SupportTicket.Status.RESOLVED, SupportTicket.Status.CLOSED],
                                                      updated_at__gte=week_ago).count(),
        "oldest": tickets.waiting_label(min(waiting, key=lambda t: t.submitted_at)) if waiting else None,
        "next": [(t, tickets.waiting_label(t)) for t in waiting[:3]],
    }
