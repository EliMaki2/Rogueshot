# menus.py
# This file will contain all menu rendering and logic functions for WorldExplore
import pygame
import math
import Background.ui_assets as ui_assets
import Enemies.enemies as enemy_file
import Enemies.particles as particles_mod
import Player.player_body as player_body
import Player.bullets as bullets_file


_enemy_preview_state = {
    "enemy_name": None,
    "enemy": None,
    "target": None,
    "enemies": [],
    "particles": [],
    "ticks": 0
}

_upgrade_preview_state = {
    "upgrade_name": None,
    "ticks": 0,
    "player": None,
    "chaser": None,
    "enemies": [],
    "bullets": [],
    "particles": []
}
_upgrade_exp_drops = []
_upgrade_hurt_cooldown = 0
_achievement_image_cache = {}

_ENEMY_PREVIEW_SCALE = 0.5
_ENEMY_PREVIEW_EFFECT_SCALE = 0.5


def _lookup_stat_case_insensitive(stats, key):
    if key in stats:
        return stats.get(key, 0)

    key_norm = str(key).strip().lower()
    for existing_key, value in stats.items():
        if str(existing_key).strip().lower() == key_norm:
            return value
    return 0


class _PreviewTarget:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.size = 10
        self.speed = 0
        self.velocity = enemy_file.Vector(0, 0)

    def update(self, center_x, center_y, ticks):
        self.x = center_x + math.cos(ticks / 24) * 48
        self.y = center_y + math.sin(ticks / 32) * 38
        self.velocity = enemy_file.Vector(0, 0)

    def hurt(self, enemy):
        return None


def _spawn_preview_enemy(enemy_name, cx, cy):
    if enemy_name == "Chaser":
        enemy = enemy_file.Chaser(cx - 20, cy - 18, 120)
    if enemy_name == "Dasher":
        enemy = enemy_file.Dasher(cx - 20, cy - 18, 120)
    if enemy_name == "Blaster":
        enemy = enemy_file.Blaster(cx - 24, cy - 20, 120)
    if enemy_name == "Ghost":
        enemy = enemy_file.Ghost(cx - 14, cy - 14, 120)
    if enemy_name == "Spiker":
        enemy = enemy_file.Spiker(cx - 18, cy - 18, 120)
    if enemy_name not in ["Chaser", "Dasher", "Blaster", "Ghost", "Spiker"]:
        return None

    extra_scale = 0.5 if enemy_name == "Blaster" else 0.85 if enemy_name == "Spiker" else 1.0
    enemy.size = max(3, round(enemy.size * _ENEMY_PREVIEW_SCALE * extra_scale))
    return enemy


def _draw_enemy_without_healthbar(enemy, screen, effect_scale):
    red, green, blue = enemy.color
    red = min(255, max(0, red))
    green = min(255, max(0, green))
    blue = min(255, max(0, blue))
    enemy.color = (red, green, blue)
    pygame.draw.circle(screen, enemy.color, (int(enemy.x), int(enemy.y)), enemy.size)

    if enemy.harm_frames > 0:
        pygame.draw.circle(screen, (255, 255, 255), (int(enemy.x), int(enemy.y)), enemy.size + enemy.harm_frames / 3, 2)
        enemy.harm_frames -= 1

    if hasattr(enemy, "blast_time") and enemy.blast_time != -1:
        blast_radius = max(1, round((enemy.blast_time * 2 + enemy.size) * effect_scale))
        pygame.draw.circle(screen, (200, 100, 250), (int(enemy.x), int(enemy.y)), blast_radius, 2)

    if hasattr(enemy, "laser_charge") and getattr(enemy, "laser_charge", -1) >= 0:
        end_x = enemy.x + enemy.laser_direction.x * enemy.laser_length
        end_y = enemy.y + enemy.laser_direction.y * enemy.laser_length
        pygame.draw.line(screen, (180, 255, 200), (int(enemy.x), int(enemy.y)), (int(end_x), int(end_y)), 2)
    elif hasattr(enemy, "laser_time") and getattr(enemy, "laser_time", 0) > 0:
        end_x = enemy.x + enemy.laser_direction.x * enemy.laser_length
        end_y = enemy.y + enemy.laser_direction.y * enemy.laser_length
        pygame.draw.line(screen, (255, 120, 120), (int(enemy.x), int(enemy.y)), (int(end_x), int(end_y)), 3)
        pygame.draw.line(screen, (255, 230, 120), (int(enemy.x), int(enemy.y)), (int(end_x), int(end_y)), 1)


def _draw_enemy_logbook_preview(screen, entry_name, rect):
    global _enemy_preview_state

    pygame.draw.rect(screen, (20, 40, 55), rect)
    pygame.draw.rect(screen, (55, 95, 120), rect, 3)

    center_x = rect.x + rect.width // 2
    center_y = rect.y + rect.height // 2

    if _enemy_preview_state["enemy_name"] != entry_name:
        _enemy_preview_state = {
            "enemy_name": entry_name,
            "enemy": None,
            "target": _PreviewTarget(center_x, center_y),
            "enemies": [],
            "particles": [],
            "ticks": 0
        }

    if _enemy_preview_state["enemy"] is None:
        old_enemies = enemy_file.enemies
        try:
            enemy_file.enemies = _enemy_preview_state["enemies"]
            _enemy_preview_state["enemy"] = _spawn_preview_enemy(entry_name, center_x, center_y)
        finally:
            enemy_file.enemies = old_enemies

    old_enemies = enemy_file.enemies
    old_enemy_particles = enemy_file.particles
    old_particles = particles_mod.particles
    try:
        enemy_file.enemies = _enemy_preview_state["enemies"]
        enemy_file.particles = _enemy_preview_state["particles"]
        particles_mod.particles = _enemy_preview_state["particles"]

        _enemy_preview_state["ticks"] += 1
        ticks = _enemy_preview_state["ticks"]
        target = _enemy_preview_state["target"]
        target.update(center_x, center_y, ticks)

        enemy = _enemy_preview_state["enemy"]
        effect_scale = _ENEMY_PREVIEW_EFFECT_SCALE * (0.5 if entry_name == "Blaster" else 1.0)
        if enemy is not None:
            # Keep real targeting/ability flow, but disable contact-hit behavior in preview.
            original_hit = enemy.hit
            enemy.hit = lambda player: None
            if entry_name == "Blaster":
                # Match range behavior to preview scale so Blaster still chases when out of range.
                preview_blast_range = max(20, round(150 * _ENEMY_PREVIEW_SCALE * 0.5))
                enemy_file.Enemy.target(enemy, target)
                if enemy.distance_to(target) < preview_blast_range and enemy.blast_time == -1:
                    enemy.blast_time = 0
                if enemy.blast_time != -1:
                    enemy.blast(target)
            elif entry_name == "Spiker":
                enemy.target(target)
            else:
                enemy.target(target)
            enemy.hit = original_hit
            enemy.move()

            # Keep preview actor visible inside the image area.
            enemy.x = max(rect.x + 25, min(rect.x + rect.width - 25, enemy.x))
            enemy.y = max(rect.y + 25, min(rect.y + rect.height - 25, enemy.y))
            _draw_enemy_without_healthbar(enemy, screen, effect_scale)

        # Visible chase target for readability; it cannot be damaged.
        pygame.draw.circle(screen, (225, 235, 245), (int(target.x), int(target.y)), target.size)
        pygame.draw.circle(screen, (25, 55, 75), (int(target.x), int(target.y)), target.size, 2)

        for particle in list(_enemy_preview_state["particles"]):
            particle.move()
            if entry_name == "Blaster":
                preview_size = max(1, round(particle.size * effect_scale))
                pygame.draw.circle(screen, particle.color, (int(particle.x), int(particle.y)), preview_size)
            else:
                particle.draw(screen)
    finally:
        enemy_file.enemies = old_enemies
        enemy_file.particles = old_enemy_particles
        particles_mod.particles = old_particles


def _configure_upgrade_preview_player(player, entry_name):
    # Reset to player defaults before applying one upgrade flavor.
    player.attack_speed = 20
    player.attack_spread = 0.05
    player.multishot = 3
    player.pierce = 1
    player.attack_range = 10
    player.damage = 1
    player.bullet_color = (255, 255, 255)
    player.knockback = 0.1
    player.bullet_speed = 5
    player.speed = 1

    if entry_name == "Sharp Bullets":
        player.damage = 3
        player.bullet_color = (235, 235, 235)
    elif entry_name == "Fast Reload":
        player.attack_speed = 8
        player.bullet_color = (220, 250, 170)
    elif entry_name == "High Velocity":
        player.pierce = 3
        player.bullet_speed = 8
        player.bullet_color = (160, 180, 255)
    elif entry_name == "Long Sights":
        player.attack_range = 18
        player.bullet_color = (170, 230, 255)
    elif entry_name == "Quick Feet":
        player.speed = 2.5
        player.bullet_color = (255, 215, 120)
    elif entry_name == "Extra Barrel":
        player.multishot = 6
        player.attack_spread = 0.08
        player.bullet_color = (255, 190, 120)
    elif entry_name == "Tough Skin":
        player.max_health = 25
        player.health = player.max_health
        player.bullet_color = (255, 160, 160)
    elif entry_name == "Pocket Magnets":
        player.pickup = 320
        player.bullet_color = (140, 230, 230)
    elif entry_name == "Lead Tips":
        player.knockback = 0.4
        player.bullet_color = (250, 170, 170)


