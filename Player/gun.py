from Player.bullets import Bullet, Poison, Bomb, SlashBullet, Fire
import math
import pygame
import random
from helpers import Vector


class Gun:
    def __init__(self, owner):
        self.owner = owner
        self.rotation = "right"

    def update(self):
        self.owner.attack_cooldown = max(0, self.owner.attack_cooldown - 1)

    def shoot(self, direction, bullets, ignore_cooldown=False):
        if ignore_cooldown or self.owner.attack_cooldown <= 0:
            if not ignore_cooldown:
                self.owner.attack_cooldown = self.owner.attack_speed

            # Calculate bullet direction
            direction_map = {
                "up": Vector(0, -1),
                "down": Vector(0, 1),
                "left": Vector(-1, 0),
                "right": Vector(1, 0),
                "up-left": Vector(-1, -1).normalize(),
                "up-right": Vector(1, -1).normalize(),
                "down-left": Vector(-1, 1).normalize(),
                "down-right": Vector(1, 1).normalize(),
            }

            self.rotation = direction if direction in direction_map else "right"
            bullet_velocity = direction_map.get(direction, Vector(1, 0))

            bullet_velocity = bullet_velocity.multiply(self.owner.bullet_speed)

            for i in range(self.owner.multishot):
                angle = (i - self.owner.multishot // 2) * self.owner.attack_spread
                rotated_velocity = Vector(
                    bullet_velocity.x * math.cos(angle)
                    - bullet_velocity.y * math.sin(angle),
                    bullet_velocity.x * math.sin(angle)
                    + bullet_velocity.y * math.cos(angle),
                )
                shell = Bomb(
                    self.owner.x,
                    self.owner.y,
                    rotated_velocity,
                    self.owner.damage,
                    self.owner.pierce,
                    self.owner.attack_range,
                    5,
                    self.owner.bullet_color,
                    self.owner.knockback,
                )
                if not self.owner.gun_effect_unlocked:
                    shell.explosion_radius += 20
                bullets.append(shell)

    def draw(self, player, screen):
        rotation_draw_map = {
            "right": [
                (player.x - 5, player.y - 5),
                (player.x + 10, player.y),
                (player.x - 5, player.y + 5),
            ],
            "left": [
                (player.x + 5, player.y - 5),
                (player.x - 10, player.y),
                (player.x + 5, player.y + 5),
            ],
            "up": [
                (player.x - 5, player.y + 5),
                (player.x, player.y - 10),
                (player.x + 5, player.y + 5),
            ],
            "down": [
                (player.x - 5, player.y - 5),
                (player.x, player.y + 10),
                (player.x + 5, player.y - 5),
            ],
            "up-left": [
                (player.x + 5, player.y),
                (player.x - 7, player.y - 7),
                (player.x, player.y + 5),
            ],
            "up-right": [
                (player.x - 5, player.y),
                (player.x + 7, player.y - 7),
                (player.x, player.y + 5),
            ],
            "down-left": [
                (player.x + 5, player.y),
                (player.x - 7, player.y + 7),
                (player.x, player.y - 5),
            ],
            "down-right": [
                (player.x - 5, player.y),
                (player.x + 7, player.y + 7),
                (player.x, player.y - 5),
            ],
        }
        if self.rotation in rotation_draw_map:
            pygame.draw.polygon(
                screen, (200, 200, 200), rotation_draw_map[self.rotation]
            )


class Shotgun(Gun):
    def __init__(self, owner):
        super().__init__(owner)

    def shoot(self, direction, bullets, ignore_cooldown=False):
        o = self.owner
        if ignore_cooldown or o.attack_cooldown <= 0:
            if not ignore_cooldown:
                o.attack_cooldown = o.attack_speed
            # Calculate bullet direction
            if direction == "up":
                self.rotation = "up"
                bullet_velocity = Vector(0, -1)
            elif direction == "down":
                self.rotation = "down"
                bullet_velocity = Vector(0, 1)
            elif direction == "left":
                self.rotation = "left"
                bullet_velocity = Vector(-1, 0)
            elif direction == "right":
                self.rotation = "right"
                bullet_velocity = Vector(1, 0)
            elif direction == "up-left":
                self.rotation = "up-left"
                bullet_velocity = Vector(-1, -1).normalize()
            elif direction == "up-right":
                self.rotation = "up-right"
                bullet_velocity = Vector(1, -1).normalize()
            elif direction == "down-left":
                self.rotation = "down-left"
                bullet_velocity = Vector(-1, 1).normalize()
            elif direction == "down-right":
                self.rotation = "down-right"
                bullet_velocity = Vector(1, 1).normalize()
            bullet_velocity = bullet_velocity.multiply(o.bullet_speed)
            spread_mult = 1.0
            multishot_count = o.multishot
            if getattr(o, "gun_effect_unlocked", False):
                spread_mult = 2.0  # Spread increased a lot
                multishot_count = round(o.multishot * 2.5)  # Multishot doubled
            for i in range(multishot_count):
                angle = (i - multishot_count // 2) * o.attack_spread * 1.4 * spread_mult
                rotated_velocity = Vector(
                    bullet_velocity.x * math.cos(angle)
                    - bullet_velocity.y * math.sin(angle),
                    bullet_velocity.x * math.sin(angle)
                    + bullet_velocity.y * math.cos(angle),
                )
                bullets.append(
                    Bullet(
                        o.x,
                        o.y,
                        rotated_velocity,
                        o.damage,
                        o.pierce,
                        o.attack_range,
                        5,
                        o.bullet_color,
                        o.knockback,
                    )
                )
            if getattr(o, "gun_effect_unlocked", False):
                bullets.append(
                    Bullet(
                        o.x,
                        o.y,
                        bullet_velocity,
                        o.damage + 1,
                        o.pierce,
                        o.attack_range,
                        5,
                        o.bullet_color,
                        o.knockback,
                    )
                )


class Blowdart(Gun):
    def __init__(self, owner):
        super().__init__(owner)

    def shoot(self, direction, bullets, ignore_cooldown=False):
        o = self.owner
        if ignore_cooldown or o.attack_cooldown <= 0:
            if not ignore_cooldown:
                o.attack_cooldown = o.attack_speed * 1.2
            # Calculate bullet direction
            if direction == "up":
                self.rotation = "up"
                bullet_velocity = Vector(0, -1)
            elif direction == "down":
                self.rotation = "down"
                bullet_velocity = Vector(0, 1)
            elif direction == "left":
                self.rotation = "left"
                bullet_velocity = Vector(-1, 0)
            elif direction == "right":
                self.rotation = "right"
                bullet_velocity = Vector(1, 0)
            elif direction == "up-left":
                self.rotation = "up-left"
                bullet_velocity = Vector(-1, -1).normalize()
            elif direction == "up-right":
                self.rotation = "up-right"
                bullet_velocity = Vector(1, -1).normalize()
            elif direction == "down-left":
                self.rotation = "down-left"
                bullet_velocity = Vector(-1, 1).normalize()
            elif direction == "down-right":
                self.rotation = "down-right"
                bullet_velocity = Vector(1, 1).normalize()
            bullet_velocity = bullet_velocity.multiply(o.bullet_speed)
            for i in range(o.multishot):
                angle = (i - o.multishot // 2) * o.attack_spread * 1.2
                rotated_velocity = Vector(
                    bullet_velocity.x * math.cos(angle)
                    - bullet_velocity.y * math.sin(angle),
                    bullet_velocity.x * math.sin(angle)
                    + bullet_velocity.y * math.cos(angle),
                )
                dart = Poison(
                    o.x,
                    o.y,
                    rotated_velocity,
                    o.damage,
                    o.pierce,
                    o.attack_range,
                    5,
                    o.bullet_color,
                    o.knockback,
                )
                if getattr(o, "gun_effect_unlocked", False):
                    dart.poison_duration += 45
                    dart.poison_duration *= 2  # Poison effect twice as long
                bullets.append(dart)


class Cannon(Gun):
    def __init__(self, owner):
        super().__init__(owner)

    def shoot(self, direction, bullets, ignore_cooldown=False):
        o = self.owner
        if ignore_cooldown or o.attack_cooldown <= 0:
            if not ignore_cooldown:
                o.attack_cooldown = o.attack_speed * 2
            # Calculate bullet direction
            if direction == "up":
                self.rotation = "up"
                bullet_velocity = Vector(0, -1)
            elif direction == "down":
                self.rotation = "down"
                bullet_velocity = Vector(0, 1)
            elif direction == "left":
                self.rotation = "left"
                bullet_velocity = Vector(-1, 0)
            elif direction == "right":
                self.rotation = "right"
                bullet_velocity = Vector(1, 0)
            elif direction == "up-left":
                self.rotation = "up-left"
                bullet_velocity = Vector(-1, -1).normalize()
            elif direction == "up-right":
                self.rotation = "up-right"
                bullet_velocity = Vector(1, -1).normalize()
            elif direction == "down-left":
                self.rotation = "down-left"
                bullet_velocity = Vector(-1, 1).normalize()
            elif direction == "down-right":
                self.rotation = "down-right"
                bullet_velocity = Vector(1, 1).normalize()
            bullet_velocity = bullet_velocity.multiply(o.bullet_speed)
            for i in range(o.multishot // 3):
                bomb = Bomb(
                    o.x,
                    o.y,
                    bullet_velocity,
                    o.damage,
                    o.pierce,
                    o.attack_range,
                    5,
                    o.bullet_color,
                    o.knockback,
                    fuse=i,
                )
                if getattr(o, "gun_effect_unlocked", False):
                    bomb.explosion_radius *= 2  # Blast radius doubled
                    bomb.size *= 2  # Bomb size increased
                bullets.append(bomb)


class Blade(Gun):
    def __init__(self, owner):
        super().__init__(owner)

    def shoot(self, direction, bullets, ignore_cooldown=False, allow_parry=True):
        o = self.owner
        if ignore_cooldown or o.attack_cooldown <= 0:
            if not ignore_cooldown:
                o.attack_cooldown = o.attack_speed * 2
            # Calculate slash direction
            if direction == "up":
                self.rotation = "up"
                forward = Vector(0, -1)
            elif direction == "down":
                self.rotation = "down"
                forward = Vector(0, 1)
            elif direction == "left":
                self.rotation = "left"
                forward = Vector(-1, 0)
            elif direction == "right":
                self.rotation = "right"
                forward = Vector(1, 0)
            elif direction == "up-left":
                self.rotation = "up-left"
                forward = Vector(-1, -1).normalize()
            elif direction == "up-right":
                self.rotation = "up-right"
                forward = Vector(1, -1).normalize()
            elif direction == "down-left":
                self.rotation = "down-left"
                forward = Vector(-1, 1).normalize()
            elif direction == "down-right":
                self.rotation = "down-right"
                forward = Vector(1, 1).normalize()

            # Fire one large slash; multishot increases rotation angle and range increases travel distance.
            effective_multishot = max(1, o.multishot * 3)
            swing_angle = min(85, 12 + max(0, effective_multishot - 1) * 8)
            if getattr(o, "gun_effect_unlocked", False):
                swing_angle = min(89, swing_angle + 10)

            base_angle = math.atan2(forward.y, forward.x)
            for i in range(o.multishot):
                slash = SlashBullet(
                    o.x,
                    o.y,
                    forward,
                    o.damage * 3,
                    o.pierce * 4,
                    max(5, round(o.attack_speed * 0.45)),
                    12,
                    o.bullet_color,
                    o.knockback,
                    owner=o,
                    length=max(24, round(o.attack_range * 3 + 25)),
                    height=12,
                    base_angle=base_angle,
                    sweep_angle=swing_angle,
                )
                bullets.append(slash)

            if getattr(o, "gun_effect_unlocked", False):
                o.sword_guard_timer = max(getattr(o, "sword_guard_timer", 0), 8)
                if allow_parry and hasattr(o, "try_post_hit_parry"):
                    o.try_post_hit_parry()


class Flamethrower(Gun):
    def __init__(self, owner):
        super().__init__(owner)
        self.pending_fire = []

    def shoot(self, direction, bullets, ignore_cooldown=False):
        o = self.owner
        if ignore_cooldown or o.attack_cooldown <= 0:
            if not ignore_cooldown:
                o.attack_cooldown = o.attack_speed
            # Calculate bullet direction
            if direction == "up":
                self.rotation = "up"
                bullet_velocity = Vector(0, -1)
            elif direction == "down":
                self.rotation = "down"
                bullet_velocity = Vector(0, 1)
            elif direction == "left":
                self.rotation = "left"
                bullet_velocity = Vector(-1, 0)
            elif direction == "right":
                self.rotation = "right"
                bullet_velocity = Vector(1, 0)
            elif direction == "up-left":
                self.rotation = "up-left"
                bullet_velocity = Vector(-1, -1).normalize()
            elif direction == "up-right":
                self.rotation = "up-right"
                bullet_velocity = Vector(1, -1).normalize()
            elif direction == "down-left":
                self.rotation = "down-left"
                bullet_velocity = Vector(-1, 1).normalize()
            elif direction == "down-right":
                self.rotation = "down-right"
                bullet_velocity = Vector(1, 1).normalize()
            bullet_velocity = bullet_velocity.multiply(o.bullet_speed)
            spread_mult = 0.4
            multishot_count = o.multishot * 3
            if getattr(o, "gun_effect_unlocked", False):
                spread_mult = 0.6  # Spread increased a lot
                multishot_count = round(o.multishot * 4)  # Multishot doubled
            max_angle = (multishot_count // 4) * o.attack_spread * spread_mult
            for i in range(multishot_count):
                angle = random.uniform(-max_angle, max_angle)
                speed_variation = random.uniform(1.3, 1.6)
                rotated_velocity = Vector(
                    (
                        bullet_velocity.x * math.cos(angle)
                        - bullet_velocity.y * math.sin(angle)
                    )
                    * speed_variation,
                    (
                        bullet_velocity.x * math.sin(angle)
                        + bullet_velocity.y * math.cos(angle)
                    )
                    * speed_variation,
                )
                # One flame per frame
                self.pending_fire.append((i, bullets, rotated_velocity, o.damage))
            if getattr(o, "gun_effect_unlocked", False):
                self.pending_fire.append(
                    (multishot_count, bullets, bullet_velocity, o.damage + 1)
                )
            self._spawn_pending()

    def _spawn_pending(self):
        o = self.owner
        if self.pending_fire:
            if getattr(o, "gun_effect_unlocked", False):
                fire_amount = 5
            else:
                fire_amount = 1
            for _ in range(fire_amount):
                try:
                    _, bullets, velocity, damage = self.pending_fire.pop(0)
                    fire = Fire(
                        o.x,
                        o.y,
                        velocity,
                        damage,
                        o.pierce,
                        o.attack_range,
                        5,
                        o.bullet_color,
                        o.knockback,
                    )
                    fire.age = random.randint(0, 3)
                    bullets.append(fire)
                except IndexError:
                    break

    def update(self):
        super().update()
        self._spawn_pending()
