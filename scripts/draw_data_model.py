"""Draw the data model as a UML class diagram: docs/data_model_uml.svg (+ .png via headless Edge/Chrome).

    python scripts/draw_data_model.py

Layout is by hand (fixed columns, orthogonal edges with explicit waypoints), so it stays readable
on one page. If a model changes, edit CLASSES below and re-run.
"""
import shutil
import subprocess
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_SVG = ROOT / "docs" / "data_model_uml.svg"
OUT_PNG = ROOT / "docs" / "data_model_uml.png"

# ---- look ------------------------------------------------------------------------------------
FONT = "Segoe UI, Arial, sans-serif"
FS = 12.5          # attribute font size
LH = 16            # attribute line height
HEAD = 28          # class name band
PAD = 6
W = 240            # class box width
COLS = [40, 350, 660, 970, 1280]
CANVAS_W = 1570
APPS = {  # header fill, legend label
    "auth": ("#e6e6e6", "Django auth"),
    "accounts": ("#dbe8f7", "accounts"),
    "planner": ("#e3f1dc", "planner (ML recommendation)"),
    "catalog": ("#fdebd3", "catalog"),
    "orders": ("#efe2f5", "orders"),
    "support": ("#fbe0e0", "support"),
}
INK, MUTED, LINE = "#1f2328", "#57606a", "#4a4f55"

# ---- content: name -> (app, attributes, methods, stereotype) -----------------------------------
CLASSES = {
    "User": ("auth", ["username : str", "email : str", "first_name, last_name : str",
                      "is_staff : bool", "is_active : bool"], [], "Django built-in"),
    "CustomerProfile": ("accounts", ["phone : str", "postal_code : str", "housing_type : HousingType",
                                     "household_size : int", "created_at : datetime"], [], None),
    "Address": ("accounts", ["label : str", "line, unit : str", "postal_code : str  {6 digits}",
                             "is_default : bool"], ["one_line() : str"], None),
    "TaskRequest": ("planner", ["description : text", "category_hint : TaskCategory [0..1]",
                                "floor_plan : Image", "keep_out_zones : JSON",
                                "housing_type, floor_type : str", "area_m2 : decimal", "num_rooms : int",
                                "has_stairs, is_outdoor, has_pets,", "   has_children, fragile_items : bool",
                                "payload_kg, budget_sgd : decimal", "start_date, deadline_date : date",
                                "hours_per_day : int", "quiet_hours : str", "status : RequestStatus"],
                    ["duration_days() : int"], None),
    "TaskSpec": ("planner", ["task_category : TaskCategory", "category_confidence : float", "subtasks : JSON",
                             "edge_cases : JSON", "est_robot_hours : float", "est_days_needed : int",
                             "feasible_in_time : bool", "within_budget : bool"], [], None),
    "Recommendation": ("planner", ["source : Source", "predicted_platform : Platform",
                                   "platform_confidence : float", "policy_conditioning : JSON",
                                   "quoted_price : decimal", "price_breakdown : JSON", "is_selected : bool"],
                       [], None),
    "RobotModel": ("catalog", ["name, slug : str", "platform : Platform", "manufacturer : str",
                               "daily_rate : decimal", "indoor, outdoor : bool", "can_climb_stairs : bool",
                               "max_payload_kg : decimal", "battery_hours : decimal", "noise_db : int",
                               "task_categories : str  (CSV)", "image : Image", "is_active : bool"],
                   ["category_list() : list", "available_units() : int"], None),
    "AddOn": ("catalog", ["code : str  {unique}", "name : str", "daily_rate : decimal",
                          "compatible_platforms : str  (CSV)", "is_active : bool"],
              ["fits(platform) : bool"], None),
    "SkillPack": ("catalog", ["code : str  {unique}", "name, version : str", "summary : str",
                              "flat_fee : decimal", "task_categories : str  (CSV)",
                              "default_conditioning : JSON", "is_active : bool"], [], None),
    "FleetUnit": ("catalog", ["serial_number : str  {unique}", "status : UnitStatus", "depot : str",
                              "last_serviced : date", "notes : text"], [], None),
    "Order": ("orders", ["status : OrderStatus", "start_date, end_date : date", "delivery_address : str",
                         "subtotal, discount, total : decimal", "created_at : datetime",
                         "review_status : ReviewStatus", "review_note : text", "reviewed_by : User [0..1]",
                         "reviewed_at : datetime"], [], None),
    "OrderItem": ("orders", ["kind : ItemKind", "description : str", "quantity : int  (days)",
                             "unit_price : decimal"], ["line_total() : decimal"], None),
    "OrderStatusEvent": ("orders", ["status : OrderStatus", "note : str", "created_by : User [0..1]",
                                    "created_at : datetime"], [], None),
    "Payment": ("orders", ["method : str", "amount : decimal", "status : PaymentStatus", "reference : str",
                           "paid_at : datetime"], [], None),
    "PromoCode": ("orders", ["code : str  {unique}", "percent_off : int", "valid_until : date [0..1]",
                             "is_active : bool"], [], None),
    "Review": ("support", ["rating : int  {1..5}", "comment : text", "is_visible : bool",
                           "robot_model : RobotModel", "skill_pack : SkillPack [0..1]", "created_at : datetime"],
               [], None),
    "SupportTicket": ("support", ["subject : str", "category : TicketCategory", "description : text",
                                  "status : TicketStatus", "priority : Priority", "submitted_at : datetime",
                                  "reply_draft : text  (staff only)"], [], None),
    "TicketMessage": ("support", ["author : User", "body : text", "created_at : datetime"], [], None),
}

