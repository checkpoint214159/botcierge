"""Quote rules shared by the planner (S07), the booking page (S08/S09) and checkout (S10).

Delivery is priced by zone. The first two digits of a Singapore postal code are the postal
sector, and sectors group into districts. We bucket districts into four zones by distance from
our depot in Jurong West, so no outside map service is needed.
"""
from decimal import Decimal

DEPOT = "Jurong West"

ZONE_FEES = {
    "west": Decimal("29.00"),
    "north": Decimal("45.00"),
    "central": Decimal("49.00"),
    "east": Decimal("69.00"),
}
ZONE_LABELS = {"west": "West", "north": "North", "central": "Central", "east": "East"}

# postal sectors (first two digits) per zone; sector 74 and 83-99 are not used in Singapore
_ZONE_SECTORS = {
    # D05 Clementi/West Coast, D21 Upper Bukit Timah, D22 Jurong, D23 Bukit Batok/CCK, D24 Tengah
    "west": [11, 12, 13, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71],
    # D25 Woodlands, D26 Upper Thomson, D27 Yishun/Sembawang, D28 Seletar
    "north": [72, 73, 75, 76, 77, 78, 79, 80],
    # D14 Geylang, D15 Katong, D16 Bedok, D17 Changi, D18 Tampines/Pasir Ris, D19 Serangoon/Punggol
    "east": [38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 81, 82],
    # D01-D04, D06-D13, D20: city, Orchard, Bukit Timah, Toa Payoh, Bishan/AMK
    "central": [*range(1, 11), *range(14, 38), 56, 57],
}
SECTOR_ZONE = {sector: zone for zone, sectors in _ZONE_SECTORS.items() for sector in sectors}


def zone_for(postal_code: str | None) -> str | None:
    """'west' / 'north' / 'central' / 'east', or None if the code is not a Singapore postal code."""
    if not postal_code or len(postal_code) != 6 or not postal_code.isdigit():
        return None
    return SECTOR_ZONE.get(int(postal_code[:2]))


def build_quote(robot, addons, skill_pack, rental_days: int, postal_code: str | None = None):
    """Price a setup. Delivery is only included once we know where it goes (a valid postal code).

    Returns (total, breakdown). The breakdown is stored on the Recommendation as JSON.
    """
    breakdown = {"rental_days": rental_days}
    total = Decimal("0.00")
    if robot:
        breakdown["robot"] = float(robot.daily_rate * rental_days)
        total += robot.daily_rate * rental_days
    for a in addons:
        breakdown[f"addon:{a.code}"] = float(a.daily_rate * rental_days)
        total += a.daily_rate * rental_days
    if skill_pack:
        breakdown["skill_pack"] = float(skill_pack.flat_fee)
        total += skill_pack.flat_fee
    zone = zone_for(postal_code)
    if zone:
        breakdown["delivery_and_setup"] = float(ZONE_FEES[zone])
        breakdown["delivery_zone"] = zone
        total += ZONE_FEES[zone]
    return total, breakdown


def quote_lines(breakdown: dict, robot, addons, skill_pack) -> list[tuple[str, float | None]]:
    """Human-readable lines for a breakdown. An amount of None means "not priced yet"."""
    days = breakdown.get("rental_days", 1)
    lines = []
    if robot:
        lines.append((f"{robot.name} × {days} day{'s' if days != 1 else ''}", breakdown.get("robot", 0)))
    for a in addons:
        lines.append((f"{a.name} × {days} day{'s' if days != 1 else ''}", breakdown.get(f"addon:{a.code}", 0)))
    if skill_pack:
        lines.append((f"{skill_pack.name} skill pack", breakdown.get("skill_pack", 0)))
    if "delivery_and_setup" in breakdown:
        zone = ZONE_LABELS.get(breakdown.get("delivery_zone"))  # plans made before zones have none
        label = f"Delivery, setup and collection ({zone} zone)" if zone else "Delivery, setup and collection"
        lines.append((label, breakdown["delivery_and_setup"]))
    else:
        low, high = min(ZONE_FEES.values()), max(ZONE_FEES.values())
        lines.append((f"Delivery: set when you choose an address (S${low:.0f} to S${high:.0f})", None))
    return lines


def rec_quote_lines(rec) -> list[tuple[str, float | None]]:
    return quote_lines(rec.price_breakdown, rec.robot_model, list(rec.addons.all()), rec.skill_pack)