def _aim_direction(source_x, source_y, target_x, target_y):
    dx = target_x - source_x
    dy = target_y - source_y
    if abs(dx) < 2 and abs(dy) < 2:
        return "right"
    horizontal = "right" if dx >= 0 else "left"
    vertical = "down" if dy >= 0 else "up"
    if abs(dx) > abs(dy) * 1.5:
        return horizontal
    if abs(dy) > abs(dx) * 1.5:
        return vertical
    return vertical + "-" + horizontal


def _draw_player_preview(player, target, screen):
    pygame.draw.circle(screen, player.color, (int(player.x), int(player.y)), player.size)
    pygame.draw.circle(screen, (255, 255, 255), (int(player.x), int(player.y)), player.size, 2)
    if target is not None:
        aim = enemy_file.Vector(target.x - player.x, target.y - player.y).normalize().multiply(player.size + 8)
        pygame.draw.line(screen, (240, 230, 210), (int(player.x), int(player.y)), (int(player.x + aim.x), int(player.y + aim.y)), 2)


def _draw_upgrade_logbook_preview(screen, entry_name, rect):
    global _upgrade_preview_state
    global _upgrade_exp_drops, _upgrade_hurt_cooldown

    pygame.draw.rect(screen, (20, 40, 55), rect)
    pygame.draw.rect(screen, (55, 95, 120), rect, 3)

    if _upgrade_preview_state["upgrade_name"] != entry_name:
        _upgrade_preview_state = {
            "upgrade_name": entry_name,
            "ticks": 0,
            "player": None,
            "chaser": None,
            "enemies": [],
            "bullets": [],
            "particles": []
        }
        _upgrade_exp_drops = []
        _upgrade_hurt_cooldown = 0

    state = _upgrade_preview_state
    state["ticks"] += 1
    ticks = state["ticks"]

    if state["player"] is None or state["chaser"] is None:
        state["player"] = player_body.Retribution(rect.x + int(rect.width * 0.28), rect.y + int(rect.height * 0.55), size=9, health=20)

        if entry_name not in ["Quick Feet", "Pocket Magnets", "Long Sights"]:
            state["chaser"] = enemy_file.Chaser(rect.x + int(rect.width * 0.78), rect.y + int(rect.height * 0.55), 1)
            state["chaser"].size = 8
            state["chaser"].maxHealth = 200
            state["chaser"].health = 200
            state["chaser"].damage = 0
            state["enemies"] = [state["chaser"]]

    old_enemies = enemy_file.enemies
    old_enemy_particles = enemy_file.particles
    old_particles = particles_mod.particles
    old_bullets = bullets_file.bullets
    try:
        enemy_file.enemies = state["enemies"]
        enemy_file.particles = state["particles"]
        particles_mod.particles = state["particles"]
        bullets_file.bullets = state["bullets"]

        player = state["player"]
        chaser = state["chaser"]
        _configure_upgrade_preview_player(player, entry_name)

        if entry_name == "Quick Feet":
            player.velocity.x += math.cos(ticks / 5) * (0.55 * player.speed)

        if entry_name == "Pocket Magnets":
            if ticks % 30 == 0:
                drop = {
                    "x": rect.x + rect.width * 0.75,
                    "y": rect.y + int(rect.height * 0.2),
                    "age": 0
                }
                _upgrade_exp_drops.append(drop)

        if entry_name == "Tough Skin":
            _upgrade_hurt_cooldown = max(0, _upgrade_hurt_cooldown - 1)
            if _upgrade_hurt_cooldown <= 0 and ticks > 20:
                player.hurt(type('obj', (object,), {'damage': 2})())
                _upgrade_hurt_cooldown = 60

        if chaser is not None:
            original_hit = chaser.hit
            chaser.hit = lambda target_player: None
            chaser.target(player)
            chaser.hit = original_hit
            chaser.move()

        player.move()
        player.x = max(rect.x + 18, min(rect.x + rect.width * 0.55, player.x))
        player.y = max(rect.y + 18, min(rect.y + rect.height - 18, player.y))

        if chaser is not None:
            chaser.x = max(rect.x + rect.width * 0.58, min(rect.x + rect.width - 18, chaser.x))
            chaser.y = max(rect.y + 18, min(rect.y + rect.height - 18, chaser.y))

        if entry_name == "Long Sights":
            wall_x = rect.x + rect.width - 20
            pygame.draw.rect(screen, (100, 100, 100), (wall_x, rect.y + 10, 12, rect.height - 20))
            pygame.draw.rect(screen, (70, 70, 70), (wall_x, rect.y + 10, 12, rect.height - 20), 2)
            shoot_direction = "right"
        elif chaser is not None:
            shoot_direction = _aim_direction(player.x, player.y, chaser.x, chaser.y)
        else:
            shoot_direction = "right"

        if ticks % 2 == 0 and entry_name not in ["Quick Feet", "Pocket Magnets", "Tough Skin"]:
            player.shoot(shoot_direction)

        for bullet in list(state["bullets"]):
            removed = bullet.move(state["enemies"])
            if removed or bullet.x < rect.x - 10 or bullet.x > rect.x + rect.width + 10 or bullet.y < rect.y - 10 or bullet.y > rect.y + rect.height + 10:
                if bullet in state["bullets"]:
                    state["bullets"].remove(bullet)
                continue
            bullet.draw(screen)

        if chaser is not None:
            chaser.health = max(120, chaser.health)
            chaser.maxHealth = max(chaser.maxHealth, chaser.health)
            _draw_enemy_without_healthbar(chaser, screen, _ENEMY_PREVIEW_EFFECT_SCALE)

        for drop in list(_upgrade_exp_drops):
            drop["age"] += 1
            if drop["x"] - player.x < 30:
                _upgrade_exp_drops.remove(drop)
                continue
            if drop["age"] > 300:
                _upgrade_exp_drops.remove(drop)
                continue
            pygame.draw.polygon(screen, (255, 220, 80), [(drop["x"], drop["y"] - 4), (drop["x"] - 3, drop["y"] + 4), (drop["x"] + 3, drop["y"] + 4)])

        _draw_player_preview(player, chaser, screen)

        for particle in list(state["particles"]):
            particle.move()
            particle.draw(screen)
    finally:
        enemy_file.enemies = old_enemies
        enemy_file.particles = old_enemy_particles
        particles_mod.particles = old_particles
        bullets_file.bullets = old_bullets


def _build_logbook_data():
    # Keep logbook content grouped by category so each display gets its own side menu.
    return {
        "Upgrades": [
            {
                "name": "Sharp Bullets",
                "paragraph": "A clean damage boost that lets each shot hit harder. Great for pushing through tougher waves.",
                "color": (200, 200, 200),
                "shape": "diamond"
            },
            {
                "name": "Fast Reload",
                "paragraph": "Reduces the time between shots so your weapon fires more often during crowded fights.",
                "color": (150, 250, 150),
                "shape": "rect"
            },
            {
                "name": "High Velocity",
                "paragraph": "Improves piercing so bullets travel through more enemies before fading out.",
                "color": (150, 150, 250),
                "shape": "triangle"
            },
            {
                "name": "Long Sights",
                "paragraph": "Extends projectile range so shots stay active longer and control more of the screen.",
                "color": (160, 220, 255),
                "shape": "diamond"
            },
            {
                "name": "Quick Feet",
                "paragraph": "Increases movement speed for cleaner dodges and better positioning.",
                "color": (250, 200, 100),
                "shape": "triangle"
            },
            {
                "name": "Extra Barrel",
                "paragraph": "Adds bullets per attack for stronger spread and burst pressure.",
                "color": (255, 180, 120),
                "shape": "rect"
            },
            {
                "name": "Tough Skin",
                "paragraph": "Raises max health to survive longer runs and mistakes.",
                "color": (255, 130, 130),
                "shape": "circle"
            },
            {
                "name": "Pocket Magnets",
                "paragraph": "Expands pickup radius so drops are collected faster and with less risk.",
                "color": (120, 230, 230),
                "shape": "circle"
            },
            {
                "name": "Lead Tips",
                "paragraph": "Adds knockback so enemies are pushed away and pressure is easier to manage.",
                "color": (250, 170, 170),
                "shape": "diamond"
            }
        ],
        "Enemies": [
            {
                "name": "Chaser",
                "paragraph": "A fast basic threat that closes distance quickly and swarms in numbers.",
                "color": (250, 60, 60),
                "shape": "circle"
            },
            {
                "name": "Dasher",
                "paragraph": "Charges toward the player in bursts. Watch for windup and sudden movement spikes.",
                "color": (250, 200, 50),
                "shape": "diamond"
            },
            {
                "name": "Blaster",
                "paragraph": "Builds an expanding blast zone. Keep moving to avoid the explosive radius.",
                "color": (150, 50, 250),
                "shape": "rect"
            },
            {
                "name": "Ghost",
                "paragraph": "Shifts behavior near the player and can become dangerous when it finds an opening.",
                "color": (100, 100, 255),
                "shape": "triangle"
            },
            {
                "name": "Spiker",
                "paragraph": "Charges a laser line, then fires a short beam. The warning particles show where it will strike.",
                "color": (80, 220, 140),
                "shape": "diamond"
            }
        ],
        "Items": [
            {
                "name": "Exp Crystal",
                "paragraph": "The most common pickup. Gather enough crystals to level up and choose upgrades.",
                "color": (255, 220, 60),
                "shape": "triangle"
            }
        ]
    }