ENUMS = [
    ("OrderStatus", "pending_payment | confirmed | dispatched | on_site | running |"),
    ("", "      completed | collected | cancelled"),
    ("ReviewStatus", "pending | approved | rejected"),
    ("UnitStatus", "available | reserved | deployed | maintenance | retired"),
    ("Source", "ml | customer | staff"),
    ("ItemKind", "robot | addon | skill_pack | service"),
    ("PaymentStatus", "pending | paid | refunded"),
    ("TicketStatus", "draft | open | in_progress | resolved | closed"),
    ("TicketCategory", "robot | safety | schedule | billing | other"),
    ("Priority", "low | normal | urgent"),
    ("RequestStatus", "draft | planned | booked"),
    ("HousingType", "hdb | condo | landed | shophouse"),
    ("TaskCategory, Platform", "8 values each, fixed in catalog/taxonomy.py"),
]


def height(name):
    _, attrs, methods, stereo = CLASSES[name]
    h = HEAD + (12 if stereo else 0) + PAD * 2 + len(attrs) * LH
    if methods:
        h += PAD * 2 + len(methods) * LH
    return h


class Box:
    def __init__(self, name, col, y):
        self.name, self.x, self.y, self.w, self.h = name, COLS[col], y, W, height(name)

    @property
    def r(self): return self.x + self.w

    @property
    def b(self): return self.y + self.h

    @property
    def cx(self): return self.x + self.w / 2


B = {}


def place(name, col, y):
    B[name] = Box(name, col, y)
    return B[name]


# ---- layout ------------------------------------------------------------------------------------
TOP, GAP = 100, 52
place("CustomerProfile", 0, TOP)
place("User", 0, B["CustomerProfile"].b + GAP)
place("Address", 0, B["User"].b + GAP)
place("TaskRequest", 1, TOP)
place("TaskSpec", 2, TOP)
place("Recommendation", 2, B["TaskSpec"].b + 44)
place("RobotModel", 3, TOP)
place("AddOn", 3, B["RobotModel"].b + GAP)
place("SkillPack", 4, TOP)
place("FleetUnit", 4, B["SkillPack"].b + 46)

ROW2 = max(b.b for b in B.values()) + 70
place("SupportTicket", 0, ROW2)
place("TicketMessage", 0, B["SupportTicket"].b + GAP)
place("Payment", 1, ROW2)
place("OrderStatusEvent", 1, B["Payment"].b + 44)
place("Order", 2, ROW2)
place("PromoCode", 2, B["Order"].b + GAP)
place("OrderItem", 3, ROW2)
place("Review", 3, B["OrderItem"].b + GAP + 10)

