import json
import os
from datetime import datetime


STATS_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "run_stats.json")
HAUNTING_OPTION_KEYS = ("Chaser", "Dasher", "Blaster", "Ghost", "Spiker", "Guardian", "Warper", "Turret")
SWARM_ENEMY_KEYS = ("Chaser", "Dasher", "Blaster", "Ghost", "Spiker", "Guardian", "Warper", "Turret")
CANONICAL_PLAYER_NAMES = {"dasher": "Dasher", "nova": "Nova", "retribution": "Retribution", "slime": "Slime"}
CANONICAL_GUN_NAMES = {
    "blowdart": "Blowdart",
    "cannon": "Cannon",
    "shotgun": "Shotgun",
    "sword": "Sword",
    "flamethrower": "Flamethrower",
}
CANONICAL_HAUNTING_NAMES = {name.lower(): name for name in HAUNTING_OPTION_KEYS}
CANONICAL_SWARM_NAMES = {name.lower(): name for name in SWARM_ENEMY_KEYS}
CANONICAL_HAUNTING_NAMES["Guardian"] = "Guardian"
CANONICAL_SWARM_NAMES["Guardian"] = "Guardian"
SECRET_PROGRESS_KEYS = {
    "blaster_self_destructions": 0,
    "offscreen_distance_max": 0,
    "spiker_parries": 0,
}


def default_haunting_options():
    return {enemy_name: False for enemy_name in HAUNTING_OPTION_KEYS}


def default_swarm_options():
    return {
        "enabled": False,
        "enemy_types": [SWARM_ENEMY_KEYS[0]],
        "enemy_type": SWARM_ENEMY_KEYS[0],
    }


def default_selected_loadout():
    return {
        "body": "Dasher",
        "gun": "Cannon",
    }


def _normalize_swarm_enemy_types(raw_enemy_types, fallback=None):
    normalized = []
    fallback = fallback or [SWARM_ENEMY_KEYS[0]]

    if isinstance(raw_enemy_types, str):
        raw_enemy_types = [raw_enemy_types]

    if isinstance(raw_enemy_types, (list, tuple, set)):
        for enemy_name in raw_enemy_types:
            enemy_name = str(enemy_name).strip()
            if enemy_name in SWARM_ENEMY_KEYS and enemy_name not in normalized:
                normalized.append(enemy_name)

    if not normalized:
        for enemy_name in fallback:
            enemy_name = str(enemy_name).strip()
            if enemy_name in SWARM_ENEMY_KEYS and enemy_name not in normalized:
                normalized.append(enemy_name)

    if not normalized:
        normalized = [SWARM_ENEMY_KEYS[0]]

    return normalized


def _normalize_selected_loadout(raw_loadout, fallback_body="Dasher", fallback_gun="Cannon"):
    fallback = {
        "body": _canonicalize_name(fallback_body, CANONICAL_PLAYER_NAMES),
        "gun": _canonicalize_name(fallback_gun, CANONICAL_GUN_NAMES),
    }

    if not isinstance(raw_loadout, dict):
        return fallback

    body_name = _canonicalize_name(raw_loadout.get("body", fallback["body"]), CANONICAL_PLAYER_NAMES)
    gun_name = _canonicalize_name(raw_loadout.get("gun", fallback["gun"]), CANONICAL_GUN_NAMES)
    return {
        "body": body_name,
        "gun": gun_name,
    }


def create_run_snapshot(selected_body, selected_gun):
    return {
        "body": selected_body,
        "gun": selected_gun,
        "waves_spawned": 0,
        "level_ups": 0,
        "upgrades_chosen": 0,
        "level_reached": 1,
        "ticks_survived": 0,
        "exp_held": 0,
    }


def update_runtime(run_snapshot, game_ticks, level, exp_held):
    run_snapshot["ticks_survived"] = max(run_snapshot.get("ticks_survived", 0), int(game_ticks))
    run_snapshot["level_reached"] = max(run_snapshot.get("level_reached", 1), int(level))
    run_snapshot["exp_held"] = max(run_snapshot.get("exp_held", 0), int(exp_held))