def _draw_logbook_icon(screen, rect, entry):
    color = entry.get("color", (200, 200, 200))
    shape = entry.get("shape", "circle")
    dark_color = (max(0, color[0] - 80), max(0, color[1] - 80), max(0, color[2] - 80))
    pygame.draw.rect(screen, (20, 40, 55), rect)
    pygame.draw.rect(screen, dark_color, rect, 3)

    cx, cy = rect.center
    radius = min(rect.width, rect.height) // 4

    if shape == "rect":
        inner = pygame.Rect(0, 0, radius * 2, radius * 2)
        inner.center = (cx, cy)
        pygame.draw.rect(screen, color, inner)
        pygame.draw.rect(screen, dark_color, inner, 2)
    elif shape == "triangle":
        points = [(cx, cy - radius), (cx - radius, cy + radius), (cx + radius, cy + radius)]
        pygame.draw.polygon(screen, color, points)
        pygame.draw.polygon(screen, dark_color, points, 2)
    elif shape == "diamond":
        points = [(cx, cy - radius), (cx - radius, cy), (cx, cy + radius), (cx + radius, cy)]
        pygame.draw.polygon(screen, color, points)
        pygame.draw.polygon(screen, dark_color, points, 2)
    else:
        pygame.draw.circle(screen, color, (cx, cy), radius)
        pygame.draw.circle(screen, dark_color, (cx, cy), radius, 2)


def _draw_wrapped_text(screen, text, font, color, x, y, max_width, max_lines):
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        candidate = word if current_line == "" else current_line + " " + word
        if font.size(candidate)[0] <= max_width:
            current_line = candidate
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)

    line_height = font.get_height() + 4
    for i, line in enumerate(lines[:max_lines]):
        text_surface = font.render(line, True, color)
        screen.blit(text_surface, (x, y + i * line_height))


def _draw_multiline_centered_text(screen, text, font, color, center_x, center_y, max_width, max_lines):
    paragraphs = text.split("\n")
    lines = []

    for paragraph in paragraphs:
        words = paragraph.split()
        current_line = ""
        for word in words:
            candidate = word if current_line == "" else current_line + " " + word
            if font.size(candidate)[0] <= max_width:
                current_line = candidate
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

    lines = lines[:max_lines]
    if not lines:
        return

    line_height = font.get_height() + 2
    total_height = len(lines) * line_height - 2
    start_y = center_y - total_height / 2

    for index, line in enumerate(lines):
        text_surface = font.render(line, True, color)
        text_rect = text_surface.get_rect(center=(center_x, start_y + index * line_height + text_surface.get_height() / 2))
        screen.blit(text_surface, text_rect)


def _build_achievements_data():
    """Dynamically build achievements from tracked stats and photo assets."""
    from Background import run_stats
    import os
    
    achievements_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Assets", "Achivements")
    data = run_stats._load_store()
    achievements = data.get("achievements", {})
    enemy_kills = achievements.get("enemy_kills", {})
    player_levels = achievements.get("player_max_levels", {})
    gun_levels = achievements.get("gun_max_levels", {})
    haunting_levels = achievements.get("haunting_max_levels", {})
    swarm_levels = achievements.get("swarm_max_levels", {})
    levels_combos = achievements.get("levels_total_by_combo", achievements.get("levels_by_combo", {}))
    secret_progress = achievements.get("secret_progress", {})
    
    result = []
    
    # Frame images for different completion tiers
    frames = {
        0: None,           # No progress
        1: os.path.join(achievements_folder, "copper_frame.png"),   # 1 tier completed
        2: os.path.join(achievements_folder, "silver_frame.png"),   # 2 tiers completed
        3: os.path.join(achievements_folder, "gold_frame.png"),     # 3 tiers completed
        4: os.path.join(achievements_folder, "epic_frame.png"),     # 4 tiers completed (all)
    }
    
    # Flag achievements (levels: 5, 10, 25, 50, 100)
    flag_levels = [5, 10, 25, 50, 100]
    total_combo_count = max(1, len(run_stats.CANONICAL_PLAYER_NAMES) * len(run_stats.CANONICAL_GUN_NAMES))
    tier_counts = [
        1,
        max(1, math.ceil(total_combo_count * 0.30)),
        max(1, math.ceil(total_combo_count * 0.65)),
        total_combo_count,
    ]

    for level_threshold in flag_levels:
        flag_name = f"{level_threshold}-flag.png"
        flag_image = os.path.join(achievements_folder, flag_name)

        qualifying_combos = []
        for combo_key, total_levels in sorted(levels_combos.items()):
            if int(total_levels) < level_threshold:
                continue
            if "_" in combo_key:
                player_name, gun_name = combo_key.split("_", 1)
                qualifying_combos.append(f"{player_name} + {gun_name} ({int(total_levels)})")
            else:
                qualifying_combos.append(f"{combo_key} ({int(total_levels)})")

        # Count how many different player/gun combos reached this cumulative level total.
        combos_at_level = len(qualifying_combos)
        if combos_at_level >= tier_counts[3]:
            frame_idx = 4
        elif combos_at_level >= tier_counts[2]:
            frame_idx = 3
        elif combos_at_level >= tier_counts[1]:
            frame_idx = 2
        elif combos_at_level >= tier_counts[0]:
            frame_idx = 1
        else:
            frame_idx = 0
        combos_text = ", ".join(qualifying_combos) if qualifying_combos else "None yet"
        
        frame_image = frames.get(frame_idx)
        result.append({
            "title": f"Level {level_threshold}",
            "paragraph": (
                f"Earn {level_threshold} total levels with different player/gun combinations.\n"
                f"Progress: {combos_at_level}/{total_combo_count} combos\n"
                f"Tiers: 1 | {tier_counts[1]} ({int(100 * tier_counts[1] / total_combo_count)}%) | {tier_counts[2]} ({int(100 * tier_counts[2] / total_combo_count)}%) | {tier_counts[3]} (100%)\n"
                f"Used combos: {combos_text}"
            ),
            "image": flag_image,
            "frame": frame_image,
            "completed": combos_at_level >= tier_counts[3],
            "progress": frame_idx,
            "color": (255, 215, 0),
            "category": "Level",
        })
    
    # Enemy kill achievements
    enemy_thresholds = [50, 100, 200, 500]
    enemy_names = [
        {"key": "chaser", "display": "Chaser", "aliases": []},
        {"key": "ghost", "display": "Ghost", "aliases": []},
        {"key": "leaper", "display": "Dasher", "aliases": []},
        {"key": "blaster", "display": "Blaster", "aliases": []},
        {"key": "spiker", "display": "Spiker", "aliases": []},
        {"key": "guardian", "display": "Guardian", "aliases": ["guardian"]},
        {"key": "warper", "display": "Warper", "aliases": []},
        {"key": "turret", "display": "Turret", "aliases": []},
    ]
    
    for enemy_info in enemy_names:
        enemy_key = enemy_info["key"]
        enemy_display = enemy_info["display"]
        kills = _lookup_stat_case_insensitive(enemy_kills, enemy_key)
        for alias in enemy_info.get("aliases", []):
            kills += _lookup_stat_case_insensitive(enemy_kills, alias)
        
        # Determine frame based on which thresholds are met
        frame_idx = 0
        for threshold_idx, threshold in enumerate(enemy_thresholds):
            if kills >= threshold:
                frame_idx = min(4, threshold_idx + 1)
        
        enemy_image = os.path.join(achievements_folder, f"{enemy_key}.png")
        result.append({
            "title": f"{enemy_display} Slayer",
            "paragraph": f"Defeat {enemy_display}s: {kills}\nTiers: 50 | 100 | 200 | 500",
            "image": enemy_image,
            "frame": frames.get(frame_idx),
            "completed": kills >= 500,
            "progress": frame_idx,
            "color": (255, 100, 100),
            "category": "Slayer",
        })
    
    # Shared level thresholds used by level-based achievements.
    level_thresholds = [5, 15, 30, 50]
    first_level_threshold = level_thresholds[0]

    # Haunting level achievements
    haunting_types = [
        {"key": "Chaser", "image": "chaser_haunt", "display": "Chaser"},
        {"key": "Dasher", "image": "leaper_haunt", "display": "Dasher"},
        {"key": "Blaster", "image": "blaster_haunt", "display": "Blaster"},
        {"key": "Ghost", "image": "ghost_haunt", "display": "Ghost"},
        {"key": "Spiker", "image": "spiker_haunt", "display": "Spiker"},
        {"key": "Guardian", "image": "guardian_haunt", "display": "Guardian"},
        {"key": "Warper", "image": "warper_haunt", "display": "Warper"},
        {"key": "Turret", "image": "turret_haunt", "display": "Turret"},
    ]

    haunting_unlocked = any(
        _lookup_stat_case_insensitive(haunting_levels, haunting_info["key"]) >= first_level_threshold
        for haunting_info in haunting_types
    )
    if haunting_unlocked:
        for haunting_info in haunting_types:
            haunting_key = haunting_info["key"]
            max_level = _lookup_stat_case_insensitive(haunting_levels, haunting_key)

            frame_idx = 0
            for threshold_idx, threshold in enumerate(level_thresholds):
                if max_level >= threshold:
                    frame_idx = min(4, threshold_idx + 1)

            haunting_image = os.path.join(achievements_folder, f"{haunting_info['image']}.png")
            result.append({
                "title": f"{haunting_info['display']} Haunting",
                "paragraph": (
                    f"Reach levels while {haunting_info['display']} haunting is enabled: {max_level}\n"
                    "Tiers: 5 | 15 | 30 | 50"
                ),
                "image": haunting_image,
                "frame": frames.get(frame_idx),
                "completed": max_level >= 50,
                "progress": frame_idx,
                "color": (190, 160, 255),
                "category": "Haunting",
            })

    # Swarm level achievements
    swarm_types = [
        {"key": "Chaser", "image": "chaser_swarm", "display": "Chaser"},
        {"key": "Dasher", "image": "leaper_swarm", "display": "Dasher"},
        {"key": "Blaster", "image": "blaster_swarm", "display": "Blaster"},
        {"key": "Ghost", "image": "ghost_swarm", "display": "Ghost"},
        {"key": "Spiker", "image": "spiker_swarm", "display": "Spiker"},
        {"key": "Guardian", "image": "guardian_swarm", "display": "Guardian"},
        {"key": "Warper", "image": "warper_swarm", "display": "Warper"},
        {"key": "Turret", "image": "turret_swarm", "display": "Turret"},
    ]

    swarm_unlocked = any(
        _lookup_stat_case_insensitive(swarm_levels, swarm_info["key"]) >= first_level_threshold
        for swarm_info in swarm_types
    )
    if swarm_unlocked:
        for swarm_info in swarm_types:
            swarm_key = swarm_info["key"]
            max_level = _lookup_stat_case_insensitive(swarm_levels, swarm_key)

            frame_idx = 0
            for threshold_idx, threshold in enumerate(level_thresholds):
                if max_level >= threshold:
                    frame_idx = min(4, threshold_idx + 1)

            swarm_image = os.path.join(achievements_folder, f"{swarm_info['image']}.png")
            result.append({
                "title": f"{swarm_info['display']} Swarm",
                "paragraph": (
                    f"Reach levels while swarm is enabled with {swarm_info['display']}: {max_level}\n"
                    "Tiers: 5 | 15 | 30 | 50"
                ),
                "image": swarm_image,
                "frame": frames.get(frame_idx),
                "completed": max_level >= 50,
                "progress": frame_idx,
                "color": (255, 175, 120),
                "category": "Swarm",
            })

    # Player level achievements
    players = ["dasher", "nova", "retribution", "slime"]
    
    for player_type in players:
        max_level = _lookup_stat_case_insensitive(player_levels, player_type)
        
        # Determine frame based on which level thresholds are met
        frame_idx = 0
        for threshold_idx, threshold in enumerate(level_thresholds):
            if max_level >= threshold:
                frame_idx = min(4, threshold_idx + 1)
        
        player_image = os.path.join(achievements_folder, f"{player_type}.png")
        result.append({
            "title": f"{player_type.title()}",
            "paragraph": f"Reach levels with {player_type.title()}: {max_level}\nTiers: 5 | 15 | 30 | 50",
            "image": player_image,
            "frame": frames.get(frame_idx),
            "completed": max_level >= 50,
            "progress": frame_idx,
            "color": (100, 200, 255),
            "category": "Player/Gun",
        })
    
    # Gun level achievements
    guns = ["blowdart", "cannon", "shotgun", "sword", "flamethrower"]
    
    for gun_type in guns:
        max_level = _lookup_stat_case_insensitive(gun_levels, gun_type)
        
        # Determine frame based on which level thresholds are met
        frame_idx = 0
        for threshold_idx, threshold in enumerate(level_thresholds):
            if max_level >= threshold:
                frame_idx = min(4, threshold_idx + 1)
        
        gun_image = os.path.join(achievements_folder, f"{gun_type}.png")
        result.append({
            "title": f"{gun_type.title()}",
            "paragraph": f"Reach levels with {gun_type.title()}: {max_level}\nTiers: 5 | 15 | 30 | 50",
            "image": gun_image,
            "frame": frames.get(frame_idx),
            "completed": max_level >= 50,
            "progress": frame_idx,
            "color": (100, 255, 150),
            "category": "Player/Gun",
        })

    # Secret achievements
    secret_image = os.path.join(achievements_folder, "secret.png")
    epic_frame = os.path.join(achievements_folder, "epic_frame.png")
    blaster_self_destructions = max(0, int(secret_progress.get("blaster_self_destructions", 0)))
    offscreen_distance_max = max(0, int(secret_progress.get("offscreen_distance_max", 0)))
    spiker_parries = max(0, int(secret_progress.get("spiker_parries", 0)))

    secret_entries = [
        {
            "title": "Collateral Lessons",
            "locked_title": "Hidden Secret I",
            "paragraph": (
                "Watch 20 Blasters destroy themselves with their own explosion self-damage.\n"
                f"Progress: {blaster_self_destructions}/20"
            ),
            "locked_paragraph": "No information is shown until this secret achievement is unlocked.",
            "image": os.path.join(achievements_folder, "blaster_destruction.png"),
            "locked_image": secret_image,
            "frame": epic_frame if blaster_self_destructions >= 20 else None,
            "completed": blaster_self_destructions >= 20,
            "progress": 4 if blaster_self_destructions >= 20 else 0,
            "color": (180, 180, 180),
            "category": "Secret",
            "secret": True,
        },
        {
            "title": "Beyond The Border",
            "locked_title": "Hidden Secret II",
            "paragraph": (
                "Get more than 300 pixels outside the main screen.\n"
                f"Best distance: {offscreen_distance_max}px"
            ),
            "locked_paragraph": "No information is shown until this secret achievement is unlocked.",
            "image": secret_image,
            "locked_image": secret_image,
            "frame": epic_frame if offscreen_distance_max > 300 else None,
            "completed": offscreen_distance_max > 300,
            "progress": 4 if offscreen_distance_max > 300 else 0,
            "color": (180, 180, 180),
            "category": "Secret",
            "secret": True,
        },
        {
            "title": "Steel Against Spikes",
            "locked_title": "Hidden Secret III",
            "paragraph": (
                "Parry 10 Spikers with sword guard.\n"
                f"Progress: {spiker_parries}/10"
            ),
            "locked_paragraph": "No information is shown until this secret achievement is unlocked.",
            "image": os.path.join(achievements_folder, "parry_spiker.png"),
            "locked_image": secret_image,
            "frame": epic_frame if spiker_parries >= 10 else None,
            "completed": spiker_parries >= 10,
            "progress": 4 if spiker_parries >= 10 else 0,
            "color": (180, 180, 180),
            "category": "Secret",
            "secret": True,
        },
    ]
    result.extend(secret_entries)
    
    return result