rec, add = B["Recommendation"], B["AddOn"]
assert add.y + 16 < rec.b, "Recommendation and AddOn need to overlap vertically for their edge"

# ---- edges ---------------------------------------------------------------------------------------
# (points, end labels (first, last), composition at first point?, middle label)
EDGES = []


def edge(points, m1, m2, comp=False, label=None, label_at=None, side1=1, side2=-1):
    EDGES.append(dict(points=points, m=(m1, m2), comp=comp, label=label, label_at=label_at,
                      side=(side1, side2)))


u, cp, ad, tr, ts = B["User"], B["CustomerProfile"], B["Address"], B["TaskRequest"], B["TaskSpec"]
rm, sp, fu = B["RobotModel"], B["SkillPack"], B["FleetUnit"]
o, oi, ose, pay, pc = B["Order"], B["OrderItem"], B["OrderStatusEvent"], B["Payment"], B["PromoCode"]
rv, st, tm = B["Review"], B["SupportTicket"], B["TicketMessage"]
CH = 25  # channel offset from a box edge

# accounts
edge([(u.cx, u.y), (cp.cx, cp.b)], "1", "0..1", comp=True)
edge([(u.cx, u.b), (ad.cx, ad.b - ad.h)], "1", "*", comp=True)
y = u.y + 40
edge([(u.r, y), (tr.x, y)], "1", "*")
y = ad.y + 18
edge([(ad.r, y), (ad.r + CH, y), (ad.r + CH, tr.b - 14), (tr.x, tr.b - 14)], "0..1", "*")

# planner
y = ts.y + 60
edge([(tr.r, y), (ts.x, y)], "1", "0..1", comp=True)
y = rec.y + 60
edge([(tr.r, y), (rec.x, y)], "1", "*", comp=True)
edge([(rec.r, rec.y + 40), (rm.x, rec.y + 40)], "*", "0..1")
edge([(rec.r, rec.y + 14), (rec.r + CH, rec.y + 14), (rec.r + CH, TOP - 22), (sp.cx, TOP - 22), (sp.cx, sp.y)],
     "*", "0..1", side2=1)
y = (add.y + rec.b) / 2
edge([(rec.r, y), (add.x, y)], "*", "*")

# catalog
y = sp.y + 70
edge([(sp.x, y), (rm.r, y)], "*", "*")
y = fu.y + 40
edge([(rm.r, y), (fu.x, y)], "1", "*")

# orders
edge([(rec.cx, rec.b), (o.cx, o.y)], "0..1", "*")
edge([(o.x, o.y + 40), (pay.r, o.y + 40)], "1", "0..1", comp=True)
y = (ose.y + o.b) / 2
edge([(o.x, y), (ose.r, y)], "1", "*", comp=True)
edge([(o.cx, o.b), (pc.cx, pc.y)], "*", "0..1")
y = oi.y + 30
edge([(o.r, y), (oi.x, y)], "1", "*", comp=True)
edge([(add.cx, add.b), (oi.cx, oi.y)], "0..1", "*")
y = oi.y + 22
edge([(oi.r, y), (oi.r + CH, y), (oi.r + CH, rm.b - 14), (rm.r, rm.b - 14)], "*", "0..1", side1=-1, side2=1)
y = oi.y + 52
edge([(oi.r, y), (fu.cx, y), (fu.cx, fu.b)], "*", "0..1", label="assigned unit", label_at=1.5, side1=-1, side2=1)
y = oi.y + 86
edge([(oi.r, y), (CANVAS_W - 25, y), (CANVAS_W - 25, sp.y + 110), (sp.r, sp.y + 110)], "*", "0..1",
     side1=-1, side2=1)
y = rv.y + 20
edge([(o.r, y), (rv.x, y)], "1", "0..1", comp=True)

# customer links into row 2 (down the left margin)
gy = ROW2 - 30
edge([(u.x, u.y + 70), (22, u.y + 70), (22, gy), (o.x + 40, gy), (o.x + 40, o.y)], "1", "*",
     label="customer", label_at=3.3)
