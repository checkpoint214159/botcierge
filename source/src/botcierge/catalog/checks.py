"""Catalogue sync checks for the staff panel (A03-A05 and the ML models page).

The catalogue is edited in four places (robots, fleet, add-ons, skill packs) but they depend on each
other: a skill pack needs a robot that can run it, a robot needs units, a task type needs a robot.
This module finds the gaps so staff see them in one list instead of finding out from a customer.
Each issue is a dict: {"area": "robots"|"fleet"|"addons"|"skill_packs", "level": "danger"|"warning",
"text": ..., "obj": the row (or None)}.
"""
from .models import AddOn, FleetUnit, RobotModel, SkillPack
from .taxonomy import TASK_CATEGORY_CHOICES

CATEGORY_LABELS = dict(TASK_CATEGORY_CHOICES)
UNBOOKABLE = [FleetUnit.Status.MAINTENANCE, FleetUnit.Status.RETIRED]


def _issue(area, level, text, obj=None):
    return {"area": area, "level": level, "text": text, "obj": obj}


def catalogue_issues(area: str | None = None) -> list[dict]:
    robots = list(RobotModel.objects.filter(is_active=True).prefetch_related("units"))
    live_platforms = {r.platform for r in robots}
    issues = []

    # task types no active robot is marked for: customers can plan them but never book them
    for code, label in TASK_CATEGORY_CHOICES:
        if not any(code in r.category_list for r in robots):
            issues.append(_issue("robots", "danger", f"No active robot is marked for {label.lower()}."))

    for r in robots:
        bookable = [u for u in r.units.all() if u.status not in UNBOOKABLE]
        if not bookable:
            issues.append(_issue("fleet", "danger", f"{r.name} is listed but has no bookable units.", r))

    for a in AddOn.objects.filter(is_active=True):
        if a.platform_list and not live_platforms & set(a.platform_list):
            issues.append(_issue("addons", "warning", f"{a.name} only fits platforms with no active robot.", a))

    for sp in SkillPack.objects.filter(is_active=True).prefetch_related("compatible_robots"):
        active = [r for r in sp.compatible_robots.all() if r.is_active]
        if not sp.category_list:
            issues.append(_issue("skill_packs", "danger",
                                 f"{sp.name} has no task types, so it is never offered.", sp))
        if not active:
            issues.append(_issue("skill_packs", "danger", f"{sp.name} has no active robot that can run it.", sp))
            continue
        # a robot listed for the pack should be bookable for at least one of the pack's task types;
        # fix it either way: remove the robot from the pack, or add the task type to the robot
        odd = [r for r in active if not set(r.category_list) & set(sp.category_list)]
        if odd and sp.category_list:
            names = ", ".join(r.name for r in odd)
            issues.append(_issue("skill_packs", "warning",
                                 f"{sp.name} lists {names}, which can't be booked for its task types "
                                 f"(remove it here, or add the task type to the robot).", sp))

    return [i for i in issues if area is None or i["area"] == area]