def _scale_pixelperfect_to_fill(image, target_width, target_height):
    """Scale image with 8x pixel-perfect scaling, increasing factor to fill box."""
    orig_width, orig_height = image.get_size()
    scale_factor = 8
    
    # Keep scaling up until it fills the box, but don't exceed target dimensions
    while (orig_width * scale_factor < target_width or orig_height * scale_factor < target_height):
        if (orig_width * (scale_factor + 1) > target_width or orig_height * (scale_factor + 1) > target_height):
            break
        scale_factor += 1
    
    scaled_width = min(orig_width * scale_factor, target_width)
    scaled_height = min(orig_height * scale_factor, target_height)
    return pygame.transform.scale(image, (scaled_width, scaled_height))


def _load_achievement_image(image_path):
    if not image_path:
        return None
    if image_path in _achievement_image_cache:
        return _achievement_image_cache[image_path]

    try:
        loaded = pygame.image.load(image_path).convert_alpha()
    except (pygame.error, FileNotFoundError):
        loaded = None

    _achievement_image_cache[image_path] = loaded
    return loaded


def _draw_achievement_preview(screen, rect, entry):
    is_secret_locked = bool(entry.get("secret", False)) and not bool(entry.get("completed", False))
    image_path = entry.get("locked_image") if is_secret_locked else entry.get("image")
    frame_path = entry.get("frame")
    progress = entry.get("progress", 0)
    
    # Draw frame first (underneath)
    if frame_path:
        frame = _load_achievement_image(frame_path)
        if frame is not None:
            fitted_frame = _scale_pixelperfect_to_fill(frame, rect.width, rect.height)
            screen.blit(fitted_frame, (rect.left, rect.top))
    
    # Draw image on top
    image = _load_achievement_image(image_path)
    if image is not None:
        fitted = _scale_pixelperfect_to_fill(image, rect.width, rect.height)
        if progress == 0:
            fitted = pygame.transform.grayscale(fitted)
        screen.blit(fitted, (rect.left, rect.top))
        pygame.draw.rect(screen, (45, 65, 85), rect, 3)
        return

    fallback_entry = {
        "color": entry.get("color", (210, 210, 210)),
        "shape": entry.get("shape", "circle")
    }
    _draw_logbook_icon(screen, rect, fallback_entry)
    if not entry.get("completed", False):
        overlay = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        overlay.fill((20, 20, 20, 120))
        screen.blit(overlay, rect.topleft)

