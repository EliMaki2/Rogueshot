import os
import pygame
import math
import random
import subprocess
import sys
import traceback
import Player.player_body as player_body
from Player.bullets import Bullet
import Player.bullets as bullets_file
import Enemies.enemies as enemy_file
import Enemies.particles as particles_file
import Enemies.drops as drops_file
import Background.upgrades as upgrade_file
import Background.menus as menus_file
import Background.ui_assets as ui_assets
import Background.run_stats as run_stats
import Background.walls as walls_file
import Background.maps as maps_file
from Background.logic import MapRuntime
from Background.wave_overlay import WaveOverlay
from Background.tutorials import TUTORIALS, TutorialRun
from Background.ui_assets import setup_ui, Color, MakeButton, Fonts, MouseClick, Width, Height

if "--map-editor" in sys.argv:
    import map_editor
    map_editor.App().run()
    sys.exit(0)

pygame.init()

# Setup UI (screen, scaling, fonts, colors)
setup_ui()
stain_overlay = pygame.Surface(ui_assets.screen.get_size()).convert()
stain_capture = pygame.Surface(ui_assets.screen.get_size()).convert()
stain_overlay.fill((0, 0, 0))
stain_refresh_rate = 6
stain_draw_alpha = 40
stain_fade_strength = 244
stain_blur_offsets = (
    (0, 0, 14),
    (1, 0, 8),
    (-1, 0, 8),
)

wave_overlay = WaveOverlay(start_max_age=150)


def _draw_stain_overlay():
    stain_overlay.set_alpha(stain_draw_alpha)
    ui_assets.screen.blit(stain_overlay, (0, 0))


def _refresh_stain_overlay():
    stain_overlay.fill((stain_fade_strength, stain_fade_strength, stain_fade_strength), special_flags=pygame.BLEND_RGB_MULT)
    stain_capture.blit(ui_assets.screen, (0, 0))
    for offset_x, offset_y, alpha in stain_blur_offsets:
        stain_capture.set_alpha(alpha)
        stain_overlay.blit(stain_capture, (offset_x, offset_y))

debug = True
running = True
Display = "MainMenu"
pressed_keys = []
keydown_events = []
mouse_x, mouse_y = 0, 0
game_ticks = 0
mouse_pressed = False

tutorial_selected = 0
tutorial_scroll_offset = 0
tutorial_scroll_input = 0
tutorial_notice = ""
tutorial_run = None
achievements_selected = 0
achievements_scroll_offset = 0
achievements_scroll_input = 0
achievements_category = "Player/Gun"
achievements_selected_by_category = {
    "Player/Gun": 0,
    "Haunting": 0,
    "Swarm": 0,
    "Slayer": 0,
    "Level": 0,
    "Secret": 0,
}
achievements_scroll_by_category = {
    "Player/Gun": 0,
    "Haunting": 0,
    "Swarm": 0,
    "Slayer": 0,
    "Level": 0,
    "Secret": 0,
}
selected_body = "Dasher"
selected_gun = "Cannon"
selected_upgrade_index = 0
player = None
level_card = None
run_snapshot = None
wave_xp_drop_last_spawn = None
level_reqirement = 10
level = 1
display_level_ratio = 0
haunting_options = run_stats.load_haunting_options()
enemy_file.set_haunting_options(haunting_options)
swarm_options = run_stats.load_swarm_options()
drops_file.update_exp_bonus(haunting_options, swarm_options)
options_tab = "Haunting"
options_scroll_input = 0
haunting_scroll_offset = 0
swarm_type_scroll_offset = 0
customisations_scroll_input = 0
body_scroll_offset = 0
gun_scroll_offset = 0
selected_loadout = run_stats.load_selected_loadout(selected_body, selected_gun)
selected_body = selected_loadout.get("body", selected_body)
selected_gun = selected_loadout.get("gun", selected_gun)


def _active_spawn_zones():
    if current_map is None:
        return []
    return map_runtime.active_spawn_zones() if map_runtime is not None else []


def _random_spawn_position():
    zones = _active_spawn_zones()
    if zones:
        zone = random.choice(zones)
        h_scale, v_scale = ui_assets.Horizontal_Scale, ui_assets.Vertical_Scale
        return (
            random.uniform(zone.x, zone.x + zone.width) * h_scale,
            random.uniform(zone.y, zone.y + zone.height) * v_scale,
        )
    return (
        random.randint(-50, round(ui_assets.Horizontal_Scale * Width + 50)),
        random.randint(-50, round(ui_assets.Vertical_Scale * Height + 50)),
    )


def _difficulty_multiplier():
    if tutorial_run is not None:
        return 1.0
    return DIFFICULTY_MULTIPLIERS.get(run_difficulty, 1.0)


def _create_enemy_by_name(enemy_name, tick_value, position=None):
    spawn_x, spawn_y = position if position is not None else _random_spawn_position()
    spawn_time = round(tick_value / 100)

    create_enemy_map = {
        "Dasher": enemy_file.Dasher,
        "Blaster": enemy_file.Blaster,
        "Ghost": enemy_file.Ghost,
        "Spiker": enemy_file.Spiker,
        "Commander": enemy_file.Commander,
        "Guardian": enemy_file.Guardian,
        "Warper": enemy_file.Warper,
        "Turret": enemy_file.Turret,
        "Chaser": enemy_file.Chaser,
        "Shatterking": enemy_file.Shatterking,
    }

    enemy = create_enemy_map.get(enemy_name, enemy_file.Chaser)(spawn_x, spawn_y, spawn_time)
    health_scale = _difficulty_multiplier()
    if health_scale != 1.0:
        enemy.maxHealth = max(1, round(enemy.maxHealth * health_scale))
        enemy.health = enemy.maxHealth
    return enemy


def _spawn_offscreen(enemy):
    if _active_spawn_zones():
        return
    while 0 < enemy.x < ui_assets.Horizontal_Scale * Width and 0 < enemy.y < ui_assets.Vertical_Scale * Height:
        enemy.x, enemy.y = _random_spawn_position()


def _create_wave_enemy(enemy_name, tick_value, position=None):
    enemy = _create_enemy_by_name(enemy_name, tick_value, position)
    _spawn_offscreen(enemy)
    return enemy


def _roll_upgrade(name=None):
    pool = upgrade_file.total_Upgrades
    named = next((u for u in pool if u.name == name), None) if name else None
    while True:
        upgrade = named or random.choice(pool)
        upgrade.randomize_strength(upgrade_file.luck)
        if upgrade.strength >= upgrade.minimum:
            return upgrade


def _tutorial_levels():
    return tutorial_run.tutorial.get("levels", []) if tutorial_run is not None else []


def _roll_wave_enemy_name(tick_value, allow_early_spiker=False):
    temp = random.randint(0, 19)
    if temp <= 6:
        return "Chaser"
    if temp in (7, 8):
        return "Dasher"
    if temp in (9, 10):
        return "Blaster"
    if temp in (11, 12):
        return "Ghost"
    if temp in (13, 14):
        if tick_value > 1000:
            return "Turret"
        return "Chaser"
    if temp == 15:
        if tick_value > 1800:
            return "Commander"
        return "Chaser"
    if temp == 16:
        if allow_early_spiker or tick_value > 2400:
            return "Spiker"
        return "Chaser"
    if temp == 17:
        if tick_value > 3000:
            return "Guardian"
        return "Chaser"
    if temp == 18:
        if tick_value > 3600:
            return "Warper"
        return "Chaser"
    if temp == 19:
        if tick_value > 4200:
            return "Shatterking"
        return "Chaser"
    return "Chaser"