def _default_store():
    return {
        "version": 1,
        "updated_at": None,
        "totals": {
            "runs_started": 0,
            "runs_finished": 0,
            "waves_spawned": 0,
            "level_ups": 0,
            "upgrades_chosen": 0,
        },
        "best_run": {
            "waves_spawned": 0,
            "level_ups": 0,
            "upgrades_chosen": 0,
            "level_reached": 0,
            "ticks_survived": 0,
            "exp_held": 0,
        },
        "current_run": {},
        "suspended_run": {},
        "last_run": {},
        "last_player_snapshot": {},
        "selected_loadout": default_selected_loadout(),
        "achievements": {
            "enemy_kills": {},  # {"enemy_type": total_kills}
            "player_max_levels": {},  # {"player_name": max_level}
            "gun_max_levels": {},  # {"gun_name": max_level}
            "waves_by_combo": {},  # {"player_gun": max_waves}
            "levels_by_combo": {},  # {"player_gun": max_level}
            "levels_total_by_combo": {},  # {"player_gun": total_level_ups}
            "haunting_max_levels": {},  # {"haunting_name": max_level}
            "swarm_max_levels": {},  # {"swarm_enemy_name": max_level}
            "secret_progress": dict(SECRET_PROGRESS_KEYS),
        },
        "options": {
            "hauntings": default_haunting_options(),
            "swarm": default_swarm_options(),
        },
    }