def main_menu(active_run, mouse_x, mouse_y, mouse_pressed, MouseClick):
    screen = ui_assets.screen
    Color = ui_assets.Color
    Fonts = ui_assets.Fonts
    Horizontal_Scale = ui_assets.Horizontal_Scale
    Vertical_Scale = ui_assets.Vertical_Scale
    MakeButton = ui_assets.MakeButton
    screen.fill(Color.MenuLight)
    pygame.draw.rect(screen, Color.MenuDark, (50 * Horizontal_Scale, 150 * Vertical_Scale, 900 * Horizontal_Scale, 440 * Vertical_Scale))
    text_surface = Fonts.title.render("Rougeshot", True, Color.MenuDarkSelect)
    text_rect = text_surface.get_rect(center=((50 + 900 / 2) * Horizontal_Scale, (30 + 100 / 2) * Vertical_Scale))
    screen.blit(text_surface, text_rect)
    EndRunButton = None
    if active_run:
        continue_width = round(350 * (2 / 3))
        continue_gap = 10
        end_width = 350 - continue_width - continue_gap
        StartButton = MakeButton(125, 180, continue_width, 70, "Continue", select_color=Color.MenuDarkSelect)
        EndRunButton = MakeButton(
            125 + continue_width + continue_gap,
            180,
            end_width,
            70,
            "End Run",
            text_color=(245, 245, 245),
            button_color=(170, 45, 45),
            select_color=(110, 20, 20),
            Font=Fonts.bold,
        )
    else:
        StartButton = MakeButton(125, 180, 350, 70, "Start Game")
    OptionsButton = MakeButton(125, 380, 350, 70, "Challenges")
    TutorialButton = MakeButton(125, 280, 350, 70, "Tutorial")
    AchievementsButton = MakeButton(525, 280, 350, 70, "Achievements")
    CustomisationsButton = MakeButton(525, 180, 350, 70, "Build")
    MapEditorButton = MakeButton(525, 380, 350, 70, "Map Editor")
    ExitButton = MakeButton(150, 480, 700, 70, "Quit", select_color=Color.MenuDarkSelect)
    return {
        'StartButton': StartButton,
        'EndRunButton': EndRunButton,
        'OptionsButton': OptionsButton,
        'TutorialButton': TutorialButton,
        'AchievementsButton': AchievementsButton,
        'CustomisationsButton': CustomisationsButton,
        'MapEditorButton': MapEditorButton,
        'ExitButton': ExitButton
    }

def options_menu(haunting_options, swarm_options, active_tab="Haunting", haunting_scroll=0, swarm_type_scroll=0, options_scroll_input=0):
    screen = ui_assets.screen
    Color = ui_assets.Color
    Fonts = ui_assets.Fonts
    Horizontal_Scale = ui_assets.Horizontal_Scale
    Vertical_Scale = ui_assets.Vertical_Scale
    MakeButton = ui_assets.MakeButton
    screen.fill(Color.MenuDark)
    pygame.draw.rect(screen, Color.MenuLight, (50 * Horizontal_Scale, 50 * Vertical_Scale, 900 * Horizontal_Scale, 530 * Vertical_Scale))
    text_surface = Fonts.font.render("Challenges", True, Color.MenuDarkSelect)
    text_rect = text_surface.get_rect(center=((50 + 900 / 2) * Horizontal_Scale, (30 + 100 / 2) * Vertical_Scale))
    screen.blit(text_surface, text_rect)

    tab_haunting = MakeButton(
        230,
        115,
        260,
        50,
        "Haunting",
        button_color=Color.MenuDarkSelect if active_tab == "Haunting" else Color.MenuDark,
        text_color=Color.MenuLight,
        Font=Fonts.bold,
    )
    tab_swarm = MakeButton(
        510,
        115,
        260,
        50,
        "Swarm",
        button_color=Color.MenuDarkSelect if active_tab == "Swarm" else Color.MenuDark,
        text_color=Color.MenuLight,
        Font=Fonts.bold,
    )

    mouse_x, mouse_y = pygame.mouse.get_pos()
    mouse_x = mouse_x / Horizontal_Scale
    mouse_y = mouse_y / Vertical_Scale

    toggle_buttons = {}
    enemy_type_buttons = {}
    swarm_enabled_button = None

    option_names = ["Chaser", "Dasher", "Blaster", "Ghost", "Spiker", "Guardian", "Warper", "Turret"]
    if active_tab == "Haunting":
        description_lines = [
            "Checked enemies spawn as haunted variants.",
            "This compact list supports mouse-wheel scrolling.",
        ]
        for index, line in enumerate(description_lines):
            line_surface = Fonts.suble.render(line, True, Color.MenuDark)
            line_rect = line_surface.get_rect(center=((50 + 900 / 2) * Horizontal_Scale, (188 + index * 24) * Vertical_Scale))
            screen.blit(line_surface, line_rect)

        panel_x = 210
        panel_y = 250
        panel_width = 580
        row_height = 56
        row_gap = 12
        visible_count = 5
        max_scroll = max(0, len(option_names) - visible_count)
        haunting_scroll = max(0, min(max_scroll, haunting_scroll - options_scroll_input))

        for index, enemy_name in enumerate(option_names[haunting_scroll:haunting_scroll + visible_count]):
            row_y = panel_y + index * (row_height + row_gap)
            row_rect = pygame.Rect(
                int(panel_x * Horizontal_Scale),
                int(row_y * Vertical_Scale),
                int(panel_width * Horizontal_Scale),
                int(row_height * Vertical_Scale),
            )
            hovered = panel_x <= mouse_x <= panel_x + panel_width and row_y <= mouse_y <= row_y + row_height
            row_color = (95, 160, 186) if hovered else (103, 170, 196)
            pygame.draw.rect(screen, row_color, row_rect, border_radius=10)
            pygame.draw.rect(screen, Color.MenuDark, row_rect, 3, border_radius=10)

            checkbox_size = 26
            checkbox_x = panel_x + 20
            checkbox_y = row_y + (row_height - checkbox_size) / 2
            checkbox_rect = pygame.Rect(
                int(checkbox_x * Horizontal_Scale),
                int(checkbox_y * Vertical_Scale),
                int(checkbox_size * Horizontal_Scale),
                int(checkbox_size * Vertical_Scale),
            )
            pygame.draw.rect(screen, (236, 242, 245), checkbox_rect, border_radius=4)
            pygame.draw.rect(screen, Color.MenuDark, checkbox_rect, 2, border_radius=4)

            if haunting_options.get(enemy_name, False):
                check_points = [
                    (checkbox_x + 5, checkbox_y + 13),
                    (checkbox_x + 11, checkbox_y + 20),
                    (checkbox_x + 21, checkbox_y + 6),
                ]
                scaled_points = [(point_x * Horizontal_Scale, point_y * Vertical_Scale) for point_x, point_y in check_points]
                pygame.draw.lines(screen, Color.MenuDarkSelect, False, scaled_points, 4)

            label_surface = Fonts.bold.render(enemy_name + " haunting", True, Color.MenuDark)
            label_rect = label_surface.get_rect(midleft=((panel_x + 62) * Horizontal_Scale, (row_y + row_height / 2) * Vertical_Scale))
            screen.blit(label_surface, label_rect)

            toggle_buttons[enemy_name] = ui_assets.Button(panel_x, row_y, panel_width, row_height)

        if len(option_names) > visible_count:
            track_rect = pygame.Rect(
                int((panel_x + panel_width + 14) * Horizontal_Scale),
                int(panel_y * Vertical_Scale),
                int(12 * Horizontal_Scale),
                int((visible_count * row_height + (visible_count - 1) * row_gap) * Vertical_Scale),
            )
            pygame.draw.rect(screen, (48, 74, 94), track_rect, border_radius=5)
            handle_height = max(int(track_rect.height * (visible_count / len(option_names))), int(22 * Vertical_Scale))
            travel = max(1, track_rect.height - handle_height)
            handle_y = track_rect.y + round((haunting_scroll / max_scroll) * travel)
            handle_rect = pygame.Rect(track_rect.x, handle_y, track_rect.width, handle_height)
            pygame.draw.rect(screen, Color.MenuLightSelect, handle_rect, border_radius=5)

    else:
        description_lines = [
            "Enable a swarm to add extra enemies each wave.",
            "Each selected swarm type adds +50% of the base wave enemy count.",
            "Each selected swarm type grants +15% EXP while swarm is enabled.",
        ]
        for index, line in enumerate(description_lines):
            line_surface = Fonts.suble.render(line, True, Color.MenuDark)
            line_rect = line_surface.get_rect(center=((50 + 900 / 2) * Horizontal_Scale, (188 + index * 24) * Vertical_Scale))
            screen.blit(line_surface, line_rect)

        row_x = 210
        row_y = 250
        row_width = 580
        row_height = 56

        enabled_rect = pygame.Rect(
            int(row_x * Horizontal_Scale),
            int(row_y * Vertical_Scale),
            int(row_width * Horizontal_Scale),
            int(row_height * Vertical_Scale),
        )
        pygame.draw.rect(screen, (103, 170, 196), enabled_rect, border_radius=10)
        pygame.draw.rect(screen, Color.MenuDark, enabled_rect, 3, border_radius=10)

        checkbox_size = 26
        checkbox_x = row_x + 20
        checkbox_y = row_y + (row_height - checkbox_size) / 2
        checkbox_rect = pygame.Rect(
            int(checkbox_x * Horizontal_Scale),
            int(checkbox_y * Vertical_Scale),
            int(checkbox_size * Horizontal_Scale),
            int(checkbox_size * Vertical_Scale),
        )
        pygame.draw.rect(screen, (236, 242, 245), checkbox_rect, border_radius=4)
        pygame.draw.rect(screen, Color.MenuDark, checkbox_rect, 2, border_radius=4)

        if swarm_options.get("enabled", False):
            check_points = [
                (checkbox_x + 5, checkbox_y + 13),
                (checkbox_x + 11, checkbox_y + 20),
                (checkbox_x + 21, checkbox_y + 6),
            ]
            scaled_points = [(point_x * Horizontal_Scale, point_y * Vertical_Scale) for point_x, point_y in check_points]
            pygame.draw.lines(screen, Color.MenuDarkSelect, False, scaled_points, 4)

        enabled_label = Fonts.bold.render("Enable swarm", True, Color.MenuDark)
        enabled_label_rect = enabled_label.get_rect(midleft=((row_x + 62) * Horizontal_Scale, (row_y + row_height / 2) * Vertical_Scale))
        screen.blit(enabled_label, enabled_label_rect)
        swarm_enabled_button = ui_assets.Button(row_x, row_y, row_width, row_height)

        list_title = Fonts.suble.render("Swarm enemy type", True, Color.MenuDark)
        list_title_rect = list_title.get_rect(midleft=((row_x) * Horizontal_Scale, (328) * Vertical_Scale))
        screen.blit(list_title, list_title_rect)

        type_row_y = 340
        type_row_height = 44
        type_row_gap = 8
        visible_count = 4
        max_scroll = max(0, len(option_names) - visible_count)
        swarm_type_scroll = max(0, min(max_scroll, swarm_type_scroll - options_scroll_input))

        for index, enemy_name in enumerate(option_names[swarm_type_scroll:swarm_type_scroll + visible_count]):
            row_y = type_row_y + index * (type_row_height + type_row_gap)
            selected_swarm_types = swarm_options.get("enemy_types", [])
            if not selected_swarm_types and swarm_options.get("enemy_type"):
                selected_swarm_types = [swarm_options.get("enemy_type")]
            is_selected = enemy_name in selected_swarm_types
            row_rect = pygame.Rect(
                int(row_x * Horizontal_Scale),
                int(row_y * Vertical_Scale),
                int(row_width * Horizontal_Scale),
                int(type_row_height * Vertical_Scale),
            )
            row_color = Color.MenuLightSelect if is_selected else (103, 170, 196)
            pygame.draw.rect(screen, row_color, row_rect, border_radius=10)
            pygame.draw.rect(screen, Color.MenuDark, row_rect, 2, border_radius=10)

            checkbox_size = 20
            checkbox_x = row_x + 14
            checkbox_y = row_y + (type_row_height - checkbox_size) / 2
            checkbox_rect = pygame.Rect(
                int(checkbox_x * Horizontal_Scale),
                int(checkbox_y * Vertical_Scale),
                int(checkbox_size * Horizontal_Scale),
                int(checkbox_size * Vertical_Scale),
            )
            pygame.draw.rect(screen, (236, 242, 245), checkbox_rect, border_radius=4)
            pygame.draw.rect(screen, Color.MenuDark, checkbox_rect, 2, border_radius=4)

            if is_selected:
                check_points = [
                    (checkbox_x + 4, checkbox_y + 10),
                    (checkbox_x + 8, checkbox_y + 15),
                    (checkbox_x + 16, checkbox_y + 5),
                ]
                scaled_points = [(point_x * Horizontal_Scale, point_y * Vertical_Scale) for point_x, point_y in check_points]
                pygame.draw.lines(screen, Color.MenuDarkSelect, False, scaled_points, 3)

            label_surface = Fonts.suble.render(enemy_name, True, Color.MenuDark)
            label_rect = label_surface.get_rect(midleft=((row_x + 44) * Horizontal_Scale, (row_y + type_row_height / 2) * Vertical_Scale))
            screen.blit(label_surface, label_rect)
            enemy_type_buttons[enemy_name] = ui_assets.Button(row_x, row_y, row_width, type_row_height)

        if len(option_names) > visible_count:
            track_rect = pygame.Rect(
                int((row_x + row_width + 14) * Horizontal_Scale),
                int(type_row_y * Vertical_Scale),
                int(12 * Horizontal_Scale),
                int((visible_count * type_row_height + (visible_count - 1) * type_row_gap) * Vertical_Scale),
            )
            pygame.draw.rect(screen, (48, 74, 94), track_rect, border_radius=5)
            handle_height = max(int(track_rect.height * (visible_count / len(option_names))), int(18 * Vertical_Scale))
            travel = max(1, track_rect.height - handle_height)
            handle_y = track_rect.y + round((swarm_type_scroll / max_scroll) * travel)
            handle_rect = pygame.Rect(track_rect.x, handle_y, track_rect.width, handle_height)
            pygame.draw.rect(screen, Color.MenuLightSelect, handle_rect, border_radius=5)

    Back = MakeButton(75, 75, 125, 50, "Back", button_color=Color.MenuDark)
    return {
        "Back": Back,
        "TabButtons": {"Haunting": tab_haunting, "Swarm": tab_swarm},
        "ToggleButtons": toggle_buttons,
        "SwarmEnabledButton": swarm_enabled_button,
        "EnemyTypeButtons": enemy_type_buttons,
        "HauntingScrollOffset": haunting_scroll,
        "SwarmTypeScrollOffset": swarm_type_scroll,
    }

