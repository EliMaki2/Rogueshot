import json
import os
import random

MAPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "map_presets")
DEFAULT_SPAWNING = {"mode": "default"}
DEFAULT_GOAL_RADIUS = 45
DEFAULT_LEVEL_END_DELAY_TICKS = 150
ENEMY_TYPES = (
    "Chaser",
    "Dasher",
    "Blaster",
    "Ghost",
    "Spiker",
    "Commander",
    "Guardian",
    "Warper",
    "Turret",
)

DEFAULT_TUTORIAL = {
    "active": False,
    "name": "",
    "description": "",
    "body": "Dasher",
    "gun": "Shotgun",
    "health": 10,
    "intro": "",
    "goal_text": "",
    "goal": "reach",
    "duration": 600,
    "spawns": [],
    "exp": False,
    "outer_wall_exp": True,
    "waves_enabled": False,
    "waves": [],
    "levels": [],
    "icon": None,
}
ICON_SIZE = 16
# Icon rows are 16 hex digits; digit 0 is transparent, the rest index ICON_PALETTE.
ICON_PALETTE = (
    None,
    (0, 0, 0),
    (255, 255, 255),
    (157, 157, 157),
    (190, 38, 51),
    (224, 111, 139),
    (164, 100, 34),
    (235, 137, 49),
    (247, 226, 107),
    (68, 137, 26),
    (163, 206, 39),
    (0, 87, 132),
    (49, 162, 242),
    (178, 220, 239),
    (47, 72, 78),
    (137, 61, 156),
)


def sanitize_icon(icon):
    if not isinstance(icon, list) or len(icon) != ICON_SIZE:
        return None
    rows = []
    for row in icon:
        if (
            not isinstance(row, str)
            or len(row) != ICON_SIZE
            or any(c not in "0123456789abcdef" for c in row)
        ):
            return None
        rows.append(row)
    return rows if any(c != "0" for row in rows for c in row) else None


LEVEL_EXP_FIRST = 10
LEVEL_EXP_GROWTH = 1.4
MAX_LEVELS = 50
CARDS_PER_LEVEL = 3


OBJECT_TYPES = frozenset(
    {
        "wall_rect",
        "wall_tri",
        "wall_circle",
        "trig_move",
        "trig_attack",
        "trig_ability",
        "spawn_zone",
        "spawn_point",
        "kill_zone",
        "text",
        "level_end",
        "gate",
        "wave_trigger",
        "level_trigger",
        "exp_spawner",
    }
)
GATE_TYPES = ("AND", "OR", "NOT", "NAND", "NOR", "XOR", "XNOR")


class MapPreset:
    """A loaded map: its editor-format object list plus tutorial settings (see Background/logic.py for play)."""

    def __init__(self, name, player_start, objects, tutorial=None):
        self.name = name
        self.player_start = player_start
        self.objects = objects
        self.tutorial = tutorial if tutorial is not None else dict(DEFAULT_TUTORIAL)