def _load_store():
    if not os.path.exists(STATS_FILE_PATH):
        return _default_store()

    try:
        with open(STATS_FILE_PATH, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return _default_store()

    defaults = _default_store()
    defaults.update(loaded)
    defaults["totals"].update(loaded.get("totals", {}))
    defaults["best_run"].update(loaded.get("best_run", {}))
    defaults["achievements"].update(loaded.get("achievements", {}))
    defaults["options"].update(loaded.get("options", {}))
    if not isinstance(defaults.get("suspended_run"), dict):
        defaults["suspended_run"] = {}
    for key in ["enemy_kills", "player_max_levels", "gun_max_levels", "waves_by_combo", "levels_by_combo", "levels_total_by_combo", "haunting_max_levels", "swarm_max_levels", "secret_progress"]:
        if key not in defaults["achievements"]:
            defaults["achievements"][key] = {}
    hauntings = default_haunting_options()
    hauntings.update(defaults["options"].get("hauntings", {}))
    defaults["options"]["hauntings"] = {enemy_name: bool(hauntings.get(enemy_name, False)) for enemy_name in HAUNTING_OPTION_KEYS}

    swarm = default_swarm_options()
    loaded_swarm = defaults["options"].get("swarm", {})
    if isinstance(loaded_swarm, dict):
        swarm["enabled"] = bool(loaded_swarm.get("enabled", False))
        fallback_enemy = loaded_swarm.get("enemy_type", swarm["enemy_type"])
        enemy_types = _normalize_swarm_enemy_types(
            loaded_swarm.get("enemy_types", []),
            fallback=[fallback_enemy],
        )
        swarm["enemy_types"] = enemy_types
        swarm["enemy_type"] = enemy_types[0]
    defaults["options"]["swarm"] = swarm

    defaults["achievements"]["player_max_levels"] = _normalize_level_map(
        defaults["achievements"].get("player_max_levels", {}),
        CANONICAL_PLAYER_NAMES,
    )
    defaults["achievements"]["gun_max_levels"] = _normalize_level_map(
        defaults["achievements"].get("gun_max_levels", {}),
        CANONICAL_GUN_NAMES,
    )
    defaults["achievements"]["haunting_max_levels"] = _normalize_level_map(
        defaults["achievements"].get("haunting_max_levels", {}),
        CANONICAL_HAUNTING_NAMES,
    )
    defaults["achievements"]["swarm_max_levels"] = _normalize_level_map(
        defaults["achievements"].get("swarm_max_levels", {}),
        CANONICAL_SWARM_NAMES,
    )
    levels_total_source = defaults["achievements"].get("levels_total_by_combo", {})
    if not isinstance(levels_total_source, dict) or not levels_total_source:
        levels_total_source = defaults["achievements"].get("levels_by_combo", {})
    defaults["achievements"]["levels_total_by_combo"] = _normalize_nonnegative_int_map(levels_total_source)
    secret_progress = dict(SECRET_PROGRESS_KEYS)
    loaded_secret_progress = defaults["achievements"].get("secret_progress", {})
    if isinstance(loaded_secret_progress, dict):
        for key, default_value in SECRET_PROGRESS_KEYS.items():
            try:
                secret_progress[key] = max(default_value, int(loaded_secret_progress.get(key, default_value)))
            except (TypeError, ValueError):
                secret_progress[key] = default_value
    defaults["achievements"]["secret_progress"] = secret_progress
    defaults["selected_loadout"] = _normalize_selected_loadout(
        defaults.get("selected_loadout", {}),
        fallback_body=default_selected_loadout()["body"],
        fallback_gun=default_selected_loadout()["gun"],
    )
    return defaults


def _normalize_name(name):
    return str(name).strip().lower()


def _normalize_level_map(level_map, canonical_names):
    normalized = {}
    for raw_name, raw_level in level_map.items():
        key = _normalize_name(raw_name)
        canonical_key = canonical_names.get(key, str(raw_name).strip())
        try:
            level_value = int(raw_level)
        except (TypeError, ValueError):
            level_value = 0
        normalized[canonical_key] = max(level_value, int(normalized.get(canonical_key, 0)))
    return normalized


def _normalize_nonnegative_int_map(values_map):
    normalized = {}
    if not isinstance(values_map, dict):
        return normalized

    for raw_name, raw_value in values_map.items():
        key = str(raw_name).strip()
        if not key:
            continue
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            value = 0
        normalized[key] = max(0, value)
    return normalized


def _canonicalize_name(name, canonical_names):
    return canonical_names.get(_normalize_name(name), str(name).strip())


def _write_store(data):
    data["updated_at"] = datetime.utcnow().isoformat() + "Z"
    with open(STATS_FILE_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def load_haunting_options():
    data = _load_store()
    hauntings = default_haunting_options()
    hauntings.update(data.get("options", {}).get("hauntings", {}))
    return {enemy_name: bool(hauntings.get(enemy_name, False)) for enemy_name in HAUNTING_OPTION_KEYS}


def save_haunting_options(haunting_options):
    data = _load_store()
    cleaned = default_haunting_options()
    for enemy_name in cleaned:
        cleaned[enemy_name] = bool(haunting_options.get(enemy_name, False))
    data.setdefault("options", {})["hauntings"] = cleaned
    _write_store(data)
    return cleaned


def load_swarm_options():
    data = _load_store()
    options = default_swarm_options()
    loaded_options = data.get("options", {}).get("swarm", {})
    if isinstance(loaded_options, dict):
        options["enabled"] = bool(loaded_options.get("enabled", False))
        fallback_enemy = loaded_options.get("enemy_type", options["enemy_type"])
        enemy_types = _normalize_swarm_enemy_types(
            loaded_options.get("enemy_types", []),
            fallback=[fallback_enemy],
        )
        options["enemy_types"] = enemy_types
        options["enemy_type"] = enemy_types[0]
    return options


def save_swarm_options(swarm_options):
    data = _load_store()
    cleaned = default_swarm_options()
    cleaned["enabled"] = bool(swarm_options.get("enabled", False))
    fallback_enemy = swarm_options.get("enemy_type", cleaned["enemy_type"])
    enemy_types = _normalize_swarm_enemy_types(
        swarm_options.get("enemy_types", []),
        fallback=[fallback_enemy],
    )
    cleaned["enemy_types"] = enemy_types
    cleaned["enemy_type"] = enemy_types[0]
    data.setdefault("options", {})["swarm"] = cleaned
    _write_store(data)
    return cleaned


def load_selected_loadout(default_body="Dasher", default_gun="Cannon"):
    data = _load_store()
    cleaned = _normalize_selected_loadout(
        data.get("selected_loadout", {}),
        fallback_body=default_body,
        fallback_gun=default_gun,
    )
    return cleaned


def save_selected_loadout(selected_body, selected_gun):
    data = _load_store()
    cleaned = _normalize_selected_loadout(
        {
            "body": selected_body,
            "gun": selected_gun,
        },
        fallback_body=default_selected_loadout()["body"],
        fallback_gun=default_selected_loadout()["gun"],
    )
    data["selected_loadout"] = cleaned
    _write_store(data)
    return cleaned


def load_suspended_run():
    data = _load_store()
    suspended_run = data.get("suspended_run", {})
    if isinstance(suspended_run, dict):
        return dict(suspended_run)
    return {}


def save_suspended_run(suspended_run):
    data = _load_store()
    data["suspended_run"] = dict(suspended_run) if isinstance(suspended_run, dict) else {}
    _write_store(data)


def clear_suspended_run():
    data = _load_store()
    data["suspended_run"] = {}
    _write_store(data)


def discard_active_run():
    data = _load_store()
    data["current_run"] = {}
    data["suspended_run"] = {}
    _write_store(data)


def _safe_value(value):
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    if isinstance(value, tuple):
        return [_safe_value(item) for item in value]
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    if hasattr(value, "x") and hasattr(value, "y"):
        return {"x": _safe_value(value.x), "y": _safe_value(value.y)}
    if hasattr(value, "__class__"):
        return value.__class__.__name__
    return str(value)


def snapshot_player(player):
    if player is None:
        return {}

    snapshot = {}
    for key, value in player.__dict__.items():
        if key.startswith("_"):
            continue
        if key == "gun":
            snapshot["gun"] = value.__class__.__name__
            continue
        snapshot[key] = _safe_value(value)

    snapshot["body"] = player.__class__.__name__
    return snapshot


def _update_best_run(best_run, run_snapshot):
    tracked = ["waves_spawned", "level_ups", "upgrades_chosen", "level_reached", "ticks_survived", "exp_held"]
    for metric in tracked:
        best_run[metric] = max(int(best_run.get(metric, 0)), int(run_snapshot.get(metric, 0)))


stats_paused = False


def record_enemy_kill(enemy_type):
    """Track enemy kills for achievements."""
    if stats_paused:
        return
    data = _load_store()
    enemy_kills = data["achievements"]["enemy_kills"]
    enemy_kills[enemy_type] = enemy_kills.get(enemy_type, 0) + 1
    _write_store(data)


def record_player_level(player_name, level):
    """Track max level reached with each player."""
    data = _load_store()
    player_levels = data["achievements"]["player_max_levels"]
    canonical_name = _canonicalize_name(player_name, CANONICAL_PLAYER_NAMES)
    current_max = int(player_levels.get(canonical_name, 0))
    if level > current_max:
        player_levels[canonical_name] = int(level)
        _write_store(data)


def record_gun_level(gun_name, level):
    """Track max level reached with each gun."""
    data = _load_store()
    gun_levels = data["achievements"]["gun_max_levels"]
    canonical_name = _canonicalize_name(gun_name, CANONICAL_GUN_NAMES)
    current_max = int(gun_levels.get(canonical_name, 0))
    if level > current_max:
        gun_levels[canonical_name] = int(level)
        _write_store(data)


def record_haunting_levels(active_hauntings, level):
    """Track max level reached while each haunting option is enabled."""
    if not isinstance(active_hauntings, dict):
        return

    data = _load_store()
    haunting_levels = data["achievements"]["haunting_max_levels"]
    updated = False
    level_value = int(level)

    for haunting_name in HAUNTING_OPTION_KEYS:
        if not bool(active_hauntings.get(haunting_name, False)):
            continue
        canonical_name = _canonicalize_name(haunting_name, CANONICAL_HAUNTING_NAMES)
        current_max = int(haunting_levels.get(canonical_name, 0))
        if level_value > current_max:
            haunting_levels[canonical_name] = level_value
            updated = True

    if updated:
        _write_store(data)


def record_swarm_level(swarm_options, level):
    """Track max level reached while swarm mode is enabled for selected enemy types."""
    if not isinstance(swarm_options, dict):
        return
    if not bool(swarm_options.get("enabled", False)):
        return

    selected_swarm_types = _normalize_swarm_enemy_types(
        swarm_options.get("enemy_types", []),
        fallback=[swarm_options.get("enemy_type", SWARM_ENEMY_KEYS[0])],
    )

    data = _load_store()
    swarm_levels = data["achievements"]["swarm_max_levels"]
    level_value = int(level)
    updated = False

    for swarm_enemy in selected_swarm_types:
        canonical_name = _canonicalize_name(swarm_enemy, CANONICAL_SWARM_NAMES)
        current_max = int(swarm_levels.get(canonical_name, 0))
        if level_value > current_max:
            swarm_levels[canonical_name] = level_value
            updated = True

    if updated:
        _write_store(data)


def record_waves_with_combo(player_name, gun_name, waves):
    """Track waves survived with each player/gun combination."""
    data = _load_store()
    updated = _update_combo_waves_achievement(data["achievements"], {
        "body": player_name,
        "gun": gun_name,
        "waves_spawned": waves,
    })
    if updated:
        _write_store(data)


def record_secret_progress(secret_key, amount=1):
    """Increment a secret achievement counter by a positive amount."""
    if stats_paused:
        return
    if secret_key not in SECRET_PROGRESS_KEYS:
        return
    try:
        amount_value = int(amount)
    except (TypeError, ValueError):
        return
    if amount_value <= 0:
        return

    data = _load_store()
    secret_progress = data["achievements"].setdefault("secret_progress", dict(SECRET_PROGRESS_KEYS))
    current_value = int(secret_progress.get(secret_key, SECRET_PROGRESS_KEYS[secret_key]))
    secret_progress[secret_key] = current_value + amount_value
    _write_store(data)


def record_secret_max(secret_key, value):
    """Set a secret achievement value to the highest seen value."""
    if stats_paused:
        return
    if secret_key not in SECRET_PROGRESS_KEYS:
        return
    try:
        value_int = int(value)
    except (TypeError, ValueError):
        return

    data = _load_store()
    secret_progress = data["achievements"].setdefault("secret_progress", dict(SECRET_PROGRESS_KEYS))
    current_value = int(secret_progress.get(secret_key, SECRET_PROGRESS_KEYS[secret_key]))
    if value_int > current_value:
        secret_progress[secret_key] = value_int
        _write_store(data)


def _update_combo_waves_achievement(achievements, run_snapshot):
    player_name = str(run_snapshot.get("body", "")).strip()
    gun_name = str(run_snapshot.get("gun", "")).strip()
    if not player_name or not gun_name:
        return False

    waves = max(0, int(run_snapshot.get("waves_spawned", 0)))
    combo_key = f"{player_name}_{gun_name}"
    waves_combos = achievements["waves_by_combo"]
    current_max = int(waves_combos.get(combo_key, 0))
    if waves > current_max:
        waves_combos[combo_key] = waves
        return True
    return False


def _update_combo_levels_achievement(achievements, run_snapshot):
    player_name = str(run_snapshot.get("body", "")).strip()
    gun_name = str(run_snapshot.get("gun", "")).strip()
    if not player_name or not gun_name:
        return False

    level_reached = max(0, int(run_snapshot.get("level_reached", 0)))
    combo_key = f"{player_name}_{gun_name}"
    levels_combos = achievements["levels_by_combo"]
    current_max = int(levels_combos.get(combo_key, 0))
    if level_reached > current_max:
        levels_combos[combo_key] = level_reached
        return True
    return False


def _increment_combo_total_levels(achievements, run_snapshot, amount=1):
    player_name = str(run_snapshot.get("body", "")).strip()
    gun_name = str(run_snapshot.get("gun", "")).strip()
    if not player_name or not gun_name:
        return False

    try:
        amount_value = int(amount)
    except (TypeError, ValueError):
        return False
    if amount_value <= 0:
        return False

    combo_key = f"{player_name}_{gun_name}"
    levels_totals = achievements["levels_total_by_combo"]
    current_total = int(levels_totals.get(combo_key, 0))
    levels_totals[combo_key] = current_total + amount_value
    return True


def save_run_checkpoint(event, run_snapshot, player):
    data = _load_store()

    totals = data["totals"]
    if event == "run_start":
        totals["runs_started"] += 1
    elif event == "wave":
        totals["waves_spawned"] += 1
    elif event == "level_up":
        totals["level_ups"] += 1
    elif event == "upgrade":
        totals["upgrades_chosen"] += 1
    elif event == "run_end":
        totals["runs_finished"] += 1

    if event in ("wave", "suspend", "run_end"):
        _update_combo_waves_achievement(data["achievements"], run_snapshot)

    if event in ("level_up", "wave", "suspend", "run_end"):
        _update_combo_levels_achievement(data["achievements"], run_snapshot)

    if event == "level_up":
        _increment_combo_total_levels(data["achievements"], run_snapshot, amount=1)

    current_run_data = dict(run_snapshot)
    current_run_data["last_event"] = event
    current_run_data["player_body"] = run_snapshot.get("body")
    current_run_data["player_gun"] = run_snapshot.get("gun")

    _update_best_run(data["best_run"], run_snapshot)
    data["last_player_snapshot"] = snapshot_player(player)

    if event == "run_end":
        data["last_run"] = current_run_data
        data["current_run"] = {}
        data["suspended_run"] = {}
    else:
        data["current_run"] = current_run_data

    _write_store(data)