edge([(u.x, u.y + 90), (12, u.y + 90), (12, st.y + 30), (st.x, st.y + 30)], "1", "*", side1=-1, side2=1)

# support
y = (pay.b + ose.y) / 2
edge([(o.x, y), (st.r, y)], "0..1", "*")
edge([(st.cx, st.b), (tm.cx, tm.y)], "1", "*", comp=True)


# ---- render ------------------------------------------------------------------------------------
def t(x, y, s, size=FS, weight="normal", anchor="start", fill=INK, italic=False):
    st_ = ' font-style="italic"' if italic else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}" fill="{fill}"{st_}>{escape(s)}</text>')


def draw_box(b):
    app, attrs, methods, stereo = CLASSES[b.name]
    fill = APPS[app][0]
    out = [f'<rect x="{b.x}" y="{b.y}" width="{b.w}" height="{b.h}" fill="#fff" stroke="{LINE}" stroke-width="1.2"/>']
    head_h = HEAD + (12 if stereo else 0)
    out.append(f'<rect x="{b.x}" y="{b.y}" width="{b.w}" height="{head_h}" fill="{fill}" stroke="{LINE}" stroke-width="1.2"/>')
    if stereo:
        out.append(t(b.cx, b.y + 14, f"«{stereo}»", size=10.5, anchor="middle", fill=MUTED))
    out.append(t(b.cx, b.y + head_h - 9, b.name, size=14, weight="bold", anchor="middle"))
    y = b.y + head_h + PAD + LH - 4
    for a in attrs:
        out.append(t(b.x + 8, y, a))
        y += LH
    if methods:
        sep = y - LH + 4 + PAD
        out.append(f'<line x1="{b.x}" y1="{sep}" x2="{b.r}" y2="{sep}" stroke="{LINE}" stroke-width="1"/>')
        y = sep + PAD + LH - 4
        for m in methods:
            out.append(t(b.x + 8, y, m))
            y += LH
    return "\n".join(out)


def unit(p, q):
    dx, dy = q[0] - p[0], q[1] - p[1]
    n = (dx * dx + dy * dy) ** 0.5 or 1
    return dx / n, dy / n


def end_label(p, q, text, comp, side):
    dx, dy = unit(p, q)
    along = 24 if comp else 13
    nx, ny = (0, -1) if abs(dx) > abs(dy) else (1, 0)  # above horizontal lines, right of vertical ones
    off = 9 * side
    x, y = p[0] + dx * along + nx * off, p[1] + dy * along + ny * off
    anchor = "middle"
    if abs(dy) > abs(dx):
        anchor = "start" if side > 0 else "end"
        x += 0 if side > 0 else 0
    return t(x, y + 4, text, size=11.5, anchor=anchor, fill=INK)


def draw_edge(e):
    pts = e["points"]
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    marker = ' marker-start="url(#diamond)"' if e["comp"] else ""
    out = [f'<polyline points="{d}" fill="none" stroke="{LINE}" stroke-width="1.3"{marker}/>']
    out.append(end_label(pts[0], pts[1], e["m"][0], e["comp"], e["side"][0]))
    out.append(end_label(pts[-1], pts[-2], e["m"][1], False, e["side"][1]))
    if e["label"]:
        k = e["label_at"]  # segment index + fraction
        i = int(k)
        f = k - i
        (x1, y1), (x2, y2) = pts[i], pts[i + 1]
        x, y = x1 + (x2 - x1) * f, y1 + (y2 - y1) * f
        if abs(y2 - y1) < 1:  # horizontal: below the line
            out.append(t(x, y + 14, e["label"], size=11, anchor="middle", fill=MUTED, italic=True))
        else:
            out.append(t(x + 5, y, e["label"], size=11, anchor="start", fill=MUTED, italic=True))
    return "\n".join(out)