def legacy_objects(data):
    """Convert the old walls/goals/enemy_markers/enemy_spawning fields into editor-format objects."""
    objects = []

    def add(kind, **fields):
        obj = {"id": len(objects) + 1, "type": kind, "targets": []}
        obj.update(fields)
        objects.append(obj)
        return obj

    def rect(kind, corners):
        if len(corners) != 4:
            raise ValueError("a wall needs exactly four corners")
        xs = [float(c[0]) for c in corners]
        ys = [float(c[1]) for c in corners]
        return add(kind, x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys))

    walls = [rect("wall_rect", c) for c in data.get("walls", [])]
    spawning = data.get("enemy_spawning")
    zones = []
    if isinstance(spawning, dict) and spawning.get("mode") == "zones":
        for corners in spawning.get("zones", []):
            try:
                zones.append(rect("spawn_zone", corners))
            except (ValueError, TypeError, IndexError, KeyError):
                continue

    def link(obj, entry):
        for key, pool in (("walls", walls), ("zones", zones)):
            indices = entry.get(key, [])
            if isinstance(indices, list):
                obj["targets"] += [
                    pool[i]["id"]
                    for i in indices
                    if isinstance(i, int) and 0 <= i < len(pool)
                ]
        if entry.get("ends_tutorial"):
            end = add("level_end", x=obj["x"], y=min(obj["y"] + 70, 585), r=30)
            obj["targets"].append(end["id"])

    goals = data.get("goals", data.get("goal"))
    if isinstance(goals, dict):
        goals = [goals]
    for entry in goals if isinstance(goals, list) else []:
        try:
            trigger = add(
                "trig_move",
                x=float(entry["x"]),
                y=float(entry["y"]),
                r=max(5.0, float(entry.get("radius", DEFAULT_GOAL_RADIUS))),
                mode="latch",
                pulse_ticks=30,
                fulfilled=False,
            )
        except (KeyError, TypeError, ValueError):
            continue
        link(trigger, entry)
    markers = data.get("enemy_markers")
    for entry in markers if isinstance(markers, list) else []:
        try:
            enemy = entry.get("enemy", ENEMY_TYPES[0])
            point = add(
                "spawn_point",
                x=float(entry["x"]),
                y=float(entry["y"]),
                enemy=enemy if enemy in ENEMY_TYPES else ENEMY_TYPES[0],
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        link(point, entry)
    return objects


def parse_objects(items):
    """Validate editor-format objects, dropping unknown types and dangling links."""
    objects = []
    for item in items:
        if (
            isinstance(item, dict)
            and item.get("type") in OBJECT_TYPES
            and isinstance(item.get("id"), int)
        ):
            item.setdefault("targets", [])
            objects.append(item)
    ids = {o["id"] for o in objects}
    for obj in objects:
        targets = obj["targets"] if isinstance(obj["targets"], list) else []
        obj["targets"] = [t for t in targets if t in ids]
    return objects


def sanitize_waves(waves):
    """Wave list -> [{enemy name: count}, ...] keeping only known enemies with positive counts."""
    clean = []
    for wave in waves if isinstance(waves, list) else []:
        wave = wave if isinstance(wave, dict) else {}
        entry = {}
        for enemy, count in wave.items():
            if (
                enemy in ENEMY_TYPES
                and isinstance(count, (int, float))
                and int(count) > 0
            ):
                entry[enemy] = int(count)
        clean.append(entry)
    return clean


def sanitize_levels(levels):
    """Level list -> [{"exp": int or None, "cards": [name or None] * 3}, ...]; entry i is the step from level i+1."""
    clean = []
    for entry in (levels if isinstance(levels, list) else [])[:MAX_LEVELS]:
        entry = entry if isinstance(entry, dict) else {}
        exp = entry.get("exp")
        exp = (
            int(exp)
            if isinstance(exp, (int, float)) and not isinstance(exp, bool) and exp >= 1
            else None
        )
        cards = entry.get("cards") if isinstance(entry.get("cards"), list) else []
        cards = [
            c if isinstance(c, str) and c else None for c in cards[:CARDS_PER_LEVEL]
        ]
        cards += [None] * (CARDS_PER_LEVEL - len(cards))
        clean.append({"exp": exp, "cards": cards})
    return clean


def level_requirement(levels, level):
    """Exp needed to go from `level` to the next one; unset steps grow 1.4x from the previous step."""
    need = LEVEL_EXP_FIRST
    for i in range(max(1, int(level))):
        entry = levels[i] if i < len(levels) else None
        if i > 0:
            need = round(need * LEVEL_EXP_GROWTH)
        if entry and entry.get("exp"):
            need = entry["exp"]
    return need


def _parse_tutorial(data, name):
    tutorial = dict(DEFAULT_TUTORIAL)
    if isinstance(data, dict):
        tutorial.update({k: v for k, v in data.items() if k in DEFAULT_TUTORIAL})
    tutorial["active"] = bool(tutorial["active"])
    tutorial["exp"] = bool(tutorial["exp"])
    tutorial["outer_wall_exp"] = bool(tutorial["outer_wall_exp"])
    tutorial["waves_enabled"] = bool(tutorial["waves_enabled"])
    tutorial["waves"] = sanitize_waves(tutorial["waves"])
    tutorial["levels"] = sanitize_levels(tutorial["levels"])
    tutorial["icon"] = sanitize_icon(tutorial["icon"])
    if tutorial["goal"] not in ("reach", "kill", "survive"):
        tutorial["goal"] = "reach"
    if not tutorial["name"]:
        tutorial["name"] = name.replace("_", " ").title()
    if not tutorial["intro"]:
        tutorial["intro"] = tutorial["name"]
    if not tutorial["goal_text"]:
        tutorial["goal_text"] = {
            "reach": "Reach the glowing zone",
            "kill": "Defeat all enemies",
            "survive": "Survive",
        }[tutorial["goal"]]
    if not isinstance(tutorial["spawns"], list):
        tutorial["spawns"] = []
    return tutorial


def load_map(path):
    with open(path, "r", encoding="utf-8-sig") as file:
        data = json.load(file)
    start = data["player_start"]
    name = data.get("name", os.path.splitext(os.path.basename(path))[0])
    if isinstance(data.get("editor_objects"), list):
        objects = parse_objects(data["editor_objects"])
    else:
        objects = legacy_objects(data)
    return MapPreset(
        name,
        (float(start[0]), float(start[1])),
        objects,
        _parse_tutorial(data.get("tutorial"), name),
    )


def load_map_by_name(name):
    try:
        return load_map(os.path.join(MAPS_DIR, os.path.basename(str(name)) + ".json"))
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return None


def list_map_files():
    if not os.path.isdir(MAPS_DIR):
        return []
    return [
        os.path.join(MAPS_DIR, f)
        for f in sorted(os.listdir(MAPS_DIR))
        if f.lower().endswith(".json")
    ]


def load_tutorial_maps():
    """Every valid map whose tutorial flag is active, in file order."""
    maps = []
    for path in list_map_files():
        try:
            preset = load_map(path)
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            continue
        if preset.tutorial["active"]:
            maps.append((os.path.splitext(os.path.basename(path))[0], preset))
    return maps


def list_playable_map_names():
    """Names (file stems) of valid maps that are not tutorial maps."""
    names = []
    for path in list_map_files():
        try:
            preset = load_map(path)
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            continue
        if not preset.tutorial["active"]:
            names.append(os.path.splitext(os.path.basename(path))[0])
    return names


def load_random_map():
    """Pick a random valid preset; falls back to None if none can be loaded."""
    files = list_map_files()
    random.shuffle(files)
    for path in files:
        try:
            preset = load_map(path)
        except (OSError, ValueError, KeyError, IndexError, TypeError):
            continue
        if not preset.tutorial["active"]:
            return preset
    return None
