"""Map editor. Run with: python map_editor.py

Start menu: "New Map", or pick an existing map from the scrollable list. The toggle switches the
list between tutorial levels and main levels (new maps are created for the mode currently shown).

Editor:
- Move the mouse to the very bottom of the window to pull up the object drawer. Tabs along its
  bottom edge: Walls, Triggers, Enemies, Logic. Click an object, then click the canvas to place it.
- Drag objects to move them; drag the yellow handles of the selected object to resize it.
- Right-click any object (or the Delete key while hovering) for its properties menu: Duplicate, Delete,
  Connect and the object's own settings. Number rows use the [-] / [+] boxes; text rows are typed in.
- Connect: click objects to link/unlink them, click empty space or press Esc to finish. A source
  (trigger, enemy spawn point, logic gate) enables/feeds everything it is linked to.
- Triggers carry a "fulfilled" flag and a mode: Latch (stays active once the requirement is met) or
  Pulse (active for a configurable number of ticks).
- Level End objects configure the tutorial completion delay in ticks (default 150).
- Logic objects (text, level end, gates) are editor-only helpers and are not shown in normal gameplay.
- Save writes Background/map_presets/<name>.json. The file keeps the legacy fields (rect walls,
  spawn zones, movement triggers, enemy markers) that the game already reads, plus the full
  "editor_objects" list the editor itself round-trips.
"""

import copy
import json
import math
import os
import re

import pygame

from Background.maps import (
    MAPS_DIR,
    DEFAULT_SPAWNING,
    DEFAULT_GOAL_RADIUS,
    DEFAULT_LEVEL_END_DELAY_TICKS,
    ENEMY_TYPES,
    CARDS_PER_LEVEL,
    MAX_LEVELS,
    ICON_SIZE,
    ICON_PALETTE,
    legacy_objects,
    level_requirement,
    list_map_files,
    sanitize_icon,
    sanitize_levels,
    sanitize_waves,
)
from Background.run_stats import CANONICAL_GUN_NAMES, CANONICAL_PLAYER_NAMES
from Background.upgrades import total_Upgrades

BODY_NAMES = tuple(CANONICAL_PLAYER_NAMES.values())
GUN_NAMES = tuple(CANONICAL_GUN_NAMES.values())
ICON_CELL = 22
TEXT_LIMITS = {"description": 300}

CANVAS_W, CANVAS_H = 1000, 625
TOP_H = 36
WIN_W, WIN_H = CANVAS_W, CANVAS_H + TOP_H
DRAWER_H, TAB_H, EDGE_ZONE, DRAWER_MARGIN = 150, 32, 6, 24
HANDLE = 9
MIN_SIZE = 10
PLAYER_RADIUS = 20
POINT_RADIUS = 14
GATE_W, GATE_H = 64, 36
ROW_H, POPUP_W = 28, 240
GATES = ("AND", "OR", "NOT", "NAND", "NOR", "XOR", "XNOR")

BG = (4, 16, 42)
PANEL = (25, 28, 40)
BTN = (60, 66, 90)
BTN_HOVER = (90, 96, 125)
TEXT = (240, 240, 240)
DIM = (180, 185, 210)
GOLD = (255, 210, 90)
LINK_COLOR = (255, 215, 60)

# type -> (shape, label, fill, edge)
TYPES = {
    "wall_rect": ("rect", "Rect Wall", (70, 75, 95), (170, 175, 200)),
    "wall_tri": ("tri", "Triangle Wall", (70, 75, 95), (170, 175, 200)),
    "wall_circle": ("circle", "Circle Wall", (70, 75, 95), (170, 175, 200)),
    "trig_move": ("circle", "Movement Trigger", (30, 110, 70), (60, 200, 120)),
    "trig_attack": ("circle", "Attack Trigger", (120, 45, 40), (240, 100, 80)),
    "trig_ability": ("circle", "Ability Trigger", (80, 50, 130), (170, 120, 255)),
    "spawn_zone": ("rect", "Enemy Spawn Zone", (150, 40, 40), (255, 110, 110)),
    "spawn_point": ("point", "Enemy Spawn Point", (230, 120, 40), (255, 230, 200)),
    "kill_zone": ("rect", "Enemy Kill Zone", (70, 20, 90), (200, 80, 255)),
    "text": ("text", "Text", (0, 0, 0), (230, 230, 230)),
    "level_end": ("circle", "Level End", (40, 60, 90), (120, 200, 255)),
    "gate": ("gate", "Gate", (50, 55, 80), (200, 205, 240)),
    "wave_trigger": ("gate", "Wave Beaten", (60, 50, 20), (255, 190, 80)),
    "level_trigger": ("gate", "Level Reached", (20, 60, 60), (90, 230, 220)),
    "exp_spawner": ("point", "Exp Spawner", (110, 100, 20), (255, 240, 90)),
}
SHAPES = {k: v[0] for k, v in TYPES.items()}
TRIGGERS = ("trig_move", "trig_attack", "trig_ability")
SOURCES = TRIGGERS + ("spawn_point", "gate", "wave_trigger", "level_trigger")
GEOM_KEYS = ("x1", "y1", "x2", "y2", "x", "y", "r", "pts")
DEFAULT_HALF = {"wall_rect": (60, 15), "spawn_zone": (80, 50), "kill_zone": (60, 40)}
DEFAULT_RADIUS = {
    "wall_circle": 30,
    "trig_move": DEFAULT_GOAL_RADIUS,
    "trig_attack": DEFAULT_GOAL_RADIUS,
    "trig_ability": DEFAULT_GOAL_RADIUS,
    "level_end": 30,
}

# (tab, [(button label, type, extra properties)])
TABS = [
    (
        "Walls",
        [
            ("Rect Wall", "wall_rect", {}),
            ("Triangle Wall", "wall_tri", {}),
            ("Circle Wall", "wall_circle", {}),
        ],
    ),
    (
        "Triggers",
        [
            ("Movement", "trig_move", {}),
            ("Attack", "trig_attack", {}),
            ("Player Ability", "trig_ability", {}),
        ],
    ),
    (
        "Enemies",
        [
            ("Spawn Zone", "spawn_zone", {}),
            ("Spawn Point", "spawn_point", {}),
            ("Kill Zone", "kill_zone", {}),
            ("Exp Spawner", "exp_spawner", {}),
        ],
    ),
    (
        "Logic",
        [
            ("Text", "text", {}),
            ("Level End", "level_end", {}),
            ("Wave Beaten", "wave_trigger", {}),
            ("Level Reached", "level_trigger", {}),
        ]
        + [(g, "gate", {"gate": g}) for g in GATES],
    ),
]

_fonts = {}


def get_font(size):
    if size not in _fonts:
        _fonts[size] = pygame.font.SysFont(None, size)
    return _fonts[size]