def _spawn_wave(wave_count, tick_value, allow_early_spiker=False):
    wave_count = max(1, round(wave_count * _difficulty_multiplier()))
    for i in range(wave_count):
        enemy_name = _roll_wave_enemy_name(tick_value, allow_early_spiker)
        enemy = _create_enemy_by_name(enemy_name, tick_value)
        _spawn_offscreen(enemy)

    if swarm_options.get("enabled", False):
        selected_swarm_types = [
            enemy_name.strip()
            for enemy_name in swarm_options.get("enemy_types", [])
            if isinstance(enemy_name, str) and enemy_name.strip()
        ]
        if not selected_swarm_types:
            fallback_enemy_type = str(swarm_options.get("enemy_type", "Chaser"))
            selected_swarm_types = [fallback_enemy_type]
        extra_count_per_type = int(wave_count * 0.5)
        for swarm_enemy_name in dict.fromkeys(selected_swarm_types):
            for i in range(extra_count_per_type):
                enemy = _create_enemy_by_name(swarm_enemy_name, tick_value)
                _spawn_offscreen(enemy)


def _record_offscreen_secret_progress(player_obj):
    screen_width = Width * ui_assets.Horizontal_Scale
    screen_height = Height * ui_assets.Vertical_Scale
    overflow = max(
        0,
        -player_obj.x,
        player_obj.x - screen_width,
        -player_obj.y,
        player_obj.y - screen_height,
    )
    if overflow > 0:
        run_stats.record_secret_max("offscreen_distance_max", round(overflow))


def apply_selected_loadout(current_player=None):
    if current_player is None:
        new_player = player_body.create_player(selected_body, x=Width / 2, y=Height / 2, health=10)
        return player_body.equip_gun(new_player, selected_gun)
    return player_body.rebuild_player(current_player, selected_body, selected_gun)


def draw_level_hud(current_level, level_ratio, display_ratio):
    level_box = (25 * ui_assets.Horizontal_Scale, 560 * ui_assets.Vertical_Scale, 90 * ui_assets.Horizontal_Scale, 28 * ui_assets.Vertical_Scale)
    bar_x = 125 * ui_assets.Horizontal_Scale
    bar_y = 565 * ui_assets.Vertical_Scale
    bar_width = 825 * ui_assets.Horizontal_Scale
    bar_height = 16 * ui_assets.Vertical_Scale
    spawn_bar_y = 585 * ui_assets.Vertical_Scale
    spawn_bar_height = 10 * ui_assets.Vertical_Scale

    pygame.draw.rect(ui_assets.screen, (35, 35, 35), level_box, border_radius=4)
    pygame.draw.rect(ui_assets.screen, (90, 90, 90), level_box, 2, border_radius=4)
    level_text = Fonts.bold.render(f"Lv {current_level}", True, (245, 245, 245))
    level_text_rect = level_text.get_rect(center=((25 + 45) * ui_assets.Horizontal_Scale, (560 + 14) * ui_assets.Vertical_Scale))
    ui_assets.screen.blit(level_text, level_text_rect)

    pygame.draw.rect(ui_assets.screen, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height), border_radius=4)
    pygame.draw.rect(ui_assets.screen, (50, 50, 200), (bar_x, bar_y, bar_width * display_ratio, bar_height), border_radius=4)
    progress_text = Fonts.tiny.render(f"{int(level_ratio * 100)}%", True, (240, 240, 240))
    progress_text_rect = progress_text.get_rect(midright=((125 + 825 - 8) * ui_assets.Horizontal_Scale, (565 + 8) * ui_assets.Vertical_Scale))
    ui_assets.screen.blit(progress_text, progress_text_rect)


def draw_spawn_hud(game_ticks_value):
    bar_x = 125 * ui_assets.Horizontal_Scale
    bar_width = 825 * ui_assets.Horizontal_Scale
    spawn_bar_y = 585 * ui_assets.Vertical_Scale
    spawn_bar_height = 10 * ui_assets.Vertical_Scale
    spawn_cycle = 600
    ticks_until_spawn = spawn_cycle - (game_ticks_value % spawn_cycle)
    spawn_ratio = ticks_until_spawn / spawn_cycle

    if spawn_ratio > 0.66:
        bar_color = (80, 170, 90)
    elif spawn_ratio > 0.33:
        bar_color = (220, 170, 60)
    else:
        bar_color = (220, 80, 70)

    pygame.draw.rect(ui_assets.screen, (35, 30, 20), (bar_x, spawn_bar_y, bar_width, spawn_bar_height), border_radius=4)
    pygame.draw.rect(ui_assets.screen, bar_color, (bar_x, spawn_bar_y, bar_width * spawn_ratio, spawn_bar_height), border_radius=4)
    spawn_text = Fonts.tiny.render(f"Next spawn in {ticks_until_spawn // 60}:{ticks_until_spawn % 60:02d}", True, (245, 230, 200))
    spawn_text_rect = spawn_text.get_rect(midleft=((125 + 8) * ui_assets.Horizontal_Scale, (585 + 5) * ui_assets.Vertical_Scale))
    ui_assets.screen.blit(spawn_text, spawn_text_rect)


def build_level_card(events):
    if not events:
        return None
    if len(events) == 1:
        event = events[0]
        title = event["title"]
        description_lines = [event["description"]]
        color = event["color"]
    else:
        title = "Level Milestone"
        description_lines = [event["description"] for event in events]
        color = events[0]["color"]
    return {
        "title": title,
        "description_lines": description_lines,
        "color": color,
        "events": events,
    }


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _restore_player_from_snapshot(player_snapshot, fallback_body, fallback_gun):
    if not isinstance(player_snapshot, dict):
        return None

    body_name = str(player_snapshot.get("body", fallback_body))
    gun_name = str(player_snapshot.get("gun", fallback_gun))
    x = _safe_float(player_snapshot.get("x", Width / 2), Width / 2)
    y = _safe_float(player_snapshot.get("y", Height / 2), Height / 2)
    size = _safe_int(player_snapshot.get("size", 20), 20)
    max_health = _safe_int(player_snapshot.get("max_health", 10), 10)
    health = _safe_int(player_snapshot.get("health", max_health), max_health)
    restored_player = player_body.create_player(body_name, x=x, y=y, size=size, health=max(1, max_health))
    restored_player = player_body.equip_gun(restored_player, gun_name)

    for key, value in player_snapshot.items():
        if key in ("body", "gun"):
            continue
        if key == "velocity" and isinstance(value, dict):
            restored_player.velocity = player_body.Vector(
                _safe_float(value.get("x", 0), 0),
                _safe_float(value.get("y", 0), 0),
            )
            continue
        if key in ("color", "bullet_color") and isinstance(value, list):
            value = tuple(value)
        if hasattr(restored_player, key):
            setattr(restored_player, key, value)

    restored_player.max_health = max(1, _safe_int(getattr(restored_player, "max_health", max_health), max_health))
    restored_player.health = max(0, min(restored_player.max_health, _safe_int(getattr(restored_player, "health", health), health)))
    return restored_player