def tutorial_menu(selected_index=0, scroll_offset=0, scroll_input=0, notice=""):
    import os
    import Background.maps as maps_module
    from Background.tutorials import TUTORIALS

    screen = ui_assets.screen
    Color = ui_assets.Color
    Fonts = ui_assets.Fonts
    Horizontal_Scale = ui_assets.Horizontal_Scale
    Vertical_Scale = ui_assets.Vertical_Scale
    MakeButton = ui_assets.MakeButton

    visible_count = 6
    row_height = 52
    gap = 6
    max_scroll = max(0, len(TUTORIALS) - visible_count)
    scroll_offset = max(0, min(max_scroll, scroll_offset - scroll_input))
    selected_index = max(0, min(len(TUTORIALS) - 1, selected_index))

    screen.fill(Color.MenuDark)
    pygame.draw.rect(screen, Color.MenuLight, (50 * Horizontal_Scale, 50 * Vertical_Scale, 900 * Horizontal_Scale, 530 * Vertical_Scale))
    text_surface = Fonts.font.render("Tutorials", True, Color.MenuDarkSelect)
    text_rect = text_surface.get_rect(center=((50 + 900 / 2) * Horizontal_Scale, (30 + 100 / 2) * Vertical_Scale))
    screen.blit(text_surface, text_rect)

    Back = MakeButton(75, 75, 125, 50, "Back", button_color=Color.MenuDark)

    list_rect = pygame.Rect(int(95 * Horizontal_Scale), int(150 * Vertical_Scale), int(270 * Horizontal_Scale), int(380 * Vertical_Scale))
    pygame.draw.rect(screen, Color.MenuDark, list_rect)
    pygame.draw.rect(screen, Color.MenuDarkSelect, list_rect, 3)

    entry_buttons = []
    for i, tutorial in enumerate(TUTORIALS[scroll_offset:scroll_offset + visible_count]):
        real_index = i + scroll_offset
        button_color = Color.MenuDarkSelect if real_index == selected_index else Color.MenuDark
        button = MakeButton(105, 162 + i * (row_height + gap), 240, row_height, tutorial["name"], button_color=button_color, Font=Fonts.suble)
        entry_buttons.append({"index": real_index, "button": button})

    if len(TUTORIALS) > visible_count:
        track_height = visible_count * row_height + (visible_count - 1) * gap
        track_rect = pygame.Rect(int(350 * Horizontal_Scale), int(162 * Vertical_Scale), int(8 * Horizontal_Scale), int(track_height * Vertical_Scale))
        pygame.draw.rect(screen, (45, 70, 90), track_rect)
        handle_height = max(int(track_rect.height * (visible_count / len(TUTORIALS))), int(24 * Vertical_Scale))
        travel = max(1, track_rect.height - handle_height)
        handle_y = track_rect.y + round((scroll_offset / max_scroll) * travel)
        pygame.draw.rect(screen, Color.MenuLightSelect, pygame.Rect(track_rect.x, handle_y, track_rect.width, handle_height))

    selected = TUTORIALS[selected_index]

    icon_rect = pygame.Rect(int(405 * Horizontal_Scale), int(150 * Vertical_Scale), int(190 * Horizontal_Scale), int(190 * Vertical_Scale))
    icon = None
    icon_data = selected.get("icon")
    if icon_data:
        icon = pygame.Surface((maps_module.ICON_SIZE, maps_module.ICON_SIZE), pygame.SRCALPHA)
        for y, row in enumerate(icon_data):
            for x, digit in enumerate(row):
                color = maps_module.ICON_PALETTE[int(digit, 16)]
                if color is not None:
                    icon.set_at((x, y), color)
    else:
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Assets", "Achivements", "error_icon.png")
        icon = _load_achievement_image(icon_path)
    pygame.draw.rect(screen, (20, 40, 55), icon_rect)
    if icon is not None:
        fitted = _scale_pixelperfect_to_fill(icon, icon_rect.width, icon_rect.height)
        screen.blit(fitted, fitted.get_rect(center=icon_rect.center))
    pygame.draw.rect(screen, Color.MenuDarkSelect, icon_rect, 3)

    name_surface = Fonts.bold.render(selected["name"], True, Color.MenuDarkSelect)
    screen.blit(name_surface, name_surface.get_rect(center=(500 * Horizontal_Scale, 370 * Vertical_Scale)))

    detail_rect = pygame.Rect(int(625 * Horizontal_Scale), int(150 * Vertical_Scale), int(280 * Horizontal_Scale), int(380 * Vertical_Scale))
    pygame.draw.rect(screen, (24, 65, 85), detail_rect)
    pygame.draw.rect(screen, Color.MenuDarkSelect, detail_rect, 3)
    _draw_wrapped_text(
        screen,
        selected["description"],
        Fonts.suble,
        Color.MenuLight,
        int(640 * Horizontal_Scale),
        int(165 * Vertical_Scale),
        int(250 * Horizontal_Scale),
        14,
    )

    RunButton = MakeButton(400, 440, 200, 60, "Run", button_color=Color.MenuDark, text_color=Color.MenuLight)
    if notice:
        notice_surface = Fonts.tiny.render(notice, True, Color.MenuDarkSelect)
        screen.blit(notice_surface, notice_surface.get_rect(center=(500 * Horizontal_Scale, 520 * Vertical_Scale)))

    return {
        'Back': Back,
        'RunButton': RunButton,
        'EntryButtons': entry_buttons,
        'ScrollOffset': scroll_offset,
        'SelectedIndex': selected_index,
    }