def text_size(o):
    return get_font(int(o.get("size", 28))).size(o.get("text") or " ")


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class Editor:
    def __init__(self, tutorial_mode=False):
        self.player = [CANVAS_W / 2, CANVAS_H / 2]
        self.objects = []
        self.next_id = 1
        self.meta = {"name": "new_map"}
        self.tutorial = {"active": tutorial_mode, "outer_wall_exp": True}
        self.selected = None
        self.drag = None
        self.popup = None  # {"pos": (x, y), "obj": o}
        self.connecting = None
        self.placing = None  # (type, extras)
        self.typing = None  # (dict, key)
        self.status = "Ready"

    # ---- object model ----
    def new_id(self):
        self.next_id += 1
        return self.next_id - 1

    def by_id(self, oid):
        return next((o for o in self.objects if o["id"] == oid), None)

    def make(self, typ, x, y, extras=None):
        shape = SHAPES[typ]
        o = {"id": self.new_id(), "type": typ, "targets": []}
        if shape == "rect":
            hw, hh = DEFAULT_HALF[typ]
            o.update(x1=x - hw, y1=y - hh, x2=x + hw, y2=y + hh)
        elif shape == "circle":
            o.update(x=x, y=y, r=DEFAULT_RADIUS[typ])
        elif shape == "tri":
            o["pts"] = [[x, y - 30], [x - 35, y + 25], [x + 35, y + 25]]
        else:
            o.update(x=x, y=y)
        if typ in TRIGGERS:
            o.update(mode="latch", pulse_ticks=30, fulfilled=False)
            if typ != "trig_move":
                o["count"] = 1
        elif typ == "spawn_point":
            o.update(enemy=ENEMY_TYPES[0], mode="latch", pulse_ticks=30)
        elif typ == "text":
            o.update(text="Text", size=28)
        elif typ == "gate":
            o["gate"] = "AND"
        elif typ == "wave_trigger":
            o["wave"] = 1
        elif typ == "level_trigger":
            o["level"] = 2
        elif typ == "exp_spawner":
            o.update(amount=5, count=1)
        elif typ == "level_end":
            o["delay_ticks"] = DEFAULT_LEVEL_END_DELAY_TICKS
        o.update(extras or {})
        self.fit(o)
        self.objects.append(o)
        return o

    @staticmethod
    def bounds(o):
        shape = SHAPES[o["type"]]
        if shape == "rect":
            return o["x1"], o["y1"], o["x2"], o["y2"]
        if shape == "circle":
            return o["x"] - o["r"], o["y"] - o["r"], o["x"] + o["r"], o["y"] + o["r"]
        if shape == "tri":
            xs, ys = [p[0] for p in o["pts"]], [p[1] for p in o["pts"]]
            return min(xs), min(ys), max(xs), max(ys)
        if shape == "text":
            w, h = text_size(o)
        elif shape == "gate":
            w, h = GATE_W, GATE_H
        else:
            w = h = POINT_RADIUS * 2
        return o["x"] - w / 2, o["y"] - h / 2, o["x"] + w / 2, o["y"] + h / 2

    def center(self, o):
        x1, y1, x2, y2 = self.bounds(o)
        return (x1 + x2) / 2, (y1 + y2) / 2

    @staticmethod
    def translate(o, dx, dy):
        shape = SHAPES[o["type"]]
        if shape == "rect":
            o["x1"] += dx
            o["x2"] += dx
            o["y1"] += dy
            o["y2"] += dy
        elif shape == "tri":
            for p in o["pts"]:
                p[0] += dx
                p[1] += dy
        else:
            o["x"] += dx
            o["y"] += dy

    def fit(self, o):
        x1, y1, x2, y2 = self.bounds(o)
        dx = max(0, -x1) - max(0, x2 - CANVAS_W)
        dy = max(0, -y1) - max(0, y2 - CANVAS_H)
        self.translate(o, dx, dy)

    def hit(self, o, x, y):
        shape = SHAPES[o["type"]]
        if shape == "circle":
            return (x - o["x"]) ** 2 + (y - o["y"]) ** 2 <= o["r"] ** 2
        if shape == "tri":
            (ax, ay), (bx, by), (cx, cy) = o["pts"]
            d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            if d == 0:
                return False
            u = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / d
            v = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / d
            return u >= 0 and v >= 0 and u + v <= 1
        x1, y1, x2, y2 = self.bounds(o)
        return x1 <= x <= x2 and y1 <= y <= y2

    def object_at(self, x, y):
        for o in reversed(self.objects):
            if self.hit(o, x, y):
                return o
        return None

    def handles(self, o):
        shape = SHAPES[o["type"]]
        if shape == "rect":
            return [
                (o["x1"], o["y1"]),
                (o["x2"], o["y1"]),
                (o["x2"], o["y2"]),
                (o["x1"], o["y2"]),
            ]
        if shape == "tri":
            return [tuple(p) for p in o["pts"]]
        if shape == "circle":
            return [(o["x"] + o["r"], o["y"])]
        return []

    def duplicate(self, o):
        copy_o = copy.deepcopy(o)
        copy_o["id"] = self.new_id()
        self.translate(copy_o, 25, 25)
        self.fit(copy_o)
        self.objects.append(copy_o)
        for s in self.objects:
            if o["id"] in s["targets"]:
                s["targets"].append(copy_o["id"])
        self.selected = copy_o
        self.status = "Duplicated"

    def delete(self, o):
        self.objects = [x for x in self.objects if x is not o]
        for x in self.objects:
            x["targets"] = [t for t in x["targets"] if t != o["id"]]
        if self.selected is o:
            self.selected = None
        if self.connecting is o:
            self.connecting = None
        self.status = "Deleted"

    def toggle_link(self, source, target):
        if target is source:
            return
        if target["id"] in source["targets"]:
            source["targets"].remove(target["id"])
        else:
            source["targets"].append(target["id"])

    def rotate_tri(self, o):
        cx, cy = self.center(o)
        o["pts"] = [[cx - (p[1] - cy), cy + (p[0] - cx)] for p in o["pts"]]
        self.fit(o)

    # ---- properties menu ----
    def rows(self, o):
        """(text, kind, a, b) rows. Kinds: act, close (act then close menu), num (a=dec, b=inc), text."""
        t, shape, rows = o["type"], SHAPES[o["type"]], []

        def num(label, get, setter, step, lo=1, hi=9999):
            rows.append(
                (
                    f"{label}: {get()}",
                    "num",
                    lambda: setter(clamp(get() - step, lo, hi)),
                    lambda: setter(clamp(get() + step, lo, hi)),
                )
            )

        def key_num(label, key, step, lo=1, hi=9999):
            num(label, lambda: o[key], lambda v: o.__setitem__(key, v), step, lo, hi)

        def cycle(label, key, choices):
            def go():
                o[key] = choices[(choices.index(o[key]) + 1) % len(choices)]

            rows.append((f"{label}: {o[key]}", "act", go, None))

        def toggle(label, key):
            rows.append(
                (
                    f"{label}: {'Yes' if o[key] else 'No'}",
                    "act",
                    lambda: o.__setitem__(key, not o[key]),
                    None,
                )
            )

        if shape == "rect":

            def set_w(v):
                o["x2"] = min(o["x1"] + v, CANVAS_W)
                o["x1"] = min(o["x1"], o["x2"] - MIN_SIZE)

            def set_h(v):
                o["y2"] = min(o["y1"] + v, CANVAS_H)
                o["y1"] = min(o["y1"], o["y2"] - MIN_SIZE)

            num("Width", lambda: round(o["x2"] - o["x1"]), set_w, 10, MIN_SIZE)
            num("Height", lambda: round(o["y2"] - o["y1"]), set_h, 10, MIN_SIZE)
        if shape == "tri":
            rows.append(("Rotate 90", "act", lambda: self.rotate_tri(o), None))
        if shape == "circle":
            key_num("Radius", "r", 5, 5, 400)
        if t in TRIGGERS:
            toggle("Fulfilled", "fulfilled")
            cycle("Mode", "mode", ("latch", "pulse"))
            if o["mode"] == "pulse":
                key_num("Pulse ticks", "pulse_ticks", 5, 1, 9999)
            if t != "trig_move":
                key_num("Times required", "count", 1, 1, 999)
        if t == "spawn_zone":
            o.setdefault("wave_mode", False)
            toggle("Wave on signal", "wave_mode")
        if t == "spawn_point":
            cycle("Enemy", "enemy", ENEMY_TYPES)
            o.setdefault("mode", "latch")
            o.setdefault("pulse_ticks", 30)
            cycle("Mode", "mode", ("latch", "pulse"))
            if o["mode"] == "pulse":
                key_num("Pulse ticks", "pulse_ticks", 5, 1, 9999)
        if t == "text":
            rows.append(
                (
                    "Text: " + o["text"],
                    "text",
                    lambda: self.begin_typing(o, "text"),
                    None,
                )
            )
            key_num("Size", "size", 4, 10, 120)
        if t == "gate":
            cycle("Gate", "gate", GATES)
        if t == "wave_trigger":
            o.setdefault("wave", 1)
            key_num("Wave beaten", "wave", 1, 1, 99)
        if t == "level_trigger":
            o.setdefault("level", 2)
            key_num("Level reached", "level", 1, 2, 99)
        if t == "exp_spawner":
            o.setdefault("amount", 5)
            o.setdefault("count", 1)
            key_num("Exp per orb", "amount", 5, 1, 9999)
            key_num("Orbs", "count", 1, 1, 99)
        if t == "level_end":
            o.setdefault("delay_ticks", DEFAULT_LEVEL_END_DELAY_TICKS)
            key_num("Delay ticks", "delay_ticks", 5, 0, 9999)
        if t in SOURCES:
            rows.append(("Connect", "close", lambda: self.start_connect(o), None))
        rows.append(("Duplicate", "close", lambda: self.duplicate(o), None))
        rows.append(("Delete", "close", lambda: self.delete(o), None))
        return rows

    def start_connect(self, o):
        self.connecting = o
        self.status = "Linking: click objects, Esc to finish"

    def begin_typing(self, target, key):
        self.typing = (target, key)
        self.popup = None if key == "name" else self.popup

    def popup_rect(self):
        x, y = self.popup["pos"]
        h = ROW_H * len(self.rows(self.popup["obj"]))
        return pygame.Rect(
            clamp(x, 0, WIN_W - POPUP_W), clamp(y, 0, WIN_H - h), POPUP_W, h
        )

    def popup_click(self, sx, sy):
        rect = self.popup_rect()
        if not rect.collidepoint(sx, sy):
            self.popup = None
            return False
        rows = self.rows(self.popup["obj"])
        index = (sy - rect.y) // ROW_H
        text, kind, a, b = rows[index]
        if kind == "num":
            local = sx - rect.x
            if POPUP_W - 56 <= local < POPUP_W - 28:
                a()
            elif local >= POPUP_W - 28:
                b()
        else:
            a()
            if kind == "close":
                self.popup = None
        return True

    # ---- dragging ----
    def start_drag(self, x, y):
        if (x - self.player[0]) ** 2 + (y - self.player[1]) ** 2 <= PLAYER_RADIUS**2:
            self.drag = ("player",)
            return
        sel = self.selected
        if sel is not None and sel in self.objects:
            for i, (hx, hy) in enumerate(self.handles(sel)):
                if abs(x - hx) <= HANDLE and abs(y - hy) <= HANDLE:
                    self.drag = ("handle", sel, i)
                    return
        o = self.object_at(x, y)
        self.selected = o
        if o is not None:
            self.objects.remove(o)
            self.objects.append(o)
            orig = {k: copy.deepcopy(o[k]) for k in GEOM_KEYS if k in o}
            self.drag = ("move", o, x, y, orig)

    def update_drag(self, x, y):
        if not self.drag:
            return
        kind = self.drag[0]
        if kind == "player":
            self.player[:] = clamp(x, 0, CANVAS_W), clamp(y, 0, CANVAS_H)
        elif kind == "move":
            _, o, sx, sy, orig = self.drag
            o.update(copy.deepcopy(orig))
            x1, y1, x2, y2 = self.bounds(o)
            dx = clamp(x - sx, -x1, CANVAS_W - x2)
            dy = clamp(y - sy, -y1, CANVAS_H - y2)
            self.translate(o, dx, dy)
        elif kind == "handle":
            _, o, i = self.drag
            mx, my = clamp(x, 0, CANVAS_W), clamp(y, 0, CANVAS_H)
            shape = SHAPES[o["type"]]
            if shape == "tri":
                o["pts"][i] = [mx, my]
            elif shape == "circle":
                o["r"] = clamp(math.hypot(mx - o["x"], my - o["y"]), 5, 400)
            else:
                corners = self.handles(o)
                ax, ay = corners[(i + 2) % 4]
                if abs(mx - ax) < MIN_SIZE:
                    mx = ax + (MIN_SIZE if mx >= ax else -MIN_SIZE)
                if abs(my - ay) < MIN_SIZE:
                    my = ay + (MIN_SIZE if my >= ay else -MIN_SIZE)
                o.update(x1=min(ax, mx), y1=min(ay, my), x2=max(ax, mx), y2=max(ay, my))
                # Flipping past the anchor reorders the corners, so follow the one now under the mouse.
                self.drag = (
                    "handle",
                    o,
                    [
                        (mx <= ax and my <= ay),
                        (mx > ax and my <= ay),
                        (mx > ax and my > ay),
                        (mx <= ax and my > ay),
                    ].index(True),
                )

    # ---- save / load ----
    def build_data(self):
        safe = re.sub(r"[^A-Za-z0-9_\-]", "_", self.meta["name"].strip()) or "new_map"
        walls = [o for o in self.objects if o["type"] == "wall_rect"]
        zones = [o for o in self.objects if o["type"] == "spawn_zone"]
        goals = [o for o in self.objects if o["type"] == "trig_move"]
        markers = [o for o in self.objects if o["type"] == "spawn_point"]
        ends = {o["id"] for o in self.objects if o["type"] == "level_end"}

        def corners(o):
            return [
                [round(o["x1"]), round(o["y1"])],
                [round(o["x2"]), round(o["y1"])],
                [round(o["x2"]), round(o["y2"])],
                [round(o["x1"]), round(o["y2"])],
            ]

        def source(o):
            return {
                "x": round(o["x"]),
                "y": round(o["y"]),
                "walls": [i for i, w in enumerate(walls) if w["id"] in o["targets"]],
                "zones": [i for i, z in enumerate(zones) if z["id"] in o["targets"]],
                "ends_tutorial": any(t in ends for t in o["targets"]),
            }

        data = {
            "name": safe,
            "player_start": [round(self.player[0]), round(self.player[1])],
            "enemy_spawning": (
                {"mode": "zones", "zones": [corners(z) for z in zones]}
                if zones
                else dict(DEFAULT_SPAWNING)
            ),
            "walls": [corners(w) for w in walls],
        }
        if goals:
            data["goals"] = [{**source(g), "radius": round(g["r"])} for g in goals]
        if markers:
            data["enemy_markers"] = [
                {**source(m), "enemy": m["enemy"]} for m in markers
            ]
        data["tutorial"] = dict(self.tutorial)
        levels = copy.deepcopy(data["tutorial"].get("levels", []))
        while (
            levels
            and not levels[-1].get("exp")
            and not any(levels[-1].get("cards", []))
        ):
            levels.pop()
        data["tutorial"]["levels"] = levels
        data["editor_objects"] = copy.deepcopy(self.objects)
        return safe, data

    def save(self):
        safe, data = self.build_data()
        os.makedirs(MAPS_DIR, exist_ok=True)
        with open(
            os.path.join(MAPS_DIR, safe + ".json"), "w", encoding="utf-8"
        ) as file:
            json.dump(data, file, indent=2)
        self.meta["name"] = safe
        self.status = f"Saved {safe}.json"

    def load(self, path):
        with open(path, "r", encoding="utf-8-sig") as file:
            data = json.load(file)
        self.objects, self.next_id = [], 1
        self.selected = self.drag = self.popup = self.connecting = self.placing = (
            self.typing
        ) = None
        start = data.get("player_start", [CANVAS_W / 2, CANVAS_H / 2])
        self.player = [float(start[0]), float(start[1])]
        tutorial = data.get("tutorial")
        self.tutorial = (
            dict(tutorial) if isinstance(tutorial, dict) else {"active": False}
        )
        self.tutorial.setdefault("outer_wall_exp", True)
        self.tutorial["waves"] = sanitize_waves(self.tutorial.get("waves"))
        self.tutorial["levels"] = sanitize_levels(self.tutorial.get("levels"))
        self.tutorial["icon"] = sanitize_icon(self.tutorial.get("icon"))
        self.meta["name"] = os.path.splitext(os.path.basename(path))[0]
        if isinstance(data.get("editor_objects"), list):
            self._load_objects(data["editor_objects"])
        else:
            self._load_legacy(data)
        self.status = f"Loaded {self.meta['name']}"

    def _load_objects(self, items):
        for item in items:
            if (
                not isinstance(item, dict)
                or item.get("type") not in TYPES
                or not isinstance(item.get("id"), int)
            ):
                continue
            self.objects.append(item)
            item.setdefault("targets", [])
            if item["type"] == "level_end":
                item.setdefault("delay_ticks", DEFAULT_LEVEL_END_DELAY_TICKS)
        self.next_id = max([o["id"] for o in self.objects], default=0) + 1
        ids = {o["id"] for o in self.objects}
        for o in self.objects:
            o["targets"] = [t for t in o["targets"] if t in ids]

    def _load_legacy(self, data):
        self._load_objects(legacy_objects(data))