current_map = None
map_runtime = None
DIFFICULTY_MULTIPLIERS = {1: 0.7, 2: 1.0, 3: 1.4, 4: 1.8, 5: 2.3}
run_difficulty = 2
selected_map_name = None
setup_map_index = 0
setup_difficulty = 2
tutorial_end_requested = False
ability_used = False
ability_cooldown_attrs = ("dash_cooldown", "nova_cooldown", "slime_cooldown")


def _ability_cooldown_total(player_obj):
    return sum(getattr(player_obj, name, 0) for name in ability_cooldown_attrs)


def _build_map_runtime():
    global map_runtime, tutorial_end_requested
    tutorial_end_requested = False
    if current_map is None:
        map_runtime = None
        return
    map_runtime = MapRuntime(
        current_map, ui_assets.Horizontal_Scale, ui_assets.Vertical_Scale, _create_enemy_by_name, _create_wave_enemy
    )
    map_runtime.install_walls()


def _create_run_walls(reroll=True):
    """Apply the current map's objects (choosing a new random preset if `reroll`).

    Returns the player's start position for the map.
    """
    global current_map
    h_scale, v_scale = ui_assets.Horizontal_Scale, ui_assets.Vertical_Scale
    if reroll or current_map is None:
        current_map = maps_file.load_map_by_name(selected_map_name) if selected_map_name else None
        if current_map is None:
            current_map = maps_file.load_random_map()
    _build_map_runtime()
    if current_map is None:
        walls_file.set_walls(walls_file.create_plus_walls(h_scale * Width / 2, v_scale * Height / 2))
        return Width / 2, Height / 2
    return current_map.player_start[0] * h_scale, current_map.player_start[1] * v_scale

def _save_suspended_run_state():
    if not active_run or run_snapshot is None or player is None:
        return

    run_stats.update_runtime(run_snapshot, game_ticks, level, drops_file.exp)
    run_stats.save_run_checkpoint("suspend", run_snapshot, player)
    run_stats.save_suspended_run(
        {
            "selected_body": selected_body,
            "selected_gun": selected_gun,
            "game_ticks": int(game_ticks),
            "level": int(level),
            "level_reqirement": int(level_reqirement),
            "display_level_ratio": float(display_level_ratio),
            "exp": int(drops_file.exp),
            "run_snapshot": dict(run_snapshot),
            "player_snapshot": run_stats.snapshot_player(player),
            "walls": walls_file.walls_to_list(),
            "map_name": current_map.name if current_map is not None else None,
            "difficulty": run_difficulty,
            "map_state": map_runtime.snapshot() if map_runtime is not None else None,
        }
    )


def _clear_arena():
    enemy_file.enemies.clear()
    particles_file.particles.clear()
    drops_file.exp = 0
    drops_file.drops.clear()
    bullets_file.bullets.clear()
    walls_file.walls.clear()


def _start_tutorial(tutorial_index):
    # Tutorials use a fixed preset player and never touch saved runs or stats.
    global tutorial_run, player, game_ticks, level, level_reqirement, display_level_ratio, level_card, wave_xp_drop_last_spawn, current_map
    tutorial = TUTORIALS[tutorial_index]
    _clear_arena()
    run_stats.stats_paused = True
    enemy_file.set_haunting_options({})
    tutorial_run = TutorialRun(tutorial)
    current_map = maps_file.load_map_by_name(tutorial["map"])
    start_x, start_y = _create_run_walls(reroll=False)
    if current_map is None:
        start_x, start_y = ui_assets.Horizontal_Scale * Width * 0.15, ui_assets.Vertical_Scale * Height * 0.5
    player = player_body.create_player(tutorial["body"], x=start_x, y=start_y, health=tutorial["health"])
    player = player_body.equip_gun(player, tutorial["gun"])
    player.alive = True
    game_ticks = 1
    level = 1
    level_reqirement = maps_file.level_requirement(tutorial.get("levels", []), 1)
    display_level_ratio = 0
    level_card = None
    wave_xp_drop_last_spawn = None


def _exit_tutorial():
    global tutorial_run, player, game_ticks, display_level_ratio
    tutorial_run = None
    player = None
    game_ticks = 0
    display_level_ratio = 0
    _clear_arena()
    if active_run:
        _create_run_walls(reroll=False)
    run_stats.stats_paused = False
    enemy_file.set_haunting_options(haunting_options)


active_run = False
suspended_run_state = run_stats.load_suspended_run()
if suspended_run_state:
    selected_body = str(suspended_run_state.get("selected_body", selected_body))
    selected_gun = str(suspended_run_state.get("selected_gun", selected_gun))
    game_ticks = max(1, _safe_int(suspended_run_state.get("game_ticks", game_ticks), game_ticks))
    level = max(1, _safe_int(suspended_run_state.get("level", level), level))
    level_reqirement = max(1, _safe_int(suspended_run_state.get("level_reqirement", level_reqirement), level_reqirement))
    display_level_ratio = min(1.0, max(0.0, _safe_float(suspended_run_state.get("display_level_ratio", display_level_ratio), display_level_ratio)))
    drops_file.exp = max(0, _safe_int(suspended_run_state.get("exp", 0), 0))

    loaded_snapshot = suspended_run_state.get("run_snapshot", {})
    if isinstance(loaded_snapshot, dict) and loaded_snapshot:
        run_snapshot = dict(loaded_snapshot)
    else:
        run_snapshot = run_stats.create_run_snapshot(selected_body, selected_gun)
        run_stats.update_runtime(run_snapshot, game_ticks, level, drops_file.exp)

    player = _restore_player_from_snapshot(suspended_run_state.get("player_snapshot", {}), selected_body, selected_gun)
    if player is None:
        player = apply_selected_loadout()
        player.alive = True

    run_difficulty = _safe_int(suspended_run_state.get("difficulty", 2), 2)
    if run_difficulty not in DIFFICULTY_MULTIPLIERS:
        run_difficulty = 2

    if suspended_run_state.get("map_name"):
        current_map = maps_file.load_map_by_name(suspended_run_state["map_name"])
    if current_map is not None:
        _create_run_walls(reroll=False)
        if map_runtime is not None:
            map_runtime.restore(suspended_run_state.get("map_state"))
    elif "walls" in suspended_run_state:
        walls_file.set_walls(walls_file.walls_from_list(suspended_run_state.get("walls")))
    else:
        _create_run_walls()

    active_run = True