def run_setup_menu(map_options, map_index, difficulty, body_name, gun_name):
    screen = ui_assets.screen
    Color = ui_assets.Color
    Fonts = ui_assets.Fonts
    Horizontal_Scale = ui_assets.Horizontal_Scale
    Vertical_Scale = ui_assets.Vertical_Scale
    MakeButton = ui_assets.MakeButton

    screen.fill(Color.MenuDark)
    pygame.draw.rect(screen, Color.MenuLight, (50 * Horizontal_Scale, 50 * Vertical_Scale, 900 * Horizontal_Scale, 530 * Vertical_Scale))
    title = Fonts.font.render("New Run", True, Color.MenuDarkSelect)
    screen.blit(title, title.get_rect(center=(500 * Horizontal_Scale, 80 * Vertical_Scale)))

    Back = MakeButton(75, 75, 125, 50, "Back", button_color=Color.MenuDark)

    def label(text, y):
        surface = Fonts.bold.render(text, True, Color.MenuDarkSelect)
        screen.blit(surface, surface.get_rect(center=(500 * Horizontal_Scale, y * Vertical_Scale)))

    label("Map", 160)
    MapPrev = MakeButton(150, 180, 70, 60, "<", button_color=Color.MenuDark, text_color=Color.MenuLight)
    MapNext = MakeButton(780, 180, 70, 60, ">", button_color=Color.MenuDark, text_color=Color.MenuLight)
    MakeButton(235, 180, 530, 60, map_options[map_index], button_color=Color.MenuDark, text_color=Color.MenuLight, outline=False)

    label("Difficulty", 270)
    difficulty_buttons = {}
    for i in range(1, 6):
        selected = i == difficulty
        difficulty_buttons[i] = MakeButton(
            200 + (i - 1) * 120, 290, 100, 60, str(i),
            button_color=Color.MenuDarkSelect if selected else Color.MenuDark,
            text_color=Color.MenuLight,
        )

    label("Current Build", 385)
    build_text = Fonts.font.render(f"{body_name}  +  {gun_name}", True, Color.MenuDark)
    screen.blit(build_text, build_text.get_rect(center=(500 * Horizontal_Scale, 425 * Vertical_Scale)))

    StartButton = MakeButton(375, 470, 250, 70, "Start", button_color=Color.MenuDark, text_color=Color.MenuLight)

    return {
        'Back': Back,
        'MapPrev': MapPrev,
        'MapNext': MapNext,
        'DifficultyButtons': difficulty_buttons,
        'StartButton': StartButton,
    }


def achievements_menu(selected_index=0, scroll_offset=0, scroll_input=0, active_category="Player/Gun"):
    screen = ui_assets.screen
    Color = ui_assets.Color
    Fonts = ui_assets.Fonts
    Horizontal_Scale = ui_assets.Horizontal_Scale
    Vertical_Scale = ui_assets.Vertical_Scale
    MakeButton = ui_assets.MakeButton

    achievement_entries_all = _build_achievements_data()
    preferred_categories = ["Player/Gun", "Haunting", "Swarm", "Slayer", "Level", "Secret"]
    category_short_labels = {
        "Player/Gun": "P/G",
        "Haunting": "Haunt",
        "Swarm": "Swarm",
        "Slayer": "Slayer",
        "Level": "Level",
        "Secret": "Secret",
    }
    category_counts = {category: {"completed": 0, "total": 0} for category in preferred_categories}
    for entry in achievement_entries_all:
        category = entry.get("category", "Player/Gun")
        if category not in category_counts:
            continue
        category_counts[category]["total"] += 1
        if entry.get("completed", False):
            category_counts[category]["completed"] += 1
    categories = [
        category for category in preferred_categories
        if category_counts.get(category, {}).get("total", 0) > 0
    ]
    if not categories:
        categories = ["Player/Gun"]

    if active_category not in categories:
        active_category = categories[0]
    achievement_entries = [
        entry for entry in achievement_entries_all if entry.get("category", "Player/Gun") == active_category
    ]
    visible_count = 6
    max_scroll = max(0, len(achievement_entries) - visible_count)
    scroll_offset = max(0, min(max_scroll, scroll_offset - scroll_input))
    selected_index = max(0, min(len(achievement_entries) - 1, selected_index)) if achievement_entries else 0

    screen.fill(Color.MenuDark)
    pygame.draw.rect(screen, Color.MenuLight, (50 * Horizontal_Scale, 50 * Vertical_Scale, 900 * Horizontal_Scale, 530 * Vertical_Scale))
    text_surface = Fonts.font.render("Achievements", True, Color.MenuDarkSelect)
    text_rect = text_surface.get_rect(center=((50 + 900 / 2) * Horizontal_Scale, (30 + 100 / 2) * Vertical_Scale))
    screen.blit(text_surface, text_rect)

    subtitle = Fonts.suble.render("Select an achievement to view details", True, Color.MenuDark)
    subtitle_rect = subtitle.get_rect(center=((50 + 900 / 2) * Horizontal_Scale, (77 + 100 / 2) * Vertical_Scale))
    screen.blit(subtitle, subtitle_rect)

    Back = MakeButton(75, 75, 125, 50, "Back", button_color=Color.MenuDark)

    tab_buttons = {}
    tab_start_x = 95
    tab_y = 118
    tab_height = 42
    tab_gap = 8
    max_tabs_width = 810
    tab_width = int((max_tabs_width - (len(categories) - 1) * tab_gap) / max(1, len(categories)))
    tab_width = max(110, min(140, tab_width))
    for tab_index, category in enumerate(categories):
        completed_count = category_counts[category]["completed"]
        total_count = category_counts[category]["total"]
        short_label = category_short_labels.get(category, category)
        tab_label = f"{short_label} {completed_count}/{total_count}"
        tab_buttons[category] = MakeButton(
            tab_start_x + tab_index * (tab_width + tab_gap),
            tab_y,
            tab_width,
            tab_height,
            tab_label,
            button_color=Color.MenuDarkSelect if category == active_category else Color.MenuDark,
            Font=Fonts.tiny,
        )

    side_panel_rect = pygame.Rect(
        int(95 * Horizontal_Scale),
        int(170 * Vertical_Scale),
        int(300 * Horizontal_Scale),
        int(370 * Vertical_Scale)
    )
    pygame.draw.rect(screen, Color.MenuDark, side_panel_rect)
    pygame.draw.rect(screen, Color.MenuDarkSelect, side_panel_rect, 3)

    entry_buttons = []
    row_height = 50
    gap = 6
    start_y = 182
    for i, entry in enumerate(achievement_entries[scroll_offset:scroll_offset + visible_count]):
        real_index = i + scroll_offset
        is_selected = real_index == selected_index
        is_completed = entry.get("completed", False)
        is_secret_locked = bool(entry.get("secret", False)) and not is_completed
        button_title = entry.get("locked_title", "Hidden Secret") if is_secret_locked else entry["title"]
        button_label = button_title + (" *" if is_completed else "")
        button_color = Color.MenuDarkSelect if is_selected else Color.MenuDark
        button = MakeButton(110, start_y + i * (row_height + gap), 270, row_height, button_label, button_color=button_color, Font=Fonts.suble)
        entry_buttons.append({"index": real_index, "button": button})

    if len(achievement_entries) > visible_count:
        track_rect = pygame.Rect(
            int(385 * Horizontal_Scale),
            int(start_y * Vertical_Scale),
            int(8 * Horizontal_Scale),
            int((visible_count * row_height + (visible_count - 1) * gap) * Vertical_Scale)
        )
        pygame.draw.rect(screen, (45, 70, 90), track_rect)
        handle_height = max(int(track_rect.height * (visible_count / len(achievement_entries))), int(24 * Vertical_Scale))
        travel = max(1, track_rect.height - handle_height)
        handle_y = track_rect.y + round((scroll_offset / max_scroll) * travel)
        handle_rect = pygame.Rect(track_rect.x, handle_y, track_rect.width, handle_height)
        pygame.draw.rect(screen, Color.MenuLightSelect, handle_rect)

    detail_rect = pygame.Rect(
        int(420 * Horizontal_Scale),
        int(170 * Vertical_Scale),
        int(475 * Horizontal_Scale),
        int(370 * Vertical_Scale)
    )
    pygame.draw.rect(screen, (24, 65, 85), detail_rect)
    pygame.draw.rect(screen, Color.MenuDarkSelect, detail_rect, 3)

    if achievement_entries:
        selected_entry = achievement_entries[selected_index]
        is_secret_locked = bool(selected_entry.get("secret", False)) and not bool(selected_entry.get("completed", False))
        completed = selected_entry.get("completed", False)
        if is_secret_locked:
            status_text = "LOCKED"
            status_color = (190, 190, 190)
            entry_title = selected_entry.get("locked_title", "Hidden Secret")
            entry_paragraph = selected_entry.get("locked_paragraph", "No information is shown until this secret achievement is unlocked.")
        else:
            status_text = "COMPLETED" if completed else "IN PROGRESS"
            status_color = (95, 220, 110) if completed else (210, 210, 210)
            entry_title = selected_entry["title"]
            entry_paragraph = selected_entry["paragraph"]

        title_surface = Fonts.bold.render(entry_title, True, Color.MenuLight)
        screen.blit(title_surface, (int(440 * Horizontal_Scale), int(185 * Vertical_Scale)))

        status_surface = Fonts.tiny.render(status_text, True, status_color)
        screen.blit(status_surface, (int(440 * Horizontal_Scale), int(220 * Vertical_Scale)))

        image_rect = pygame.Rect(
            int(440 * Horizontal_Scale),
            int(245 * Vertical_Scale),
            int(170 * Horizontal_Scale),
            int(190 * Vertical_Scale)
        )
        _draw_achievement_preview(screen, image_rect, selected_entry)

        _draw_wrapped_text(
            screen,
            entry_paragraph,
            Fonts.suble,
            Color.MenuLight,
            int(630 * Horizontal_Scale),
            int(250 * Vertical_Scale),
            int(240 * Horizontal_Scale),
            10,
        )

    return {
        'Back': Back,
        'EntryButtons': entry_buttons,
        'TabButtons': tab_buttons,
        'Category': active_category,
        'ScrollOffset': scroll_offset,
        'SelectedIndex': selected_index,
    }