# ---- rendering ----
def draw_arrow(surf, a, b):
    pygame.draw.line(surf, LINK_COLOR, a, b, 1)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    for side in (-2.6, 2.6):
        pygame.draw.line(
            surf,
            LINK_COLOR,
            mid,
            (mid[0] + 9 * math.cos(ang + side), mid[1] + 9 * math.sin(ang + side)),
            1,
        )


def draw_label(surf, text, pos, color=TEXT, size=18):
    img = get_font(size).render(text, True, color)
    surf.blit(img, img.get_rect(center=(round(pos[0]), round(pos[1]))))


def draw_object(surf, o, outline=None):
    _, _, fill, edge = TYPES[o["type"]]
    shape, t = SHAPES[o["type"]], o["type"]
    if shape == "rect":
        r = pygame.Rect(
            round(o["x1"]),
            round(o["y1"]),
            round(o["x2"] - o["x1"]),
            round(o["y2"] - o["y1"]),
        )
        pygame.draw.rect(surf, fill, r)
        pygame.draw.rect(surf, edge, r, 2)
        if t == "kill_zone":
            draw_label(surf, "KILL", r.center, edge)
            pygame.draw.line(surf, edge, r.topleft, r.bottomright, 1)
            pygame.draw.line(surf, edge, r.topright, r.bottomleft, 1)
    elif shape == "tri":
        pts = [(round(p[0]), round(p[1])) for p in o["pts"]]
        pygame.draw.polygon(surf, fill, pts)
        pygame.draw.polygon(surf, edge, pts, 2)
    elif shape == "circle":
        c, r = (round(o["x"]), round(o["y"])), round(o["r"])
        pygame.draw.circle(surf, fill, c, r)
        pygame.draw.circle(surf, edge, c, r, 3 if t != "wall_circle" else 2)
        if t in TRIGGERS:
            if o["fulfilled"]:
                pygame.draw.circle(surf, (255, 255, 255), c, r + 4, 2)
            tag = {
                "trig_move": "MOVE",
                "trig_attack": "ATTACK",
                "trig_ability": "ABILITY",
            }[t]
            if t != "trig_move" and o["count"] > 1:
                tag += f" x{o['count']}"
            draw_label(surf, tag, c, edge)
            draw_label(
                surf,
                "latch" if o["mode"] == "latch" else f"pulse {o['pulse_ticks']}t",
                (c[0], c[1] + 14),
                DIM,
                16,
            )
        elif t == "level_end":
            draw_label(surf, "END", c, edge)
    elif shape == "point":
        c = (round(o["x"]), round(o["y"]))
        pygame.draw.circle(surf, fill, c, POINT_RADIUS)
        pygame.draw.circle(surf, edge, c, POINT_RADIUS, 2)
        if t == "exp_spawner":
            draw_label(
                surf,
                f"EXP {o.get('amount', 5)}x{o.get('count', 1)}",
                (c[0], c[1] - POINT_RADIUS - 8),
                edge,
                16,
            )
            draw_label(surf, "XP", c, edge, 16)
        else:
            draw_label(surf, o["enemy"], (c[0], c[1] - POINT_RADIUS - 8), edge, 16)
            mode = o.get("mode", "latch")
            draw_label(
                surf,
                "latch" if mode == "latch" else f"pulse {o.get('pulse_ticks', 30)}t",
                (c[0], c[1] + POINT_RADIUS + 8),
                DIM,
                16,
            )
    elif shape == "text":
        img = get_font(int(o["size"])).render(o["text"] or "(text)", True, edge)
        surf.blit(img, img.get_rect(center=(round(o["x"]), round(o["y"]))))
    elif shape == "gate":
        r = pygame.Rect(0, 0, GATE_W, GATE_H)
        r.center = (round(o["x"]), round(o["y"]))
        pygame.draw.rect(surf, fill, r, border_radius=8)
        pygame.draw.rect(surf, edge, r, 2, border_radius=8)
        tag = {
            "wave_trigger": f"WAVE {o.get('wave', 1)}",
            "level_trigger": f"LV {o.get('level', 2)}",
        }.get(t)
        draw_label(surf, tag or o["gate"], r.center, edge, 18 if tag else 22)
    if outline:
        x1, y1, x2, y2 = Editor.bounds(o)
        pygame.draw.rect(
            surf,
            outline,
            (round(x1) - 3, round(y1) - 3, round(x2 - x1) + 6, round(y2 - y1) + 6),
            1,
        )