clock = pygame.time.Clock()
while running:
    try:
        keydown_events = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pressed = True
            if event.type == pygame.MOUSEBUTTONUP:
                mouse_pressed = False
            if event.type == pygame.MOUSEMOTION:
                mouse_x, mouse_y = event.pos
                mouse_x = mouse_x / ui_assets.Horizontal_Scale  # Scale the mouse x-coordinate back to the original coordinate system
                mouse_y = mouse_y / ui_assets.Vertical_Scale    # Scale the mouse y-coordinate back to the original coordinate system
            if event.type == pygame.MOUSEWHEEL and Display == "Tutorial":
                tutorial_scroll_input += event.y
            if event.type == pygame.MOUSEWHEEL and Display == "Achievements":
                achievements_scroll_input += event.y
            if event.type == pygame.MOUSEWHEEL and Display == "Options":
                options_scroll_input += event.y
            if event.type == pygame.MOUSEWHEEL and Display == "Customisations":
                customisations_scroll_input += event.y
            if event.type == pygame.KEYDOWN:
                pressed_keys.append(event.key)
                keydown_events.append(event.key)
            if event.type == pygame.KEYUP:
                if event.key in pressed_keys:
                    pressed_keys.remove(event.key)
            # Handle custom bullet sound events
            if pygame.USEREVENT + 10 <= event.type < pygame.USEREVENT + 30:
                from Player.gun import Gun
                if Gun.shoot_sound:
                    import random
                    Gun.shoot_sound.set_volume(random.uniform(0.2, 0.7))
                    Gun.shoot_sound.play()

        if Display == "MainMenu":
            buttons = menus_file.main_menu(active_run, mouse_x, mouse_y, mouse_pressed, MouseClick)
            # Use .get() to avoid KeyError if a button is missing
            if active_run:
                if MouseClick(buttons.get('StartButton'), mouse_x, mouse_y, mouse_pressed):
                    Display = "Game"
                end_run_button = buttons.get('EndRunButton')
                if end_run_button and MouseClick(end_run_button, mouse_x, mouse_y, mouse_pressed):
                    active_run = False
                    game_ticks = 0
                    level = 1
                    level_reqirement = 10
                    display_level_ratio = 0
                    level_card = None
                    run_snapshot = None
                    player = None
                    enemy_file.enemies.clear()
                    particles_file.particles.clear()
                    drops_file.exp = 0
                    drops_file.drops.clear()
                    bullets_file.bullets.clear()
                    wave_xp_drop_last_spawn = None
                    run_stats.discard_active_run()
                    mouse_pressed = False
            else:
                if MouseClick(buttons.get('StartButton'), mouse_x, mouse_y, mouse_pressed):
                    Display = "RunSetup"
                    setup_map_index = 0
                    setup_difficulty = 2
                    mouse_pressed = False
            if MouseClick(buttons.get('ExitButton'), mouse_x, mouse_y, mouse_pressed):
                running = False
            if MouseClick(buttons.get('OptionsButton'), mouse_x, mouse_y, mouse_pressed):
                Display = "Options"
                mouse_pressed = False
            if MouseClick(buttons.get('TutorialButton'), mouse_x, mouse_y, mouse_pressed):
                Display = "Tutorial"
                tutorial_notice = ""
                mouse_pressed = False
            if MouseClick(buttons.get('AchievementsButton'), mouse_x, mouse_y, mouse_pressed):
                Display = "Achievements"
                mouse_pressed = False
            if MouseClick(buttons.get('CustomisationsButton'), mouse_x, mouse_y, mouse_pressed):
                Display = "Customisations"
                mouse_pressed = False
            if MouseClick(buttons.get('MapEditorButton'), mouse_x, mouse_y, mouse_pressed):
                if getattr(sys, "frozen", False):
                    subprocess.Popen([sys.executable, "--map-editor"])
                else:
                    project_dir = os.path.dirname(os.path.abspath(__file__))
                    subprocess.Popen(
                        [sys.executable, os.path.join(project_dir, "map_editor.py")],
                        cwd=project_dir,
                    )
                mouse_pressed = False
        elif Display == "Options":
            option_buttons = menus_file.options_menu(
                haunting_options,
                swarm_options,
                options_tab,
                haunting_scroll_offset,
                swarm_type_scroll_offset,
                options_scroll_input,
            )
            options_scroll_input = 0
            haunting_scroll_offset = option_buttons.get("HauntingScrollOffset", haunting_scroll_offset)
            swarm_type_scroll_offset = option_buttons.get("SwarmTypeScrollOffset", swarm_type_scroll_offset)
            if MouseClick(option_buttons["Back"], mouse_x, mouse_y, mouse_pressed):
                Display = "MainMenu"
                mouse_pressed = False
            if MouseClick(option_buttons["TabButtons"]["Haunting"], mouse_x, mouse_y, mouse_pressed):
                options_tab = "Haunting"
                mouse_pressed = False
            elif MouseClick(option_buttons["TabButtons"]["Swarm"], mouse_x, mouse_y, mouse_pressed):
                options_tab = "Swarm"
                mouse_pressed = False
            for enemy_name, button in option_buttons["ToggleButtons"].items():
                if MouseClick(button, mouse_x, mouse_y, mouse_pressed):
                    haunting_options[enemy_name] = not haunting_options.get(enemy_name, False)
                    haunting_options = run_stats.save_haunting_options(haunting_options)
                    enemy_file.set_haunting_options(haunting_options)
                    drops_file.update_exp_bonus(haunting_options, swarm_options)
                    mouse_pressed = False
                    break
            swarm_enabled_button = option_buttons.get("SwarmEnabledButton")
            if swarm_enabled_button and MouseClick(swarm_enabled_button, mouse_x, mouse_y, mouse_pressed):
                swarm_options["enabled"] = not swarm_options.get("enabled", False)
                swarm_options = run_stats.save_swarm_options(swarm_options)
                drops_file.update_exp_bonus(haunting_options, swarm_options)
                mouse_pressed = False
            for enemy_name, button in option_buttons.get("EnemyTypeButtons", {}).items():
                if MouseClick(button, mouse_x, mouse_y, mouse_pressed):
                    selected_swarm_types = list(swarm_options.get("enemy_types", []))
                    if enemy_name in selected_swarm_types:
                        selected_swarm_types.remove(enemy_name)
                    else:
                        selected_swarm_types.append(enemy_name)

                    swarm_options["enemy_types"] = selected_swarm_types
                    if selected_swarm_types:
                        swarm_options["enemy_type"] = selected_swarm_types[0]
                    swarm_options = run_stats.save_swarm_options(swarm_options)
                    drops_file.update_exp_bonus(haunting_options, swarm_options)
                    mouse_pressed = False
                    break
        
        elif Display == "Tutorial":
            tutorial_buttons = menus_file.tutorial_menu(tutorial_selected, tutorial_scroll_offset, tutorial_scroll_input, tutorial_notice)
            tutorial_scroll_input = 0
            tutorial_scroll_offset = tutorial_buttons['ScrollOffset']
            tutorial_selected = tutorial_buttons['SelectedIndex']

            if MouseClick(tutorial_buttons['Back'], mouse_x, mouse_y, mouse_pressed):
                Display = "MainMenu"
                mouse_pressed = False
            elif MouseClick(tutorial_buttons['RunButton'], mouse_x, mouse_y, mouse_pressed):
                mouse_pressed = False
                if active_run:
                    tutorial_notice = "End your current run before starting a tutorial"
                else:
                    _start_tutorial(tutorial_selected)
                    Display = "Game"
            else:
                for entry_button in tutorial_buttons['EntryButtons']:
                    if MouseClick(entry_button['button'], mouse_x, mouse_y, mouse_pressed):
                        tutorial_selected = entry_button['index']
                        tutorial_notice = ""
                        mouse_pressed = False
                        break

        elif Display == "Achievements":
            achievement_buttons = menus_file.achievements_menu(
                achievements_selected_by_category.get(achievements_category, achievements_selected),
                achievements_scroll_by_category.get(achievements_category, achievements_scroll_offset),
                achievements_scroll_input,
                achievements_category,
            )
            achievements_scroll_input = 0
            achievements_category = achievement_buttons.get('Category', achievements_category)
            achievements_scroll_offset = achievement_buttons['ScrollOffset']
            achievements_selected = achievement_buttons['SelectedIndex']
            achievements_scroll_by_category[achievements_category] = achievements_scroll_offset
            achievements_selected_by_category[achievements_category] = achievements_selected

            if MouseClick(achievement_buttons['Back'], mouse_x, mouse_y, mouse_pressed):
                Display = "MainMenu"
                mouse_pressed = False
            for category_name, tab_button in achievement_buttons.get('TabButtons', {}).items():
                if MouseClick(tab_button, mouse_x, mouse_y, mouse_pressed):
                    achievements_category = category_name
                    achievements_selected = achievements_selected_by_category.get(achievements_category, 0)
                    achievements_scroll_offset = achievements_scroll_by_category.get(achievements_category, 0)
                    mouse_pressed = False
                    break
            for entry_button in achievement_buttons['EntryButtons']:
                if MouseClick(entry_button['button'], mouse_x, mouse_y, mouse_pressed):
                    achievements_selected = entry_button['index']
                    achievements_selected_by_category[achievements_category] = achievements_selected
                    mouse_pressed = False
                    break

        elif Display == "Customisations":
            customisation_buttons = menus_file.customisations_menu(
                MouseClick,
                selected_body,
                selected_gun,
                body_scroll_offset,
                gun_scroll_offset,
                customisations_scroll_input,
                mouse_x,
                mouse_y,
            )
            customisations_scroll_input = 0
            body_scroll_offset = customisation_buttons.get('BodyScrollOffset', body_scroll_offset)
            gun_scroll_offset = customisation_buttons.get('GunScrollOffset', gun_scroll_offset)
            if MouseClick(customisation_buttons['Back'], mouse_x, mouse_y, mouse_pressed):
                Display = "MainMenu"
                mouse_pressed = False
            for body_name, button in customisation_buttons['BodyButtons'].items():
                if MouseClick(button, mouse_x, mouse_y, mouse_pressed):
                    if selected_body != body_name:
                        selected_body = body_name
                        selected_loadout = run_stats.save_selected_loadout(selected_body, selected_gun)
                        selected_body = selected_loadout.get("body", selected_body)
                        selected_gun = selected_loadout.get("gun", selected_gun)
                    if active_run and player is not None:
                        player = apply_selected_loadout(player)
                    mouse_pressed = False
                    break
            for gun_name, button in customisation_buttons['GunButtons'].items():
                if MouseClick(button, mouse_x, mouse_y, mouse_pressed):
                    if selected_gun != gun_name:
                        selected_gun = gun_name
                        selected_loadout = run_stats.save_selected_loadout(selected_body, selected_gun)
                        selected_body = selected_loadout.get("body", selected_body)
                        selected_gun = selected_loadout.get("gun", selected_gun)
                    if active_run and player is not None:
                        player = apply_selected_loadout(player)
                    mouse_pressed = False
                    break
        
        elif Display == "RunSetup":
            setup_map_options = ["Random"] + maps_file.list_playable_map_names()
            setup_map_index %= len(setup_map_options)
            setup_buttons = menus_file.run_setup_menu(
                setup_map_options, setup_map_index, setup_difficulty, selected_body, selected_gun
            )
            if MouseClick(setup_buttons['Back'], mouse_x, mouse_y, mouse_pressed):
                Display = "MainMenu"
                mouse_pressed = False
            elif MouseClick(setup_buttons['MapPrev'], mouse_x, mouse_y, mouse_pressed):
                setup_map_index = (setup_map_index - 1) % len(setup_map_options)
                mouse_pressed = False
            elif MouseClick(setup_buttons['MapNext'], mouse_x, mouse_y, mouse_pressed):
                setup_map_index = (setup_map_index + 1) % len(setup_map_options)
                mouse_pressed = False
            elif MouseClick(setup_buttons['StartButton'], mouse_x, mouse_y, mouse_pressed):
                selected_map_name = None if setup_map_index == 0 else setup_map_options[setup_map_index]
                run_difficulty = setup_difficulty
                game_ticks = 0
                Display = "Game"
                mouse_pressed = False
            else:
                for difficulty_value, difficulty_button in setup_buttons['DifficultyButtons'].items():
                    if MouseClick(difficulty_button, mouse_x, mouse_y, mouse_pressed):
                        setup_difficulty = difficulty_value
                        mouse_pressed = False
                        break

        elif Display == "Credits":
            Back = menus_file.credits_menu(MouseClick)
            if MouseClick(Back, mouse_x, mouse_y, mouse_pressed):
                Display = "MainMenu"
                mouse_pressed = False

        elif Display == "Game":
            if game_ticks == 0 and tutorial_run is None:
                active_run = True
                run_stats.clear_suspended_run()
                level_card = None
                player = apply_selected_loadout()
                player.alive = True
                player.x, player.y = _create_run_walls()
                level_reqirement = 10
                level = 1
                display_level_ratio = 0
                wave_xp_drop_last_spawn = None
                run_snapshot = run_stats.create_run_snapshot(selected_body, selected_gun)
                run_stats.update_runtime(run_snapshot, game_ticks, level, drops_file.exp)
                run_stats.save_run_checkpoint("run_start", run_snapshot, player)
                _spawn_wave(5, game_ticks, allow_early_spiker=True)
                run_snapshot["waves_spawned"] += 1
                run_stats.update_runtime(run_snapshot, game_ticks, level, drops_file.exp)
                run_stats.save_run_checkpoint("wave", run_snapshot, player)
            if tutorial_run is not None and not getattr(player, 'alive', True):
                _start_tutorial(tutorial_selected)
            if tutorial_run is None and not getattr(player, 'alive', True):
                if run_snapshot is not None:
                    run_stats.update_runtime(run_snapshot, game_ticks, level, drops_file.exp)
                    run_stats.save_run_checkpoint("run_end", run_snapshot, player)
                active_run = False
                level_card = None
                Display = "GameOver"
                enemy_file.enemies.clear()
                particles_file.particles.clear()
                drops_file.exp = 0
                drops_file.drops.clear()
                bullets_file.bullets.clear()
                wave_xp_drop_last_spawn = None
                run_snapshot = None
                run_stats.clear_suspended_run()
            game_ticks += 1
            if game_ticks % 600 == 0 and tutorial_run is None:
                _spawn_wave(game_ticks // 1800 + 2, game_ticks)
                if run_snapshot is not None:
                    run_snapshot["waves_spawned"] += 1
                    run_stats.update_runtime(run_snapshot, game_ticks, level, drops_file.exp)
                    run_stats.save_run_checkpoint("wave", run_snapshot, player)
            ui_assets.screen.fill((4, 16, 42))
            level_ratio = drops_file.exp / level_reqirement
            if display_level_ratio < level_ratio:
                if level_ratio - display_level_ratio < .1:
                    display_level_ratio = level_ratio
                else:
                    display_level_ratio += 0.1
            if display_level_ratio >= 1:
                display_level_ratio = 0
                level += 1
                if run_snapshot is not None:
                    run_snapshot["level_ups"] += 1
                    run_stats.update_runtime(run_snapshot, game_ticks, level, drops_file.exp)
                    run_stats.save_run_checkpoint("level_up", run_snapshot, player)
                    # Track achievements
                    run_stats.record_player_level(run_snapshot.get("body", ""), level)
                    run_stats.record_gun_level(run_snapshot.get("gun", ""), level)
                    run_stats.record_haunting_levels(haunting_options, level)
                    run_stats.record_swarm_level(swarm_options, level)
                level_events = player_body.apply_level_progression(player, level)
                player.attack_cooldown = 0
                player.health += round(player.max_health*.15)
                if player.health > player.max_health:
                    player.health = player.max_health
                if level_events:
                    level_card = build_level_card(level_events)
                    selected_upgrade_index = 0
                    Display = "LevelCard"
                else:
                    upgraded = False
                    step = _tutorial_levels()[level - 2] if 0 <= level - 2 < len(_tutorial_levels()) else None
                    chosen = (step or {}).get("cards") or [None] * 3
                    upgrade1, upgrade2, upgrade3 = (_roll_upgrade(chosen[i] if i < len(chosen) else None) for i in range(3))
                    selected_upgrade_index = 0
                    Display = "Upgrade"
                drops_file.exp -= level_reqirement
                if tutorial_run is not None:
                    level_reqirement = maps_file.level_requirement(_tutorial_levels(), level)
                else:
                    level_reqirement = round(level_reqirement * 1.4)
            if run_snapshot is not None:
                run_stats.update_runtime(run_snapshot, game_ticks, level, drops_file.exp)
            if tutorial_run is None or tutorial_run.tutorial.get("exp"):
                draw_level_hud(level, level_ratio, display_level_ratio)
            if tutorial_run is None:
                draw_spawn_hud(game_ticks)
            if isinstance(player, player_body.Slime):
                player.draw_slime_trail(ui_assets.screen)
            experience = drops_file.exp
            bullets = bullets_file.bullets
            enemies = enemy_file.enemies
            particles = particles_file.particles
            wave_overlay.update()
            wave_overlay.draw(ui_assets.screen)
            walls_file.draw_walls(ui_assets.screen)
            if map_runtime is not None:
                map_runtime.update(player, bullets_file.bullets, enemy_file.enemies, ability_used, level)
                tutorial_end_requested = map_runtime.end_requested
                map_runtime.draw(ui_assets.screen, game_ticks)
            health_before = {enemy: enemy.health for enemy in enemies}
            player_health_before = player.health
            for bullet in bullets[:]:
                old_bullet_x, old_bullet_y = bullet.x, bullet.y
                if bullet.x < 0:
                    bullet.x = 0
                    bullet.velocity.x *= -.5
                    bullet.speed *= .7
                elif bullet.x > Width*ui_assets.Horizontal_Scale:
                    bullet.x = Width*ui_assets.Horizontal_Scale
                    bullet.velocity.x *= -.5
                    bullet.speed *= .7
                if bullet.y < 0:
                    bullet.y = 0
                    bullet.velocity.y *= -.5
                    bullet.speed *= .7
                elif bullet.y > Height*ui_assets.Vertical_Scale:
                    bullet.y = Height*ui_assets.Vertical_Scale
                    bullet.velocity.y *= -.5
                    bullet.speed *= .7
                if bullet.move(enemies) or not walls_file.bounce_off_walls(bullet, old_bullet_x, old_bullet_y):
                    bullets.remove(bullet)
                else:
                    bullet.draw(ui_assets.screen)
            particles_file.update_and_draw(ui_assets.screen)
            for enemy in enemies:
                enemy.target(player)
                enemy.move()
                if not isinstance(enemy, enemy_file.Ghost):
                    walls_file.push_out_of_walls(enemy)
                enemy.draw(ui_assets.screen)
                if enemy.x < 0:
                    enemy.x += 1
                elif enemy.x > Width*ui_assets.Horizontal_Scale:
                    enemy.x -= 1
                if enemy.y < 0:
                    enemy.y += 1
                elif enemy.y > Height*ui_assets.Vertical_Scale:
                    enemy.y -= 1
            wave_enemies = [enemy for enemy in enemies if enemy.health > 0 and not getattr(enemy, "haunted", False)]
            if wave_enemies:
                wave_xp_drop_last_spawn = None
            elif tutorial_run is None or (
                tutorial_run.tutorial.get("exp")
                and tutorial_run.tutorial.get("outer_wall_exp", True)
            ):
                if wave_xp_drop_last_spawn is None:
                    wave_xp_drop_last_spawn = game_ticks
                elif game_ticks - wave_xp_drop_last_spawn >= 60:
                    edge_xp_amount = max(1, round(level_reqirement * 0.01))
                    drops_file.drops.append(
                        drops_file.create_edge_exp_drop(
                            edge_xp_amount,
                            round(ui_assets.Horizontal_Scale * Width),
                            round(ui_assets.Vertical_Scale * Height),
                        )
                    )
                    wave_xp_drop_last_spawn = game_ticks
            for drop in drops_file.drops:
                drop.move()
                drop.draw(ui_assets.screen)
                drop.collect(player)
            player.move()
            walls_file.push_out_of_walls(player)
            _record_offscreen_secret_progress(player)
            if isinstance(player, player_body.Slime):
                player.slime_target(enemies)
            if player.x < 0 + player.size:
                player.x += 1
            elif player.x > Width*ui_assets.Horizontal_Scale - player.size:
                player.x -= 1
            if player.y < 0 + player.size:
                player.y += 1
            elif player.y > Height*ui_assets.Vertical_Scale - player.size:
                player.y -= 1
            player.draw(ui_assets.screen, Fonts.tiny)
            if tutorial_run is not None:
                if not tutorial_run.tutorial.get("exp"):
                    drops_file.drops.clear()
                    drops_file.exp = 0
                tutorial_run.update(
                    player,
                    tutorial_end_requested,
                    map_runtime.end_delay_ticks if map_runtime is not None else None,
                    map_runtime,
                )
                if tutorial_run.finished:
                    _exit_tutorial()
                    Display = "Tutorial"
                    mouse_pressed = False
                    continue
            for enemy, old_health in health_before.items():
                if enemy.health < old_health:
                    wave_overlay.spawn((enemy.x, enemy.y), force=True)
            if player.health < player_health_before:
                wave_overlay.spawn((player.x, player.y), force=True)
            alive_enemies = [enemy for enemy in enemies if enemy.health > 0 and not getattr(enemy, "haunted", False)]
            if alive_enemies:
                avg_enemy_damage = sum(enemy.damage for enemy in alive_enemies) / len(alive_enemies)
                avg_enemy_max_health = sum(enemy.maxHealth for enemy in alive_enemies) / len(alive_enemies)
                dmg_surface = Fonts.tiny.render(f"Avg Enemy DMG: {avg_enemy_damage:.2f}", True, (255, 180, 80))
                hp_surface = Fonts.tiny.render(f"Avg Enemy Max HP: {avg_enemy_max_health:.2f}", True, (255, 220, 130))
                ui_assets.screen.blit(dmg_surface, (8, 8))
                ui_assets.screen.blit(hp_surface, (8, 24))
            if player.attack_cooldown == 0:
                effect = particles_file.HitParticle(player.x, player.y, player.size/5, player.color)
                particles_file.particles.append(effect)
            if pygame.K_w in pressed_keys:
                if pygame.K_a in pressed_keys or pygame.K_d in pressed_keys:
                    player.velocity.y -= player.speed * 0.7
                else:
                    player.velocity.y -= player.speed
            elif pygame.K_s in pressed_keys:
                if pygame.K_a in pressed_keys or pygame.K_d in pressed_keys:
                    player.velocity.y += player.speed * 0.7
                else:
                    player.velocity.y += player.speed
            if pygame.K_a in pressed_keys:
                if pygame.K_w in pressed_keys or pygame.K_s in pressed_keys:
                    player.velocity.x -= player.speed * 0.7
                else:
                    player.velocity.x -= player.speed
            elif pygame.K_d in pressed_keys:
                if pygame.K_w in pressed_keys or pygame.K_s in pressed_keys:
                    player.velocity.x += player.speed * 0.7
                else:
                    player.velocity.x += player.speed
            if pygame.K_UP in pressed_keys:
                if pygame.K_LEFT in pressed_keys:
                    player.shoot("up-left")
                elif pygame.K_RIGHT in pressed_keys:
                    player.shoot("up-right")
                else:
                    player.shoot("up")
            elif pygame.K_DOWN in pressed_keys:
                if pygame.K_LEFT in pressed_keys:
                    player.shoot("down-left")
                elif pygame.K_RIGHT in pressed_keys:
                    player.shoot("down-right")
                else:
                    player.shoot("down")
            elif pygame.K_LEFT in pressed_keys:
                player.shoot("left")
            elif pygame.K_RIGHT in pressed_keys:
                player.shoot("right")
            if pygame.K_ESCAPE in pressed_keys:
                if tutorial_run is not None:
                    _exit_tutorial()
                    Display = "Tutorial"
                    mouse_pressed = False
                    continue
                Display = "MainMenu"
            cooldown_before = _ability_cooldown_total(player)
            if pygame.K_LSHIFT in pressed_keys and isinstance(player, player_body.Dasher):
                if pygame.K_w in pressed_keys:
                    if pygame.K_a in pressed_keys:
                        player.dash("up-left")
                    elif pygame.K_d in pressed_keys:
                        player.dash("up-right")
                    else:
                        player.dash("up")
                elif pygame.K_s in pressed_keys:
                    if pygame.K_a in pressed_keys:
                        player.dash("down-left")
                    elif pygame.K_d in pressed_keys:
                        player.dash("down-right")
                    else:
                        player.dash("down")
                elif pygame.K_a in pressed_keys:
                    player.dash("left")
                elif pygame.K_d in pressed_keys:
                    player.dash("right")
            if pygame.K_LSHIFT in pressed_keys and isinstance(player, player_body.Nova):
                player.nova(enemies)
            if pygame.K_LSHIFT in pressed_keys and isinstance(player, player_body.Slime):
                player.slime_effect()
            ability_used = _ability_cooldown_total(player) > cooldown_before
        elif Display == "Upgrade":
            text_surface = Fonts.font.render("Level Up!", True, (250, 250, 250))
            text_rect = text_surface.get_rect(center=((50 + 900 / 2) * ui_assets.Horizontal_Scale, (30 + 100 / 2) * ui_assets.Vertical_Scale))
            ui_assets.screen.blit(text_surface, text_rect)
            text_surface = Fonts.font.render("Pick a Upgrade or Scrap for bonus XP", True, (250, 250, 250))
            text_rect = text_surface.get_rect(center=((50 + 900 / 2) * ui_assets.Horizontal_Scale, (80 + 100 / 2) * ui_assets.Vertical_Scale))
            ui_assets.screen.blit(text_surface, text_rect)
            if pygame.K_DOWN in keydown_events:
                selected_upgrade_index = 3
            else:
                if pygame.K_UP in keydown_events and selected_upgrade_index == 3:
                    selected_upgrade_index = 1
                if pygame.K_LEFT in keydown_events:
                    if selected_upgrade_index == 3:
                        selected_upgrade_index = 2
                    else:
                        selected_upgrade_index = (selected_upgrade_index - 1) % 3
                if pygame.K_RIGHT in keydown_events:
                    if selected_upgrade_index == 3:
                        selected_upgrade_index = 0
                    else:
                        selected_upgrade_index = (selected_upgrade_index + 1) % 3

            upgrade1_dark_color = (upgrade1.color[0] - 50, upgrade1.color[1] - 50, upgrade1.color[2] - 50)
            upgrade2_dark_color = (upgrade2.color[0] - 50, upgrade2.color[1] - 50, upgrade2.color[2] - 50)
            upgrade3_dark_color = (upgrade3.color[0] - 50, upgrade3.color[1] - 50, upgrade3.color[2] - 50)
            if "\n" in upgrade1.description:
                description = upgrade1.description.split("\n")
                UpgradeButton1 = MakeButton(50, 200, 275, 350, description[0], button_color=upgrade1.color, Font=Fonts.suble, select_color=upgrade1_dark_color)
                text_surface = Fonts.suble.render(description[1], True, Color.MenuText)
                text_rect = text_surface.get_rect(center=((50 + 275 / 2) * ui_assets.Horizontal_Scale, (230 + 350 / 2) * ui_assets.Vertical_Scale))
                ui_assets.screen.blit(text_surface, text_rect)
            else:
                UpgradeButton1 = MakeButton(50, 200, 275, 350, upgrade1.description, button_color=upgrade1.color, Font=Fonts.suble, select_color=upgrade1_dark_color)
            if "\n" in upgrade2.description:
                description = upgrade2.description.split("\n")
                UpgradeButton2 = MakeButton(360, 200, 275, 350, description[0], button_color=upgrade2.color, Font=Fonts.suble, select_color=upgrade2_dark_color)
                text_surface = Fonts.suble.render(description[1], True, Color.MenuText)
                text_rect = text_surface.get_rect(center=((360 + 275 / 2) * ui_assets.Horizontal_Scale, (230 + 350 / 2) * ui_assets.Vertical_Scale))
                ui_assets.screen.blit(text_surface, text_rect)
            else:
                UpgradeButton2 = MakeButton(360, 200, 275, 350, upgrade2.description, button_color=upgrade2.color, Font=Fonts.suble, select_color=upgrade2_dark_color)
            if "\n" in upgrade3.description:
                description = upgrade3.description.split("\n")
                UpgradeButton3 = MakeButton(675, 200, 275, 350, description[0], button_color=upgrade3.color, Font=Fonts.suble, select_color=upgrade3_dark_color)
                text_surface = Fonts.suble.render(description[1], True, Color.MenuText)
                text_rect = text_surface.get_rect(center=((675 + 275 / 2) * ui_assets.Horizontal_Scale, (230 + 350 / 2) * ui_assets.Vertical_Scale))
                ui_assets.screen.blit(text_surface, text_rect)
            else:
                UpgradeButton3 = MakeButton(675, 200, 275, 350, upgrade3.description, button_color=upgrade3.color, Font=Fonts.suble, select_color=upgrade3_dark_color)
            UpgradeName1 = MakeButton(50, 200, 275, 75, upgrade1.name, button_color=upgrade1_dark_color, outline=False, Font=Fonts.bold)
            UpgradeName2 = MakeButton(360, 200, 275, 75, upgrade2.name, button_color=upgrade2_dark_color, outline=False, Font=Fonts.bold)
            UpgradeName3 = MakeButton(675, 200, 275, 75, upgrade3.name, button_color=upgrade3_dark_color, outline=False, Font=Fonts.bold)
            scrap_color = (120, 120, 120)
            scrap_dark_color = (80, 80, 80)
            ScrapButton = MakeButton(290, 575, 420, 50, "Scrap (+25% next level XP)", button_color=scrap_color, Font=Fonts.suble, select_color=scrap_dark_color)

            selected_button = [UpgradeButton1, UpgradeButton2, UpgradeButton3, ScrapButton][selected_upgrade_index]
            selected_rect = pygame.Rect(
                selected_button.x * ui_assets.Horizontal_Scale,
                selected_button.y * ui_assets.Vertical_Scale,
                selected_button.width * ui_assets.Horizontal_Scale,
                selected_button.height * ui_assets.Vertical_Scale,
            )
            pygame.draw.rect(ui_assets.screen, (255, 255, 255), selected_rect, 4, border_radius=8)

            enter_pressed = pygame.K_RETURN in keydown_events or pygame.K_KP_ENTER in keydown_events

            if MouseClick(UpgradeButton1, mouse_x, mouse_y, mouse_pressed) or (enter_pressed and selected_upgrade_index == 0):
                upgrade1.apply(player)
                for i in range(10):
                    particles.append(particles_file.HitParticle(player.x, player.y, 15, upgrade1.color))
                if run_snapshot is not None:
                    run_snapshot["upgrades_chosen"] += 1
                    run_stats.update_runtime(run_snapshot, game_ticks, level, drops_file.exp)
                    run_stats.save_run_checkpoint("upgrade", run_snapshot, player)
                upgraded = True
            elif MouseClick(UpgradeButton2, mouse_x, mouse_y, mouse_pressed) or (enter_pressed and selected_upgrade_index == 1):
                upgrade2.apply(player)
                for i in range(10):
                    particles.append(particles_file.HitParticle(player.x, player.y, 15, upgrade2.color))
                if run_snapshot is not None:
                    run_snapshot["upgrades_chosen"] += 1
                    run_stats.update_runtime(run_snapshot, game_ticks, level, drops_file.exp)
                    run_stats.save_run_checkpoint("upgrade", run_snapshot, player)
                upgraded = True
            elif MouseClick(UpgradeButton3, mouse_x, mouse_y, mouse_pressed) or (enter_pressed and selected_upgrade_index == 2):
                upgrade3.apply(player)
                for i in range(10):
                    particles.append(particles_file.HitParticle(player.x, player.y, 15, upgrade3.color))
                if run_snapshot is not None:
                    run_snapshot["upgrades_chosen"] += 1
                    run_stats.update_runtime(run_snapshot, game_ticks, level, drops_file.exp)
                    run_stats.save_run_checkpoint("upgrade", run_snapshot, player)
                upgraded = True
            elif MouseClick(ScrapButton, mouse_x, mouse_y, mouse_pressed) or (enter_pressed and selected_upgrade_index == 3):
                drops_file.exp += round(level_reqirement * 0.25)
                for i in range(8):
                    particles.append(particles_file.HitParticle(player.x, player.y, 12, scrap_color))
                if run_snapshot is not None:
                    run_stats.update_runtime(run_snapshot, game_ticks, level, drops_file.exp)
                    run_stats.save_run_checkpoint("upgrade_scrap", run_snapshot, player)
                upgraded = True
            if upgraded:
                Display = "Game"
        elif Display == "LevelCard":
            card = level_card or build_level_card([{ "title": "Level Up", "description": "Something changed.", "color": (180, 180, 180) }])
            text_surface = Fonts.font.render("Level Up!", True, (250, 250, 250))
            text_rect = text_surface.get_rect(center=((50 + 900 / 2) * ui_assets.Horizontal_Scale, (30 + 100 / 2) * ui_assets.Vertical_Scale))
            ui_assets.screen.blit(text_surface, text_rect)
            text_surface = Fonts.font.render("Choose a card and press Enter", True, (250, 250, 250))
            text_rect = text_surface.get_rect(center=((50 + 900 / 2) * ui_assets.Horizontal_Scale, (80 + 100 / 2) * ui_assets.Vertical_Scale))
            ui_assets.screen.blit(text_surface, text_rect)
            level_events = card["events"]
            event_count = max(1, len(level_events))
            selected_upgrade_index = selected_upgrade_index % event_count

            if pygame.K_LEFT in keydown_events or pygame.K_UP in keydown_events:
                selected_upgrade_index = (selected_upgrade_index - 1) % event_count
            if pygame.K_RIGHT in keydown_events or pygame.K_DOWN in keydown_events:
                selected_upgrade_index = (selected_upgrade_index + 1) % event_count

            if event_count == 1:
                card_x_positions = [360]
            elif event_count == 2:
                card_x_positions = [205, 520]
            else:
                card_x_positions = [50, 360, 675]

            event_buttons = []
            for index, level_event in enumerate(level_events[:3]):
                event_color = level_event["color"]
                dark_color = (
                    max(0, event_color[0] - 50),
                    max(0, event_color[1] - 50),
                    max(0, event_color[2] - 50),
                )
                event_desc = level_event["description"]
                card_x = card_x_positions[index]

                if "\n" in event_desc:
                    description = event_desc.split("\n")
                    event_button = MakeButton(card_x, 200, 275, 350, description[0], button_color=event_color, Font=Fonts.suble, select_color=dark_color)
                    text_surface = Fonts.suble.render(description[1], True, Color.MenuText)
                    text_rect = text_surface.get_rect(center=((card_x + 275 / 2) * ui_assets.Horizontal_Scale, (230 + 350 / 2) * ui_assets.Vertical_Scale))
                    ui_assets.screen.blit(text_surface, text_rect)
                else:
                    event_button = MakeButton(card_x, 200, 275, 350, event_desc, button_color=event_color, Font=Fonts.suble, select_color=dark_color)

                MakeButton(card_x, 200, 275, 75, level_event["title"], button_color=dark_color, outline=False, Font=Fonts.bold)
                event_buttons.append(event_button)

            selected_button = event_buttons[selected_upgrade_index]
            selected_rect = pygame.Rect(
                selected_button.x * ui_assets.Horizontal_Scale,
                selected_button.y * ui_assets.Vertical_Scale,
                selected_button.width * ui_assets.Horizontal_Scale,
                selected_button.height * ui_assets.Vertical_Scale,
            )
            pygame.draw.rect(ui_assets.screen, (255, 255, 255), selected_rect, 4, border_radius=8)

            enter_pressed = pygame.K_RETURN in keydown_events or pygame.K_KP_ENTER in keydown_events
            accepted = enter_pressed and selected_upgrade_index < len(event_buttons)
            if not accepted:
                for event_button in event_buttons:
                    if MouseClick(event_button, mouse_x, mouse_y, mouse_pressed):
                        accepted = True
                        break

            if accepted:
                level_card = None
                Display = "Game"
                mouse_pressed = False
        
        elif Display == "GameOver":
            Display = "MainMenu"
            mouse_pressed = False

        else:
            ui_assets.screen.fill((250, 150, 150))
            text_surface = Fonts.font.render("A error has occurced", True, (200, 250, 250))  # Render the text
            text_rect = text_surface.get_rect(center=((50 + 900 / 2) * ui_assets.Horizontal_Scale, (130 + 100 / 2) * ui_assets.Vertical_Scale))  # Center the text
            ui_assets.screen.blit(text_surface, text_rect)  # Draw the text on the screen

        stain_enabled = Display == "Game"
        if stain_enabled and game_ticks % stain_refresh_rate == 0:
            _refresh_stain_overlay()
        if stain_enabled:
            _draw_stain_overlay()
        pygame.display.flip()  # Update the display
        clock.tick(60)  # Limit the frame rate to 60 FPS
    except Exception as e:
        print('Exception in main loop:', e)
        traceback.print_exc()
        if debug:
            running = False

if active_run and run_snapshot is not None and player is not None:
    _save_suspended_run_state()

pygame.quit()