def legend_and_enums(y0):
    out = []
    x0, w = COLS[0], COLS[4] + W - COLS[0]
    out.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{CANVAS_H - y0 - 20}" fill="#fafbfc" stroke="#d0d7de"/>')
    # legend column
    lx, ly = x0 + 14, y0 + 22
    out.append(t(lx, ly, "Legend", size=13, weight="bold"))
    ly += 20
    for app, (fill, label) in APPS.items():
        out.append(f'<rect x="{lx}" y="{ly - 11}" width="14" height="14" fill="{fill}" stroke="{LINE}" stroke-width="0.8"/>')
        out.append(t(lx + 22, ly, label, size=11.5))
        ly += 18
    ly += 4
    out.append(f'<polyline points="{lx},{ly - 4} {lx + 40},{ly - 4}" stroke="{LINE}" stroke-width="1.3" marker-start="url(#diamond)"/>')
    out.append(t(lx + 48, ly, "composition: part is deleted with its owner", size=11.5))
    ly += 18
    out.append(f'<line x1="{lx}" y1="{ly - 4}" x2="{lx + 40}" y2="{ly - 4}" stroke="{LINE}" stroke-width="1.3"/>')
    out.append(t(lx + 48, ly, "association (foreign key), with multiplicities", size=11.5))
    ly += 18
    for s in ["Every class also has an integer id (PK), not shown.",
              "An attribute typed with a class (e.g. reviewed_by : User)",
              "   is a foreign key whose line is left out for readability.",
              "OrderItem references exactly one of robot / add-on / skill pack."]:
        out.append(t(lx, ly, s, size=11.5, fill=MUTED))
        ly += 16
    # enums, two columns
    ex = x0 + 420
    out.append(t(ex, y0 + 22, "Enumerations (Django TextChoices)", size=13, weight="bold"))
    half = (len(ENUMS) + 1) // 2
    for i, (name, vals) in enumerate(ENUMS):
        col, row = divmod(i, half)
        x = ex + col * 560
        y = y0 + 42 + row * 18
        out.append(f'<text x="{x}" y="{y}" font-size="11.5" fill="{INK}"><tspan font-weight="bold">{escape(name)}</tspan>'
                   f'<tspan fill="{MUTED}">{": " if name else ""}{escape(vals)}</tspan></text>')
    return "\n".join(out)


ENUM_Y = max(b.b for b in B.values()) + 40
CANVAS_H = ENUM_Y + 265

svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" '
       f'viewBox="0 0 {CANVAS_W} {CANVAS_H}" font-family="{FONT}">',
       '<defs><marker id="diamond" viewBox="0 0 20 10" refX="0" refY="5" markerWidth="20" markerHeight="10" '
       f'markerUnits="userSpaceOnUse" orient="auto"><path d="M0,5 L10,0 L20,5 L10,10 z" fill="{LINE}"/></marker></defs>',
       f'<rect width="100%" height="100%" fill="#fff"/>',
       t(COLS[0], 42, "Botcierge data model", size=22, weight="bold"),
       t(COLS[0], 66, "UML class diagram of the Django models (accounts, planner, catalog, orders, support)",
         size=13, fill=MUTED)]
svg += [draw_edge(e) for e in EDGES]
svg += [draw_box(b) for b in B.values()]
svg.append(legend_and_enums(ENUM_Y))
svg.append("</svg>")
OUT_SVG.write_text("\n".join(svg), encoding="utf-8")
print(f"wrote {OUT_SVG} ({CANVAS_W}x{CANVAS_H})")

# ---- PNG through a headless browser (Edge ships with Windows) -----------------------------------
browser = next((p for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                            shutil.which("msedge"), shutil.which("chrome")] if p and Path(p).exists()), None)
if browser:
    html = OUT_SVG.with_suffix(".html")
    html.write_text(f'<html><body style="margin:0">{OUT_SVG.read_text(encoding="utf-8")}</body></html>',
                    encoding="utf-8")
    subprocess.run([browser, "--headless", "--disable-gpu", "--hide-scrollbars", f"--screenshot={OUT_PNG}",
                    f"--window-size={CANVAS_W},{CANVAS_H}", "--force-device-scale-factor=2", html.as_uri()],
                   check=True, capture_output=True)
    html.unlink()
    print(f"wrote {OUT_PNG} ({CANVAS_W * 2}x{CANVAS_H * 2})")
else:
    print("no Edge/Chrome found: open the SVG in a browser or draw.io and export PNG")