def draw_button(screen, rect, label, mouse, active=False, size=22):
    pygame.draw.rect(
        screen,
        GOLD if active else (BTN_HOVER if rect.collidepoint(mouse) else BTN),
        rect,
        border_radius=5,
    )
    draw_label(screen, label, rect.center, (20, 20, 20) if active else TEXT, size)


class App:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("Map Editor")
        self.clock = pygame.time.Clock()
        self.canvas = pygame.Surface((CANVAS_W, CANVAS_H))
        self.state = "menu"
        self.tutorial_mode = False
        self.entries = []
        self.scroll = 0
        self.editor = None
        self.tab = 0
        self.drawer_open = False
        self.drawer_t = 0.0
        self.menu_error = ""
        self.new_btn = pygame.Rect(250, 100, 230, 44)
        self.mode_btn = pygame.Rect(520, 100, 230, 44)
        self.list_rect = pygame.Rect(250, 170, 500, 440)
        self.back_btn = pygame.Rect(8, 5, 70, 26)
        self.name_box = pygame.Rect(82, 5, 174, 26)
        self.save_btn = pygame.Rect(262, 5, 60, 26)
        self.tut_btn = pygame.Rect(328, 5, 110, 26)
        self.exp_btn = pygame.Rect(444, 5, 80, 26)
        self.outer_wall_exp_btn = pygame.Rect(530, 5, 120, 26)
        self.waves_btn = pygame.Rect(656, 5, 55, 26)
        self.levels_btn = pygame.Rect(717, 5, 60, 26)
        self.info_btn = pygame.Rect(783, 5, 50, 26)
        self.panel = None  # None, "waves", "levels" or "info"
        self.icon_color = 2
        self.painting = None  # palette index being painted, or None
        self.panel_rect = pygame.Rect(60, 50, 880, 580)
        self.panel_sel = 0
        self.panel_scroll = 0
        self.refresh_entries()

    # ---- start menu ----
    def refresh_entries(self):
        self.entries = []
        for path in list_map_files():
            try:
                with open(path, "r", encoding="utf-8-sig") as file:
                    data = json.load(file)
                tutorial = bool((data.get("tutorial") or {}).get("active"))
            except (OSError, ValueError, AttributeError):
                continue
            if tutorial == self.tutorial_mode:
                self.entries.append((os.path.splitext(os.path.basename(path))[0], path))
        self.scroll = 0

    def max_scroll(self):
        return max(0, len(self.entries) * 44 - self.list_rect.height)

    def menu_click(self, pos):
        if self.new_btn.collidepoint(pos):
            self.editor = Editor(self.tutorial_mode)
            self.state = "edit"
        elif self.mode_btn.collidepoint(pos):
            self.tutorial_mode = not self.tutorial_mode
            self.refresh_entries()
        elif self.list_rect.collidepoint(pos):
            index = (pos[1] - self.list_rect.y + self.scroll) // 44
            if 0 <= index < len(self.entries):
                editor = Editor(self.tutorial_mode)
                try:
                    editor.load(self.entries[index][1])
                except (OSError, ValueError, KeyError, IndexError, TypeError):
                    self.menu_error = f"Failed to load {self.entries[index][0]}"
                    return
                self.menu_error = ""
                self.editor, self.state = editor, "edit"

    def draw_menu(self, mouse):
        self.screen.fill(BG)
        draw_label(self.screen, "Map Editor", (WIN_W / 2, 50), TEXT, 56)
        draw_button(self.screen, self.new_btn, "New Map", mouse)
        draw_button(
            self.screen,
            self.mode_btn,
            (
                "Showing: Tutorial Levels"
                if self.tutorial_mode
                else "Showing: Main Levels"
            ),
            mouse,
        )
        pygame.draw.rect(self.screen, PANEL, self.list_rect)
        self.screen.set_clip(self.list_rect)
        for i, (name, _) in enumerate(self.entries):
            row = pygame.Rect(
                self.list_rect.x + 6,
                self.list_rect.y + i * 44 - self.scroll + 3,
                self.list_rect.width - 22,
                38,
            )
            pygame.draw.rect(
                self.screen,
                (
                    BTN_HOVER
                    if row.collidepoint(mouse) and self.list_rect.collidepoint(mouse)
                    else BTN
                ),
                row,
                border_radius=5,
            )
            self.screen.blit(
                get_font(26).render(name, True, TEXT), (row.x + 12, row.y + 10)
            )
        if not self.entries:
            draw_label(
                self.screen,
                "No levels in this category",
                self.list_rect.center,
                DIM,
                26,
            )
        self.screen.set_clip(None)
        pygame.draw.rect(self.screen, DIM, self.list_rect, 1)
        if self.max_scroll() > 0:
            bar_h = max(
                30,
                self.list_rect.height
                * self.list_rect.height
                // (len(self.entries) * 44),
            )
            bar_y = (
                self.list_rect.y
                + (self.list_rect.height - bar_h) * self.scroll // self.max_scroll()
            )
            pygame.draw.rect(
                self.screen,
                DIM,
                (self.list_rect.right - 12, bar_y, 8, bar_h),
                border_radius=4,
            )
        if self.menu_error:
            draw_label(
                self.screen, self.menu_error, (WIN_W / 2, 635), (255, 120, 120), 24
            )

    # ---- editor ----
    def drawer_rect(self):
        h = round(DRAWER_H * self.drawer_t)
        return pygame.Rect(0, WIN_H - h, WIN_W, h)

    def hint_rect(self):
        return pygame.Rect(WIN_W // 2 - 130, WIN_H - 20, 260, 20)

    def drawer_buttons(self):
        top = WIN_H - DRAWER_H + 12
        buttons = []
        for i, (label, typ, extras) in enumerate(TABS[self.tab][1]):
            col, row = i % 7, i // 7
            buttons.append(
                (
                    pygame.Rect(14 + col * 140, top + row * 48, 130, 40),
                    label,
                    typ,
                    extras,
                )
            )
        return buttons

    def tab_rects(self):
        w = WIN_W // len(TABS)
        return [pygame.Rect(i * w, WIN_H - TAB_H, w, TAB_H) for i in range(len(TABS))]

    def editor_mouse_down(self, event):
        ed = self.editor
        sx, sy = event.pos
        if self.panel is not None:
            self.panel_click(event)
            return
        if ed.popup is not None:
            if event.button == 1:
                ed.popup_click(sx, sy)
                return
            ed.popup = None
        if ed.typing is not None and not (
            event.button == 1 and self.name_box.collidepoint(sx, sy)
        ):
            ed.typing = None
        if sy < TOP_H:
            if event.button != 1:
                return
            if self.back_btn.collidepoint(sx, sy):
                self.refresh_entries()
                self.state = "menu"
            elif self.name_box.collidepoint(sx, sy):
                ed.begin_typing(ed.meta, "name")
            elif self.save_btn.collidepoint(sx, sy):
                ed.save()
            elif self.tut_btn.collidepoint(sx, sy):
                ed.tutorial["active"] = not ed.tutorial.get("active", False)
            elif self.exp_btn.collidepoint(sx, sy) and ed.tutorial.get("active"):
                ed.tutorial["exp"] = not ed.tutorial.get("exp", False)
            elif (
                self.outer_wall_exp_btn.collidepoint(sx, sy)
                and ed.tutorial.get("active")
                and ed.tutorial.get("exp")
            ):
                ed.tutorial["outer_wall_exp"] = not ed.tutorial.get(
                    "outer_wall_exp", True
                )
            elif self.waves_btn.collidepoint(sx, sy) and ed.tutorial.get("active"):
                self.open_panel("waves")
            elif self.levels_btn.collidepoint(sx, sy) and ed.tutorial.get("active"):
                self.open_panel("levels")
            elif self.info_btn.collidepoint(sx, sy) and ed.tutorial.get("active"):
                self.open_panel("info")
            return
        drawer = self.drawer_rect()
        if drawer.height > 0 and sy >= drawer.y:
            if event.button == 1 and self.drawer_t >= 1.0:
                for i, rect in enumerate(self.tab_rects()):
                    if rect.collidepoint(sx, sy):
                        self.tab = i
                for rect, label, typ, extras in self.drawer_buttons():
                    if rect.collidepoint(sx, sy):
                        ed.placing = (typ, extras)
                        ed.connecting = None
                        ed.status = f"Click the canvas to place: {label} (Esc cancels)"
            return
        x, y = sx, sy - TOP_H
        if ed.placing is not None:
            if event.button == 1:
                o = ed.make(ed.placing[0], x, y, copy.deepcopy(ed.placing[1]))
                ed.selected = o
                ed.status = "Placed " + TYPES[o["type"]][1]
            ed.placing = None
            return
        if ed.connecting is not None:
            target = ed.object_at(x, y) if event.button == 1 else None
            if target is not None:
                ed.toggle_link(ed.connecting, target)
            else:
                ed.connecting = None
                ed.status = "Ready"
            return
        if event.button == 3:
            o = ed.object_at(x, y)
            if o is not None:
                ed.selected = o
                ed.popup = {"pos": (sx, sy), "obj": o}
        elif event.button == 1:
            ed.start_drag(x, y)

    # ---- waves / levels panels ----
    def open_panel(self, name):
        self.panel, self.panel_sel, self.panel_scroll = name, 0, 0
        tut = self.editor.tutorial
        tut.setdefault("waves", [])
        tut.setdefault("levels", [])
        tut.setdefault("name", "")
        tut.setdefault("description", "")
        tut.setdefault("body", BODY_NAMES[0])
        tut.setdefault("gun", GUN_NAMES[0])
        tut.setdefault("health", 10)
        tut["icon"] = sanitize_icon(tut.get("icon"))

    # ---- info panel (name, description, loadout, icon) ----
    def icon_rect(self):
        return pygame.Rect(
            self.panel_rect.x + 470,
            self.panel_rect.y + 70,
            ICON_SIZE * ICON_CELL,
            ICON_SIZE * ICON_CELL,
        )

    def swatch_rect(self, i):
        P = self.panel_rect
        return pygame.Rect(P.x + 470 + (i % 8) * 44, P.y + 440 + (i // 8) * 44, 40, 40)

    def paint_icon(self, pos, color):
        rect = self.icon_rect()
        if not rect.collidepoint(pos):
            return
        tut = self.editor.tutorial
        rows = (
            [list(r) for r in tut["icon"]]
            if tut.get("icon")
            else [["0"] * ICON_SIZE for _ in range(ICON_SIZE)]
        )
        rows[(pos[1] - rect.y) // ICON_CELL][(pos[0] - rect.x) // ICON_CELL] = (
            "0123456789abcdef"[color]
        )
        tut["icon"] = ["".join(r) for r in rows]

    def info_click(self, event):
        for i in range(len(ICON_PALETTE)):
            if self.swatch_rect(i).collidepoint(event.pos) and event.button == 1:
                self.icon_color = i
                return True
        if self.icon_rect().collidepoint(event.pos):
            self.painting = self.icon_color if event.button == 1 else 0
            self.paint_icon(event.pos, self.painting)
            return True
        return False

    def info_items(self):
        tut, P, ed = self.editor.tutorial, self.panel_rect, self.editor
        items = []

        def cycle(key, choices):
            def go(button):
                index = choices.index(tut[key]) if tut.get(key) in choices else 0
                tut[key] = choices[(index + (1 if button == 1 else -1)) % len(choices)]

            return go

        def bump(sign):
            def go(_):
                tut["health"] = clamp(int(tut.get("health", 10)) + sign, 1, 99)

            return go

        def clear(_):
            tut["icon"] = None

        def field(key):
            def go(_):
                ed.begin_typing(tut, key)

            return go

        typing_name = ed.typing is not None and ed.typing[1] == "name"
        items.append(
            (
                pygame.Rect(P.x + 16, P.y + 70, 420, 30),
                tut["name"] + ("|" if typing_name else ""),
                typing_name,
                field("name"),
            )
        )
        items.append(
            (
                pygame.Rect(P.x + 16, P.y + 140, 420, 150),
                "",
                False,
                field("description"),
            )
        )
        items.append(
            (
                pygame.Rect(P.x + 16, P.y + 330, 200, 30),
                "Body: " + str(tut["body"]),
                False,
                cycle("body", BODY_NAMES),
            )
        )
        items.append(
            (
                pygame.Rect(P.x + 236, P.y + 330, 200, 30),
                "Gun: " + str(tut["gun"]),
                False,
                cycle("gun", GUN_NAMES),
            )
        )
        items.append((pygame.Rect(P.x + 16, P.y + 390, 32, 30), "-", False, bump(-1)))
        items.append((pygame.Rect(P.x + 120, P.y + 390, 32, 30), "+", False, bump(1)))
        items.append(
            (pygame.Rect(P.x + 16, P.y + 440, 200, 30), "Clear Icon", False, clear)
        )
        return items

    def wrap_text(self, text, font, width):
        lines, line = [], ""
        for word in text.split(" "):
            trial = word if not line else line + " " + word
            if font.size(trial)[0] <= width or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        lines.append(line)
        return lines

    def draw_info(self):
        tut, P, ed = self.editor.tutorial, self.panel_rect, self.editor
        draw_label(self.screen, "Tutorial Info", (P.x + 440, P.y + 24), TEXT, 28)
        draw_label(self.screen, "Display name", (P.x + 70, P.y + 56), DIM, 20)
        draw_label(
            self.screen, "Displayed description", (P.x + 100, P.y + 126), DIM, 20
        )
        draw_label(self.screen, "Starting loadout", (P.x + 80, P.y + 316), DIM, 20)
        draw_label(
            self.screen,
            f"Health: {tut.get('health', 10)}",
            (P.x + 84, P.y + 405),
            TEXT,
            22,
        )
        draw_label(
            self.screen,
            "Map icon (16x16): left-click paints, right-click erases",
            (P.x + 650, P.y + 56),
            DIM,
            20,
        )
        typing_desc = ed.typing is not None and ed.typing[1] == "description"
        font = get_font(21)
        box = pygame.Rect(P.x + 16, P.y + 140, 420, 150)
        pygame.draw.rect(self.screen, GOLD if typing_desc else (120, 125, 150), box, 2)
        text = tut.get("description", "") + ("|" if typing_desc else "")
        for n, line in enumerate(self.wrap_text(text, font, box.width - 16)[:6]):
            self.screen.blit(
                font.render(line, True, TEXT), (box.x + 8, box.y + 8 + n * 22)
            )

        rect = self.icon_rect()
        rows = tut.get("icon") or ["0" * ICON_SIZE] * ICON_SIZE
        for y, row in enumerate(rows):
            for x, digit in enumerate(row):
                cell = pygame.Rect(
                    rect.x + x * ICON_CELL, rect.y + y * ICON_CELL, ICON_CELL, ICON_CELL
                )
                color = ICON_PALETTE[int(digit, 16)]
                pygame.draw.rect(
                    self.screen,
                    color or ((60, 63, 78) if (x + y) % 2 == 0 else (45, 48, 62)),
                    cell,
                )
        for k in range(ICON_SIZE + 1):
            pygame.draw.line(
                self.screen,
                (30, 32, 44),
                (rect.x + k * ICON_CELL, rect.y),
                (rect.x + k * ICON_CELL, rect.bottom),
            )
            pygame.draw.line(
                self.screen,
                (30, 32, 44),
                (rect.x, rect.y + k * ICON_CELL),
                (rect.right, rect.y + k * ICON_CELL),
            )
        pygame.draw.rect(self.screen, DIM, rect, 2)
        for i, color in enumerate(ICON_PALETTE):
            swatch = self.swatch_rect(i)
            pygame.draw.rect(self.screen, color or (45, 48, 62), swatch)
            if color is None:
                pygame.draw.line(
                    self.screen, (200, 60, 60), swatch.topleft, swatch.bottomright, 2
                )
            pygame.draw.rect(
                self.screen,
                GOLD if i == self.icon_color else (30, 32, 44),
                swatch,
                3 if i == self.icon_color else 1,
            )

        preview = pygame.Surface((ICON_SIZE, ICON_SIZE), pygame.SRCALPHA)
        for y, row in enumerate(rows):
            for x, digit in enumerate(row):
                color = ICON_PALETTE[int(digit, 16)]
                if color is not None:
                    preview.set_at((x, y), color)
        pygame.draw.rect(self.screen, (45, 48, 62), (P.x + 300, P.y + 430, 128, 128))
        self.screen.blit(
            pygame.transform.scale(preview, (128, 128)), (P.x + 300, P.y + 430)
        )
        pygame.draw.rect(self.screen, DIM, (P.x + 300, P.y + 430, 128, 128), 2)

    def panel_scroll_by(self, amount):
        tut = self.editor.tutorial
        limit = (
            max(0, len(tut["waves"]) - 12) if self.panel == "waves" else MAX_LEVELS - 11
        )
        self.panel_scroll = clamp(self.panel_scroll - amount, 0, limit)

    def panel_items(self):
        """(clickable [(rect, label, active, handler(button))], plain labels [(text, center, color, size)])."""
        tut, P = self.editor.tutorial, self.panel_rect
        items, labels = [], []
        shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)

        def close(_):
            self.panel = None

        items.append(
            (pygame.Rect(P.right - 90, P.y + 10, 76, 28), "Close", False, close)
        )
        if self.panel == "info":
            return items + self.info_items(), labels
        if self.panel == "waves":
            waves = tut["waves"]
            self.panel_sel = clamp(self.panel_sel, 0, max(0, len(waves) - 1))

            def toggle(_):
                tut["waves_enabled"] = not tut.get("waves_enabled", False)

            items.append(
                (
                    pygame.Rect(P.x + 16, P.y + 10, 180, 28),
                    "Waves: " + ("On" if tut.get("waves_enabled") else "Off"),
                    bool(tut.get("waves_enabled")),
                    toggle,
                )
            )
            labels.append(
                (
                    "Wave 1 spawns at the start; each next wave spawns 1s after the previous one is beaten.",
                    (P.x + 560, P.y + 24),
                    DIM,
                    20,
                )
            )
            for k in range(12):
                i = self.panel_scroll + k
                if i >= len(waves):
                    break

                def select(_, i=i):
                    self.panel_sel = i

                items.append(
                    (
                        pygame.Rect(P.x + 16, P.y + 60 + k * 32, 210, 28),
                        f"Wave {i + 1} ({sum(waves[i].values())})",
                        i == self.panel_sel,
                        select,
                    )
                )

            def add(_):
                if len(waves) < 99:
                    waves.append({})
                    self.panel_sel = len(waves) - 1
                    self.panel_scroll = max(0, len(waves) - 12)

            def remove(_):
                if waves:
                    del waves[min(self.panel_sel, len(waves) - 1)]
                    self.panel_scroll = clamp(
                        self.panel_scroll, 0, max(0, len(waves) - 12)
                    )

            items.append(
                (pygame.Rect(P.x + 16, P.bottom - 80, 210, 28), "Add Wave", False, add)
            )
            items.append(
                (
                    pygame.Rect(P.x + 16, P.bottom - 44, 210, 28),
                    "Remove Selected Wave",
                    False,
                    remove,
                )
            )
            if waves:
                wave = waves[self.panel_sel]
                labels.append(
                    (
                        f"Wave {self.panel_sel + 1} enemies (total {sum(wave.values())})",
                        (P.x + 400, P.y + 76),
                        TEXT,
                        26,
                    )
                )
                for k, enemy in enumerate(ENEMY_TYPES):
                    y = P.y + 110 + k * 44
                    labels.append((enemy, (P.x + 300, y + 16), TEXT, 24))

                    def bump(button, enemy=enemy, sign=0):
                        step = 5 if shift else 1
                        count = clamp(wave.get(enemy, 0) + sign * step, 0, 99)
                        if count:
                            wave[enemy] = count
                        else:
                            wave.pop(enemy, None)

                    items.append(
                        (
                            pygame.Rect(P.x + 400, y, 32, 32),
                            "-",
                            False,
                            lambda b, e=enemy: bump(b, e, -1),
                        )
                    )
                    labels.append(
                        (str(wave.get(enemy, 0)), (P.x + 466, y + 16), GOLD, 26)
                    )
                    items.append(
                        (
                            pygame.Rect(P.x + 500, y, 32, 32),
                            "+",
                            False,
                            lambda b, e=enemy: bump(b, e, 1),
                        )
                    )
                labels.append(
                    ("Shift-click +/- changes by 5", (P.x + 700, P.y + 76), DIM, 20)
                )
            else:
                labels.append(("Add a wave to start", (P.x + 500, P.y + 200), DIM, 26))
        else:
            levels = tut["levels"]
            while len(levels) < self.panel_scroll + 11:
                levels.append({"exp": None, "cards": [None] * CARDS_PER_LEVEL})
            labels.append(
                (
                    "Exp needed and upgrade cards per level-up (mouse wheel scrolls)",
                    (P.x + 330, P.y + 24),
                    TEXT,
                    24,
                )
            )
            labels.append(
                (
                    "Auto exp = 10, then x1.4 per level. Click a card to cycle, right-click to cycle back. Shift = +/-1.",
                    (P.x + 440, P.y + 62),
                    DIM,
                    20,
                )
            )
            labels.append(("Exp needed", (P.x + 190, P.y + 90), DIM, 20))
            for j in range(CARDS_PER_LEVEL):
                labels.append(
                    (f"Card {j + 1}", (P.x + 440 + j * 160, P.y + 90), DIM, 20)
                )
            names = [None] + [u.name for u in total_Upgrades]
            for k in range(11):
                i = self.panel_scroll + k
                entry = levels[i]
                y = P.y + 108 + k * 40
                effective = level_requirement(levels, i + 1)
                labels.append((f"Lv {i + 1} to {i + 2}", (P.x + 62, y + 16), TEXT, 24))

                def bump(_, i=i, sign=0):
                    levels[i]["exp"] = max(
                        1, level_requirement(levels, i + 1) + sign * (1 if shift else 5)
                    )

                def auto(_, i=i):
                    levels[i]["exp"] = None

                items.append(
                    (
                        pygame.Rect(P.x + 110, y, 28, 32),
                        "-",
                        False,
                        lambda b, i=i: bump(b, i, -1),
                    )
                )
                labels.append(
                    (
                        str(effective) + ("" if entry["exp"] else " (auto)"),
                        (P.x + 190, y + 16),
                        GOLD if entry["exp"] else DIM,
                        22,
                    )
                )
                items.append(
                    (
                        pygame.Rect(P.x + 242, y, 28, 32),
                        "+",
                        False,
                        lambda b, i=i: bump(b, i, 1),
                    )
                )
                items.append((pygame.Rect(P.x + 276, y, 54, 32), "Auto", False, auto))
                for j in range(CARDS_PER_LEVEL):

                    def cycle(button, i=i, j=j):
                        cards = levels[i]["cards"]
                        index = names.index(cards[j]) if cards[j] in names else 0
                        cards[j] = names[
                            (index + (1 if button == 1 else -1)) % len(names)
                        ]

                    items.append(
                        (
                            pygame.Rect(P.x + 362 + j * 160, y, 154, 32),
                            entry["cards"][j] or "Random",
                            entry["cards"][j] is not None,
                            cycle,
                        )
                    )
        return items, labels

    def panel_click(self, event):
        if event.button not in (1, 3):
            return
        if not self.panel_rect.collidepoint(event.pos):
            self.panel = None
            self.editor.typing = None
            return
        self.editor.typing = None
        if self.panel == "info" and self.info_click(event):
            return
        for rect, _, _, handler in reversed(self.panel_items()[0]):
            if rect.collidepoint(event.pos):
                handler(event.button)
                return

    def draw_panel(self, mouse):
        shade = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 140))
        self.screen.blit(shade, (0, 0))
        pygame.draw.rect(self.screen, (18, 20, 30), self.panel_rect)
        pygame.draw.rect(self.screen, DIM, self.panel_rect, 2)
        items, labels = self.panel_items()
        for text, pos, color, size in labels:
            draw_label(self.screen, text, pos, color, size)
        for rect, label, active, _ in items:
            draw_button(self.screen, rect, label, mouse, active, 20)
        if self.panel == "info":
            self.draw_info()

    def editor_key(self, event):
        ed = self.editor
        if ed.typing is not None:
            target, key = ed.typing
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
                ed.typing = None
            elif event.key == pygame.K_BACKSPACE:
                target[key] = target[key][:-1]
            elif (
                event.unicode
                and event.unicode.isprintable()
                and len(target[key]) < TEXT_LIMITS.get(key, 40)
            ):
                target[key] += event.unicode
            return
        if self.panel is not None:
            if event.key == pygame.K_ESCAPE:
                self.panel = None
            return
        if event.key == pygame.K_ESCAPE:
            if ed.popup is not None:
                ed.popup = None
            elif ed.placing is not None:
                ed.placing = None
            elif ed.connecting is not None:
                ed.connecting = None
            ed.status = "Ready"
        elif event.key == pygame.K_DELETE and ed.popup is None:
            mx, my = pygame.mouse.get_pos()
            o = ed.object_at(mx, my - TOP_H)
            if o is not None:
                ed.delete(o)

    def draw_editor(self, mouse):
        ed = self.editor
        mx, my = mouse[0], mouse[1] - TOP_H
        canvas = self.canvas
        canvas.fill(BG)
        hovered = ed.object_at(mx, my) if my >= 0 else None
        for o in ed.objects:
            for tid in o["targets"]:
                t = ed.by_id(tid)
                if t is not None:
                    draw_arrow(canvas, ed.center(o), ed.center(t))
        for o in ed.objects:
            draw_object(
                canvas,
                o,
                GOLD if o is ed.selected else (LINK_COLOR if o is hovered else None),
            )
        if ed.selected in ed.objects:
            for hx, hy in ed.handles(ed.selected):
                pygame.draw.rect(canvas, GOLD, (round(hx) - 5, round(hy) - 5, 10, 10))
        if ed.connecting is not None:
            pygame.draw.line(canvas, LINK_COLOR, ed.center(ed.connecting), (mx, my), 1)
            x1, y1, x2, y2 = ed.bounds(ed.connecting)
            pygame.draw.rect(
                canvas, LINK_COLOR, (x1 - 5, y1 - 5, x2 - x1 + 10, y2 - y1 + 10), 2
            )
        px, py = round(ed.player[0]), round(ed.player[1])
        pygame.draw.circle(canvas, (60, 200, 90), (px, py), PLAYER_RADIUS)
        pygame.draw.circle(canvas, (220, 255, 225), (px, py), PLAYER_RADIUS, 2)
        draw_label(canvas, "spawn", (px, py), (10, 40, 15), 16)
        self.screen.blit(canvas, (0, TOP_H))

        # top bar
        pygame.draw.rect(self.screen, PANEL, (0, 0, WIN_W, TOP_H))
        draw_button(self.screen, self.back_btn, "Back", mouse, size=20)
        typing_name = ed.typing is not None and ed.typing[1] == "name"
        pygame.draw.rect(self.screen, (15, 17, 26), self.name_box)
        pygame.draw.rect(
            self.screen, GOLD if typing_name else (120, 125, 150), self.name_box, 2
        )
        self.screen.blit(
            get_font(22).render(
                ed.meta["name"] + ("|" if typing_name else ""), True, TEXT
            ),
            (self.name_box.x + 6, self.name_box.y + 5),
        )
        draw_button(self.screen, self.save_btn, "Save", mouse, size=20)
        draw_button(
            self.screen,
            self.tut_btn,
            "Tutorial: " + ("On" if ed.tutorial.get("active") else "Off"),
            mouse,
            size=20,
        )
        if ed.tutorial.get("active"):
            draw_button(
                self.screen,
                self.exp_btn,
                "EXP: " + ("On" if ed.tutorial.get("exp") else "Off"),
                mouse,
                size=20,
            )
            if ed.tutorial.get("exp"):
                draw_button(
                    self.screen,
                    self.outer_wall_exp_btn,
                    "Outer EXP: "
                    + ("On" if ed.tutorial.get("outer_wall_exp", True) else "Off"),
                    mouse,
                    size=18,
                )
        if ed.tutorial.get("active"):
            draw_button(
                self.screen,
                self.waves_btn,
                "Waves",
                mouse,
                ed.tutorial.get("waves_enabled", False),
                size=20,
            )
            draw_button(self.screen, self.levels_btn, "Levels", mouse, size=20)
            draw_button(self.screen, self.info_btn, "Info", mouse, size=20)
        self.screen.set_clip(pygame.Rect(840, 0, WIN_W - 840, TOP_H))
        self.screen.blit(get_font(20).render(ed.status, True, DIM), (842, 11))
        self.screen.set_clip(None)

        self.draw_drawer(mouse)
        if ed.popup is not None:
            self.draw_popup(mouse)
        if self.panel is not None:
            self.draw_panel(mouse)

    def draw_drawer(self, mouse):
        drawer = self.drawer_rect()
        if drawer.height <= 0:
            hint = self.hint_rect()
            pygame.draw.rect(
                self.screen,
                (18, 20, 30),
                hint,
                border_top_left_radius=8,
                border_top_right_radius=8,
            )
            pygame.draw.rect(
                self.screen,
                DIM,
                hint,
                1,
                border_top_left_radius=8,
                border_top_right_radius=8,
            )
            draw_label(self.screen, "Hover here for objects", hint.center, TEXT, 18)
            return
        pygame.draw.rect(self.screen, (18, 20, 30), drawer)
        pygame.draw.line(self.screen, DIM, drawer.topleft, drawer.topright, 1)
        self.screen.set_clip(drawer)
        for rect, label, typ, _ in self.drawer_buttons():
            draw_button(self.screen, rect, label, mouse, size=20)
            pygame.draw.rect(
                self.screen, TYPES[typ][3], (rect.x, rect.bottom - 4, rect.width, 4)
            )
        for i, rect in enumerate(self.tab_rects()):
            pygame.draw.rect(self.screen, GOLD if i == self.tab else BTN, rect)
            pygame.draw.rect(self.screen, (18, 20, 30), rect, 1)
            draw_label(
                self.screen,
                TABS[i][0],
                rect.center,
                (20, 20, 20) if i == self.tab else TEXT,
                22,
            )
        self.screen.set_clip(None)

    def draw_popup(self, mouse):
        rect = self.editor.popup_rect()
        for i, (text, kind, _, _) in enumerate(
            self.editor.rows(self.editor.popup["obj"])
        ):
            row = pygame.Rect(rect.x, rect.y + i * ROW_H, POPUP_W, ROW_H)
            pygame.draw.rect(
                self.screen,
                (
                    BTN_HOVER
                    if row.collidepoint(mouse) and kind != "num"
                    else (45, 49, 68)
                ),
                row,
            )
            pygame.draw.rect(self.screen, (170, 175, 200), row, 1)
            typing = self.editor.typing is not None and kind == "text"
            self.screen.blit(
                get_font(21).render(text + ("|" if typing else ""), True, TEXT),
                (row.x + 8, row.y + 6),
            )
            if kind == "num":
                for j, sign in enumerate("-+"):
                    box = pygame.Rect(row.right - 56 + j * 28, row.y + 2, 26, ROW_H - 4)
                    pygame.draw.rect(
                        self.screen,
                        BTN_HOVER if box.collidepoint(mouse) else BTN,
                        box,
                        border_radius=4,
                    )
                    draw_label(self.screen, sign, box.center, TEXT, 24)

    def update_drawer(self, mouse):
        ed = self.editor
        if self.drawer_open:
            # stay open while the mouse is over the menu (with a margin so the top edge doesn't flicker)
            if (
                mouse[1] < WIN_H - DRAWER_H - DRAWER_MARGIN
                or not pygame.mouse.get_focused()
            ):
                self.drawer_open = False
        elif (
            (mouse[1] >= WIN_H - EDGE_ZONE or self.hint_rect().collidepoint(mouse))
            and pygame.mouse.get_focused()
            and ed.popup is None
            and ed.drag is None
            and ed.placing is None
        ):
            self.drawer_open = True
        target = 1.0 if self.drawer_open else 0.0
        self.drawer_t = clamp(
            self.drawer_t + (0.2 if target > self.drawer_t else -0.2), 0.0, 1.0
        )

    def run(self):
        running = True
        while running:
            mouse = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif self.state == "menu":
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        self.menu_click(event.pos)
                    elif event.type == pygame.MOUSEWHEEL:
                        self.scroll = clamp(
                            self.scroll - event.y * 40, 0, self.max_scroll()
                        )
                else:
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        self.editor_mouse_down(event)
                    elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                        self.editor.drag = None
                        self.painting = None
                    elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
                        self.painting = None
                    elif event.type == pygame.MOUSEWHEEL and self.panel is not None:
                        self.panel_scroll_by(event.y)
                    elif event.type == pygame.MOUSEMOTION:
                        if self.painting is not None and self.panel == "info":
                            self.paint_icon(event.pos, self.painting)
                        self.editor.update_drag(event.pos[0], event.pos[1] - TOP_H)
                    elif event.type == pygame.KEYDOWN:
                        self.editor_key(event)
            if self.state == "menu":
                self.draw_menu(mouse)
            else:
                self.update_drawer(mouse)
                self.draw_editor(mouse)
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit()


if __name__ == "__main__":
    App().run()