def customisations_menu(MouseClick, selected_body, selected_gun, body_scroll=0, gun_scroll=0, scroll_input=0, mouse_x=0, mouse_y=0):
    screen = ui_assets.screen
    Color = ui_assets.Color
    Fonts = ui_assets.Fonts
    Horizontal_Scale = ui_assets.Horizontal_Scale
    Vertical_Scale = ui_assets.Vertical_Scale
    MakeButton = ui_assets.MakeButton
    screen.fill(Color.MenuDark)
    pygame.draw.rect(screen, Color.MenuLight, (50 * Horizontal_Scale, 50 * Vertical_Scale, 900 * Horizontal_Scale, 530 * Vertical_Scale))
    text_surface = Fonts.font.render("Customisations", True, Color.MenuDarkSelect)
    text_rect = text_surface.get_rect(center=((50 + 900 / 2) * Horizontal_Scale, (30 + 100 / 2) * Vertical_Scale))
    screen.blit(text_surface, text_rect)
    text_surface = Fonts.suble.render("Pick a player body and gun for your next run.", True, Color.MenuDark)
    text_rect = text_surface.get_rect(center=((50 + 900 / 2) * Horizontal_Scale, (70 + 100 / 2) * Vertical_Scale))
    screen.blit(text_surface, text_rect)

    Back = MakeButton(75, 75, 125, 50, "Back", button_color=Color.MenuDark)

    body_buttons = {}
    gun_buttons = {}

    body_panel = pygame.Rect(100 * Horizontal_Scale, 180 * Vertical_Scale, 330 * Horizontal_Scale, 300 * Vertical_Scale)
    gun_panel = pygame.Rect(570 * Horizontal_Scale, 180 * Vertical_Scale, 330 * Horizontal_Scale, 300 * Vertical_Scale)
    pygame.draw.rect(screen, Color.MenuDark, body_panel, border_radius=18)
    pygame.draw.rect(screen, Color.MenuDark, gun_panel, border_radius=18)
    pygame.draw.rect(screen, Color.MenuDarkSelect, body_panel, 4, border_radius=18)
    pygame.draw.rect(screen, Color.MenuDarkSelect, gun_panel, 4, border_radius=18)

    body_label = Fonts.bold.render("Player Body", True, Color.MenuLight)
    gun_label = Fonts.bold.render("Gun", True, Color.MenuLight)
    screen.blit(body_label, body_label.get_rect(center=((265) * Horizontal_Scale, (210) * Vertical_Scale)))
    screen.blit(gun_label, gun_label.get_rect(center=((735) * Horizontal_Scale, (210) * Vertical_Scale)))

    visible_count = 3
    body_names = list(player_body.BODY_TYPES.keys())
    gun_names = list(player_body.GUN_TYPES.keys())

    max_body_scroll = max(0, len(body_names) - visible_count)
    max_gun_scroll = max(0, len(gun_names) - visible_count)

    body_panel_hover = pygame.Rect(100, 180, 330, 300).collidepoint(mouse_x, mouse_y)
    gun_panel_hover = pygame.Rect(570, 180, 330, 300).collidepoint(mouse_x, mouse_y)

    if scroll_input != 0:
        if body_panel_hover:
            body_scroll = max(0, min(max_body_scroll, body_scroll - scroll_input))
        elif gun_panel_hover:
            gun_scroll = max(0, min(max_gun_scroll, gun_scroll - scroll_input))

    body_start_y = 245
    for index, body_name in enumerate(body_names[body_scroll:body_scroll + visible_count]):
        is_selected = body_name == selected_body
        button_color = Color.MenuLightSelect if is_selected else Color.MenuLight
        select_color = Color.MenuDarkSelect if is_selected else Color.MenuLightSelect
        body_buttons[body_name] = MakeButton(
            130,
            body_start_y + index * 80,
            270,
            55,
            body_name,
            button_color=button_color,
            select_color=select_color,
            text_color=Color.MenuDark if is_selected else Color.MenuText,
            Font=Fonts.bold,
        )

    gun_start_y = 245
    for index, gun_name in enumerate(gun_names[gun_scroll:gun_scroll + visible_count]):
        is_selected = gun_name == selected_gun
        button_color = Color.MenuLightSelect if is_selected else Color.MenuLight
        select_color = Color.MenuDarkSelect if is_selected else Color.MenuLightSelect
        gun_buttons[gun_name] = MakeButton(
            600,
            gun_start_y + index * 80,
            270,
            55,
            gun_name,
            button_color=button_color,
            select_color=select_color,
            text_color=Color.MenuDark if is_selected else Color.MenuText,
            Font=Fonts.bold,
        )

    track_height = int((3 * 55 + 2 * 25) * Vertical_Scale)
    track_top = int(245 * Vertical_Scale)
    track_width = int(10 * Horizontal_Scale)

    if len(body_names) > visible_count:
        body_track = pygame.Rect(int(410 * Horizontal_Scale), track_top, track_width, track_height)
        pygame.draw.rect(screen, (45, 70, 90), body_track, border_radius=5)
        handle_height = max(int(body_track.height * (visible_count / len(body_names))), int(24 * Vertical_Scale))
        body_travel = max(1, body_track.height - handle_height)
        body_handle_y = body_track.y + round((body_scroll / max_body_scroll) * body_travel)
        body_handle = pygame.Rect(body_track.x, body_handle_y, body_track.width, handle_height)
        pygame.draw.rect(screen, Color.MenuLightSelect, body_handle, border_radius=5)

    if len(gun_names) > visible_count:
        gun_track = pygame.Rect(int(880 * Horizontal_Scale), track_top, track_width, track_height)
        pygame.draw.rect(screen, (45, 70, 90), gun_track, border_radius=5)
        handle_height = max(int(gun_track.height * (visible_count / len(gun_names))), int(24 * Vertical_Scale))
        gun_travel = max(1, gun_track.height - handle_height)
        gun_handle_y = gun_track.y + round((gun_scroll / max_gun_scroll) * gun_travel)
        gun_handle = pygame.Rect(gun_track.x, gun_handle_y, gun_track.width, handle_height)
        pygame.draw.rect(screen, Color.MenuLightSelect, gun_handle, border_radius=5)

    preview_rect = pygame.Rect(305 * Horizontal_Scale, 500 * Vertical_Scale, 390 * Horizontal_Scale, 55 * Vertical_Scale)
    pygame.draw.rect(screen, Color.MenuDark, preview_rect, border_radius=14)
    pygame.draw.rect(screen, Color.MenuDarkSelect, preview_rect, 3, border_radius=14)
    preview_text = Fonts.suble.render(selected_body + " with " + selected_gun, True, Color.MenuLight)
    preview_rect_text = preview_text.get_rect(center=((500) * Horizontal_Scale, (527) * Vertical_Scale))
    screen.blit(preview_text, preview_rect_text)

    _draw_multiline_centered_text(
        screen,
        player_body.BODY_SUMMARIES.get(selected_body, ""),
        Fonts.tiny,
        Color.MenuDarkSelect,
        int(265 * Horizontal_Scale),
        int(150 * Vertical_Scale),
        int(250 * Horizontal_Scale),
        2,
    )
    _draw_multiline_centered_text(
        screen,
        player_body.GUN_SUMMARIES.get(selected_gun, ""),
        Fonts.tiny,
        Color.MenuDarkSelect,
        int(735 * Horizontal_Scale),
        int(150 * Vertical_Scale),
        int(250 * Horizontal_Scale),
        2,
    )

    return {
        'Back': Back,
        'BodyButtons': body_buttons,
        'GunButtons': gun_buttons,
        'BodyScrollOffset': body_scroll,
        'GunScrollOffset': gun_scroll,
    }

def credits_menu(MouseClick):
    screen = ui_assets.screen
    Color = ui_assets.Color
    Fonts = ui_assets.Fonts
    Horizontal_Scale = ui_assets.Horizontal_Scale
    Vertical_Scale = ui_assets.Vertical_Scale
    MakeButton = ui_assets.MakeButton
    screen.fill(Color.MenuDark)
    pygame.draw.rect(screen, Color.MenuLight, (50 * Horizontal_Scale, 50 * Vertical_Scale, 900 * Horizontal_Scale, 530 * Vertical_Scale))
    text_surface = Fonts.font.render("Credits", True, Color.MenuDarkSelect)
    text_rect = text_surface.get_rect(center=((50 + 900 / 2) * Horizontal_Scale, (30 + 100 / 2) * Vertical_Scale))
    screen.blit(text_surface, text_rect)
    text_surface = Fonts.font.render("There's nothing here yet", True, Color.MenuDark)
    text_rect = text_surface.get_rect(center=((50 + 900 / 2) * Horizontal_Scale, (160 + 100 / 2) * Vertical_Scale))
    screen.blit(text_surface, text_rect)
    Back = MakeButton(75, 75, 125, 50, "Back", button_color=Color.MenuDark)
    return Back
