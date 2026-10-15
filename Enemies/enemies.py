import math
from helpers import Vector
import pygame
import random
from Enemies.particles import particles
import Enemies.particles as particles_mod
from Enemies.drops import drops, exp
import Enemies.drops as drops_mod
from Background import run_stats
from Background import walls as walls_mod
import Enemies.effects as effects_mod

enemies = []
HAUNTING_ENEMY_NAMES = ("Chaser", "Dasher", "Blaster", "Ghost", "Spiker", "Guardian", "Warper", "Turret")
haunting_options = {enemy_name: False for enemy_name in HAUNTING_ENEMY_NAMES}


def _scaled_health(base_health, time_value):
    progress = max(0.0, float(time_value))
    # Stronger late-run scaling: fast linear growth with an extra quadratic boost.
    return base_health + progress / 20 + (progress * progress) / 9000


def set_haunting_options(options):
    for enemy_name in HAUNTING_ENEMY_NAMES:
        haunting_options[enemy_name] = bool(options.get(enemy_name, False))


def _has_haunted_enemy_of_same_type(enemy):
    for other in enemies:
        if other is enemy:
            continue
        if other.__class__ == enemy.__class__ and getattr(other, "haunted", False):
            return True
    return False


def apply_haunting(enemy):
    enemy_name = enemy.__class__.__name__

    enemy.haunted = bool(haunting_options.get(enemy_name, False)) and not _has_haunted_enemy_of_same_type(enemy)
    if enemy.haunted:
        enemy.speed *= 0.75
        enemy.color = tuple(min(255, channel + 35) for channel in enemy.color)
        enemy.drawing_color = enemy.color
    return enemy


def _distance_to_segment(point_x, point_y, start_x, start_y, end_x, end_y):
    segment_x = end_x - start_x
    segment_y = end_y - start_y
    length_squared = segment_x * segment_x + segment_y * segment_y
    if length_squared == 0:
        return Vector(point_x - start_x, point_y - start_y).magnitude

    projection = ((point_x - start_x) * segment_x + (point_y - start_y) * segment_y) / length_squared
    projection = max(0, min(1, projection))
    closest_x = start_x + segment_x * projection
    closest_y = start_y + segment_y * projection
    return Vector(point_x - closest_x, point_y - closest_y).magnitude


def _spawn_laser_particles(start_x, start_y, direction, length, color, count=6, size=2):
    step_count = max(1, count - 1)
    for index in range(count):
        progress = index / step_count
        particle_x = start_x + direction.x * length * progress + random.uniform(-2, 2)
        particle_y = start_y + direction.y * length * progress + random.uniform(-2, 2)
        effect = particles_mod.HitParticle(particle_x, particle_y, size, color)
        effect.direction = Vector(random.uniform(-0.15, 0.15), random.uniform(-0.15, 0.15))
        particles.append(effect)

def _split_enemy(enemy, size_ratio=0.6, min_size=8):
    """Replace an enemy with two smaller copies, each with half the health."""
    if enemy not in enemies or isinstance(enemy, Spiker) or getattr(enemy, "haunted", False):
        return
    if enemy.size < min_size:
        return
    if enemy.type == "boss":
        return
    new_size = max(min_size, enemy.size * size_ratio)
    half_health = max(1.0, enemy.health / 2)
    for i in range(8):
        effects_mod = particles_mod.HitParticle(
            enemy.x + random.uniform(-10, 10),
            enemy.y + random.uniform(-10, 10),
            4, (255, 240, 120),
        )
        effects_mod.direction = Vector(random.uniform(-1, 1), random.uniform(-1, 1)).normalize().multiply(2)
        particles.append(effects_mod)
    enemies.remove(enemy)
    for i in range(2):
        offset_x = random.uniform(-enemy.size, enemy.size)
        offset_y = random.uniform(-enemy.size, enemy.size)
        new_e = object.__new__(enemy.__class__)
        new_e.__dict__.update(enemy.__dict__)
        new_e.x = enemy.x + offset_x
        new_e.y = enemy.y + offset_y
        new_e.size = new_size
        new_e.health = half_health
        new_e.maxHealth = half_health
        new_e.velocity = Vector(random.uniform(-2, 2), random.uniform(-2, 2))
        new_e.harm_frames = 0
        new_e.dot_effects = []
        new_e.poison_frames = 0
        new_e.shield_active = False
        new_e.warp_charge = -1
        new_e.warp_cooldown = 0
        enemies.append(new_e)


class Enemy:
    def __init__(self, x, y, size=20, color=(255, 40, 40), health=10, damage=1, speed=1):
        self.x = x
        self.y = y
        self.size = size
        self.color = color
        self.health = health
        self.maxHealth = health
        self.damage = damage
        self.speed = speed
        self.velocity = Vector(0, 0)
        self.harm_frames = 0
        enemies.append(self)
        self.dash_cooldown = 0
        self.dash_time = 0
        self.drawing_color = color
        self.haunted = False
        self.shield_active = False
        self.shield_angle = 0.0
        self.warp_charge = -1
        self.warp_cooldown = 0
        self.warp_target_x = 0.0
        self.warp_target_y = 0.0
        self.bullets = []
        self.shoot_cooldown = 0
        self.max_shoot_cooldown = 60
        self.avoids_walls = True
        self.heading = None
        self.avoid_side = 1
        self.walls = []
        apply_haunting(self)
        self.type = "enemy"
        self.iceshock_point = None
        self.iceshock_radius = 30
        self.iceshock_cooldown = 0
        self.iceshock_length = 90
        self.max_iceshock_cooldown = 250
        self.iceshock_charge = 0
        self.iceshock_max_charge = 60
    
    def hurt(self, bullet, direct_damage=False):
        if direct_damage:
            if self.haunted:
                if self.harm_frames == 0:
                    self.harm_frames = 20
                return
            if self.harm_frames == 0:
                self.harm_frames = 60
                self.health -= bullet
                if self.health <= 0:
                    self.die()
            else:
                self.harm_frames = round(self.harm_frames / 2)
                if self.harm_frames < 2:
                    self.harm_frames = 0
        else:
            if self.shield_active and self.ability_shield_blocks_bullet(bullet):
                for i in range(4):
                    effect = particles_mod.HitParticle(
                        bullet.x + random.randint(-4, 4),
                        bullet.y + random.randint(-4, 4),
                        4, (200, 210, 255),
                    )
                    particles.append(effect)
                return
            if self.haunted:
                if self.harm_frames == 0:
                    self.harm_frames = 20
                    knockback_scale = 1
                else:
                    self.harm_frames = round(self.harm_frames / 2)
                    if self.harm_frames < 2:
                        self.harm_frames = 0
                    knockback_scale = 1 / 3
                self.x += bullet.velocity.x * bullet.knockback * knockback_scale
                self.y += bullet.velocity.y * bullet.knockback * knockback_scale
                return
            if self.harm_frames == 0:
                self.harm_frames = 60
                self.health -= bullet.damage
                self.x += bullet.velocity.x * bullet.knockback
                self.y += bullet.velocity.y * bullet.knockback
                particle_count = min(14, max(2, int(bullet.damage * 2)))
                for i in range(particle_count):
                    effect = particles_mod.HitParticle(
                        bullet.x + random.randint(-5, 5),
                        bullet.y + random.randint(-5, 5),
                        self.size / 3,
                        bullet.color
                    )
                    if bullet.pierce <= 1:
                        effect.direction = bullet.velocity.multiply(-0.2)
                    else:
                        effect.direction = bullet.velocity.multiply(0.3)
                    particles.append(effect)
                if self.health <= 0:
                    self.die()
            else:
                self.harm_frames = round(self.harm_frames / 2)
                if self.harm_frames < 2:
                    self.harm_frames = 0
                self.x += bullet.velocity.x * bullet.knockback / 3
                self.y += bullet.velocity.y * bullet.knockback / 3
                particle_count = min(10, max(2, int(bullet.damage * 2)))
                for i in range(particle_count):
                    effect = particles_mod.HitParticle(bullet.x+random.randint(-5, 5), bullet.y+random.randint(-5, 5), self.size/4, (100, 200, 250))
                    if bullet.pierce <= 1:
                        effect.direction = bullet.velocity.multiply(-0.05)
                    else:
                        effect.direction = bullet.velocity.multiply(0.1)
                    particles.append(effect)
    
    def die(self, multiplier=.7):
        global exp
        # Track achievement: record enemy kill
        enemy_type = self.__class__.__name__.lower()
        # Map legacy/misspelled class names to canonical achievement keys.
        if enemy_type == "dasher":
            enemy_type = "leaper"

        run_stats.record_enemy_kill(enemy_type)
        
        if self in enemies:
            enemies.remove(self)
        if random.random() < 0.01:
            drop = drops_mod.MagnetDrop(self.x, self.y, 1)
            drops.append(drop)
        elif random.random() < 0.05:
            drop = drops_mod.HealthDrop(self.x, self.y, 1)
            drops.append(drop)
        else:
            dropped_exp = self.maxHealth * multiplier
            while dropped_exp > 0:
                if dropped_exp > 2:
                    if dropped_exp > 5:
                        if dropped_exp > 10:
                            if dropped_exp > 30:
                                drop_amount = 30
                                size = 15
                                color = (255, 100, 0)
                            else:
                                drop_amount = 10
                                size = 10
                                color = (255, 150, 0)
                        else:
                            drop_amount = 5
                            size = 7
                            color = (255, 200, 0)
                    else:
                        drop_amount = 2
                        size = 5
                        color = (255, 255, 0)
                else:
                    drop_amount = 1
                    size = 3
                    color = (255, 255, 0)
                drops.append(drops_mod.ExpDrop(self.x, self.y, drop_amount, color, size))
                dropped_exp -= drop_amount

    def distance_to(self, target):
        return ((self.x - target.x) ** 2 + (self.y - target.y) ** 2) ** 0.5

    def ray_distance(self, origin_x, origin_y, dir_x, dir_y, max_length, padding=0):
        """Distance along a ray to the nearest padded wall, or None if it's clear."""
        best = None
        for wall in self.walls:
            if wall.contains_point(origin_x, origin_y, padding):
                distance = 0
            elif not wall.intersects_segment(
                origin_x,
                origin_y,
                origin_x + dir_x * max_length,
                origin_y + dir_y * max_length,
                padding,
            ):
                continue
            else:
                low, high = 0.0, max_length
                for _ in range(12):
                    distance = (low + high) / 2
                    if wall.intersects_segment(
                        origin_x,
                        origin_y,
                        origin_x + dir_x * distance,
                        origin_y + dir_y * distance,
                        padding,
                    ):
                        high = distance
                    else:
                        low = distance
                distance = high
            if best is None or distance < best:
                best = distance
        return best

    def target(self, player):
        direction = Vector(player.x - self.x, player.y - self.y).normalize()
        if self.avoids_walls and walls_mod.walls:
            direction = self.steer_around_walls(direction)
        self.velocity = self.velocity.add(direction.multiply(self.speed))
        if self.velocity.magnitude > self.speed:
            self.velocity = self.velocity.normalize().multiply(self.speed)

    def steer_around_walls(self, to_player):
        """Steer along the clearest nearby route that still leads toward the player."""
        self.walls = walls_mod.walls
        sight = max(100, self.size * 4)
        turn_rate = 0.12
        player_angle = math.atan2(to_player.y, to_player.x)
        if self.heading is None:
            self.heading = player_angle

        def angle_difference(first, second):
            return (first - second + math.pi) % (2 * math.pi) - math.pi

        direct_distance = self.ray_distance(
            self.x, self.y, math.cos(player_angle), math.sin(player_angle), sight, self.size
        )
        if direct_distance is None:
            diff = (player_angle - self.heading + math.pi) % (2 * math.pi) - math.pi
            self.heading += max(-turn_rate, min(turn_rate, diff))
        else:
            best_angle = None
            best_score = None
            best_distance = -1
            for step in range(-12, 12):
                angle = player_angle + math.radians(step * 15)
                distance = self.ray_distance(
                    self.x, self.y, math.cos(angle), math.sin(angle), sight, self.size
                )
                if distance is None:
                    side = 1 if angle_difference(angle, player_angle) >= 0 else -1
                    score = (
                        abs(angle_difference(angle, player_angle))
                        + 0.25 * abs(angle_difference(angle, self.heading))
                        + (0.01 if side != self.avoid_side else 0)
                    )
                    if best_score is None or score < best_score:
                        best_angle, best_score = angle, score
                elif distance > best_distance:
                    best_distance = distance
                    best_angle = angle

            if best_angle is not None:
                diff = angle_difference(best_angle, self.heading)
                self.heading += max(-turn_rate, min(turn_rate, diff))
                if abs(angle_difference(best_angle, player_angle)) > math.radians(7.5):
                    self.avoid_side = 1 if angle_difference(best_angle, player_angle) > 0 else -1
        return Vector(math.cos(self.heading), math.sin(self.heading))
    
    def hit(self, player):
        if self.distance_to(player) < self.size + player.size:
            direction = Vector(player.x - self.x, player.y - self.y).normalize()
            player.velocity = player.velocity.add(direction.multiply(self.speed * 2))
            player.hurt(self)
            if self.velocity.magnitude != 0:
                self.velocity = self.velocity.multiply(-2)
            else:
                self.velocity = Vector(random.uniform(-1, 1), random.uniform(-1, 1)).normalize().multiply(-2)
            self.harm_frames = 120
    
    def move(self, friction=0.9):
        if self.haunted:
            self.health = self.maxHealth
        if self.health <= 0:
            self.die()
            return
        if self.dash_time > 0:
            self.dash_time -= 1
        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= 1
        if self.iceshock_cooldown > 0:
            self.iceshock_cooldown -= 1
        self.x += self.velocity.x
        self.y += self.velocity.y
        self.velocity = self.velocity.multiply(friction)  # Friction
    
    def collide(self):
        for other in enemies:
            if other != self:
                distance = Vector(other.x - self.x, other.y - self.y).magnitude
                if distance < self.size + other.size:
                    push_direction = Vector(other.x - self.x, other.y - self.y).normalize()
                    push_strength = (self.size + other.size - distance) / (self.size + other.size)
                    self.velocity = self.velocity.subtract(push_direction.multiply(push_strength ))
                    other.velocity = other.velocity.add(push_direction.multiply(push_strength ))
    
    def draw(self, screen):
        red_mod = 0
        green_mod = 0
        blue_mod = 0
        red, green, blue = self.color
        if red < 0:
            red = 0
        if green < 0:
            green = 0
        if blue < 0:
            blue = 0
        if red > 255:
            red = 255
        if green > 255:
            green = 255
        if blue > 255:
            blue = 255
        self.color = (red, green, blue)
        self.drawing_color = (
            max(0, min(255, int(round(red + red_mod)))),
            max(0, min(255, int(round(green + green_mod)))),
            max(0, min(255, int(round(blue + blue_mod)))),
        )
        pygame.draw.circle(screen, self.drawing_color, (int(self.x), int(self.y)), self.size)
        if self.haunted:
            pygame.draw.circle(screen, (120, 255, 120), (int(self.x), int(self.y)), self.size + 4, 2)

        if not self.haunted:
            # Draw a red health bar centered above the enemy.
            bar_width = self.size * 2
            bar_height = max(3, round(self.size * 0.25))
            health_ratio = 0
            if self.maxHealth > 0:
                health_ratio = max(0, min(1, self.health / self.maxHealth))
            bar_x = int(self.x - bar_width / 2)
            bar_y = int(self.y - self.size - bar_height - 6)
            pygame.draw.rect(screen, (60, 0, 0), (bar_x, bar_y, int(bar_width), bar_height))
            pygame.draw.rect(screen, (220, 30, 30), (bar_x, bar_y, int(bar_width * health_ratio), bar_height))
            pygame.draw.rect(screen, (0, 0, 0), (bar_x, bar_y, int(bar_width), bar_height), 1)

        if self.harm_frames > 0:
            pygame.draw.circle(screen, (255, 255, 255), (int(self.x), int(self.y)), self.size + self.harm_frames/3, 2)
            self.harm_frames -= 1

    def dash(self, direction, strength):
        if self.dash_cooldown == 0:
            self.velocity = direction.normalize().multiply(strength)
            self.dash_cooldown = 60
            self.dash_time = 30

    def ability_emit_hit_particles(self, count, size, color=None, spread=0):
        particle_color = self.color if color is None else color
        for i in range(count):
            effect = particles_mod.HitParticle(
                self.x + random.uniform(-spread, spread),
                self.y + random.uniform(-spread, spread),
                size,
                particle_color,
            )
            particles.append(effect)

    def ability_dash_prepare(
        self,
        player,
        cooldown_frames=120,
        dash_frames=30,
        charge_trail_count=5,
        charge_trail_spacing=20,
        charge_trail_size=None,
        charge_trail_color=None,
    ):
        self.dash_cooldown = cooldown_frames
        self.dash_time = dash_frames
        dash_direction = Vector(player.x - self.x, player.y - self.y).normalize()
        if dash_direction.magnitude == 0:
            dash_direction = Vector(1, 0)
        self.dash_direction = dash_direction

        trail_size = self.size / 2 if charge_trail_size is None else charge_trail_size
        trail_color = self.color if charge_trail_color is None else charge_trail_color
        for i in range(charge_trail_count):
            effect = particles_mod.HitParticle(
                self.x + dash_direction.x * i * charge_trail_spacing,
                self.y + dash_direction.y * i * charge_trail_spacing,
                trail_size,
                trail_color,
            )
            particles.append(effect)

    def ability_dash_active_step(self, dash_speed=5, trail_count=3, trail_size=None, trail_color=None, throw_force=9, throw_radius=None):
        if self.dash_time <= 0:
            return False
        effect_size = self.size / 4 if trail_size is None else trail_size
        self.ability_emit_hit_particles(trail_count, effect_size, self.color if trail_color is None else trail_color)
        dash_direction = getattr(self, "dash_direction", Vector(1, 0))
        self.velocity = dash_direction.multiply(dash_speed)
        self.x += self.velocity.x
        self.y += self.velocity.y
        # Throw any enemies in the dash path
        throw_r = (self.size + 12) if throw_radius is None else throw_radius
        for other in enemies:
            if other is self:
                continue
            if self.distance_to(other) < throw_r + other.size:
                other.velocity = other.velocity.add(dash_direction.multiply(throw_force))
        self.dash_time -= 1
        return True

    def ability_dash_cooldown_step(self, warning_threshold=10, warning_count=6, warning_size=None, warning_color=(200, 150, 0)):
        if self.dash_cooldown <= 0:
            return
        self.dash_cooldown -= 1
        if self.dash_cooldown < warning_threshold:
            effect_size = self.size / 3 if warning_size is None else warning_size
            self.ability_emit_hit_particles(warning_count, effect_size, warning_color)

    def ability_interrupt_dash(self, reset_cooldown_frames=60):
        if self.dash_time > 0:
            self.dash_time = 0
            self.dash_cooldown = reset_cooldown_frames

    def ability_blast_trigger(self, player, trigger_distance=150):
        if self.distance_to(player) < trigger_distance and self.blast_time == -1:
            self.blast_time = 0

    def ability_self_blast_damage(self, self_damage_multiplier=2, secret_progress_key=None):
        if self.haunted:
            return
        was_alive = self.health > 0
        self.health -= self.damage * self_damage_multiplier
        if was_alive and self.health <= 0 and secret_progress_key and not getattr(self, "self_blast_death_recorded", False):
            run_stats.record_secret_progress(secret_progress_key, 1)
            self.self_blast_death_recorded = True

    def ability_blast_tick(self, player, max_blast_time=60, radius_multiplier=2, pulse_color=(200, 100, 250), heal_radius=120, heal_per_tick=0.4):
        if self.blast_time == -1:
            return
        if self.blast_time % 2 == 0:
            effect = particles_mod.HitParticle(self.x, self.y, self.blast_time / 2, pulse_color)
            particles.append(effect)
        if self.distance_to(player) < self.blast_time * radius_multiplier + self.size + player.size:
            player.hurt(self)
            self.ability_self_blast_damage(secret_progress_key="blaster_self_destructions")
        # Heal nearby enemies with the blast energy
        if self.blast_time % 6 == 0:
            for other in enemies:
                if other is self:
                    continue
                if self.distance_to(other) < heal_radius:
                    other.health = min(other.maxHealth, other.health + heal_per_tick)
                    effect = particles_mod.HitParticle(
                        other.x + random.uniform(-other.size * 0.5, other.size * 0.5),
                        other.y + random.uniform(-other.size * 0.5, other.size * 0.5),
                        3, (100, 255, 150),
                    )
                    effect.direction = Vector(0, -1).multiply(1.5)
                    particles.append(effect)
        if self.blast_time > max_blast_time:
            self.blast_time = -1
            self.ability_self_blast_damage(secret_progress_key="blaster_self_destructions")

    def ability_blast_advance(self):
        if self.blast_time == -1:
            return False
        self.blast_time += 1
        return True

    def ability_apply_fear(self, player, fear_range=300, slow_multiplier=0.2, feared_color=(150, 150, 255), calm_color=(100, 100, 200), boost_range=None, boost_amount=0.25):
        if self.distance_to(player) < self.size + player.size + fear_range:
            self.velocity = self.velocity.multiply(slow_multiplier)
            self.color = feared_color
            self.feared = True
            # Fear aura agitates nearby enemies, pushing them faster toward the player
            nearby_range = (fear_range * 1.2) if boost_range is None else boost_range
            for other in enemies:
                if other is self:
                    continue
                if self.distance_to(other) < nearby_range:
                    dir_to_player = Vector(player.x - other.x, player.y - other.y).normalize()
                    other.velocity = other.velocity.add(dir_to_player.multiply(boost_amount))
                    cap = getattr(other, "speed", 1) * 2.0
                    if other.velocity.magnitude > cap:
                        other.velocity = other.velocity.normalize().multiply(cap)
            return True
        self.color = calm_color
        self.feared = False
        return False

    def ability_laser_start(self, player, min_length=170, max_length=320):
        direction = Vector(player.x - self.x, player.y - self.y).normalize()
        if direction.magnitude == 0:
            direction = Vector(1, 0)
        self.laser_direction = direction
        self.laser_length = max(min_length, min(max_length, self.distance_to(player) + player.size))
        self.laser_charge = 0
        self.laser_time = 0
        self.laser_damage_done = False
        self.laser_split_done = False

    def ability_laser_end(self):
        return (
            self.x + self.laser_direction.x * self.laser_length,
            self.y + self.laser_direction.y * self.laser_length,
        )

    def ability_laser_emit_warning(self, color=(180, 255, 200), count=5, size=2):
        _spawn_laser_particles(self.x, self.y, self.laser_direction, self.laser_length, color, count=count, size=size)

    def ability_laser_emit_beam(self, color=(255, 240, 120), count=7, size=3):
        _spawn_laser_particles(self.x, self.y, self.laser_direction, self.laser_length, color, count=count, size=size)

    def ability_laser_hits_player(self, player, hit_padding=12):
        end_x, end_y = self.ability_laser_end()
        return _distance_to_segment(player.x, player.y, self.x, self.y, end_x, end_y) <= player.size + hit_padding

    def ability_laser_target_step(self, player, engage_distance=260, charge_frames=24, beam_frames=8, cooldown_frames=70):
        if self.laser_cooldown > 0:
            self.laser_cooldown -= 1

        if self.laser_charge >= 0:
            self.velocity = self.velocity.multiply(0.8)
            self.ability_laser_emit_warning()
            self.laser_charge += 1
            if self.laser_charge >= charge_frames:
                self.laser_charge = -1
                self.laser_time = beam_frames
                self.laser_damage_done = False
            return True

        if self.laser_time > 0:
            self.velocity = self.velocity.multiply(0.85)
            self.ability_laser_emit_beam()
            if not self.laser_damage_done and self.ability_laser_hits_player(player):
                player.hurt(self)
                self.laser_damage_done = True
            if not getattr(self, "laser_split_done", False):
                self.ability_laser_split_enemies_in_beam()
                self.laser_split_done = True
            self.laser_time -= 1
            if self.laser_time == 0:
                self.laser_cooldown = cooldown_frames
            return True

        if self.laser_cooldown == 0 and self.distance_to(player) < engage_distance:
            self.ability_laser_start(player)
            self.ability_laser_emit_warning()
            return True

        return False

    def ability_laser_move_step(self, active_friction=0.92):
        if self.laser_charge < 0 and self.laser_time <= 0:
            return False
        self.x += self.velocity.x
        self.y += self.velocity.y
        self.velocity = self.velocity.multiply(active_friction)
        self.collide()
        return True

    def ability_spawn_minion_wave(self, time_scale, spawn_count=3, spread=50, cooldown_frames=120, type=None):
        if self.spawn_time > 0:
            self.spawn_time -= 1
            return
        for i in range(spawn_count):
            spawn_x = self.x + random.randint(-spread, spread)
            spawn_y = self.y + random.randint(-spread, spread)
            if type is not None:
                if type == "Chaser":
                    Chaser(spawn_x, spawn_y, time_scale)
                elif type == "Dasher":
                    Dasher(spawn_x, spawn_y, time_scale)
                elif type == "Blaster":
                    Blaster(spawn_x, spawn_y, time_scale)
                elif type == "Ghost":
                    Ghost(spawn_x, spawn_y, time_scale)
                elif type == "Spiker":
                    Spiker(spawn_x, spawn_y, time_scale)

            else:
                if random.random() < 0.5:
                    Chaser(spawn_x, spawn_y, time_scale)
                else:
                    temp = random.randint(0, 2)
                    if temp == 0:
                        Dasher(spawn_x, spawn_y, time_scale)
                    elif temp == 1:
                        Blaster(spawn_x, spawn_y, time_scale)
                    else:
                        Ghost(spawn_x, spawn_y, time_scale)
        self.spawn_time = cooldown_frames

    # ------------------------------------------------------------------ #
    #  Laser split                                                         #
    # ------------------------------------------------------------------ #
    def ability_laser_split_enemies_in_beam(self, hit_padding=4):
        """Split any enemy intersected by the active laser beam into two smaller copies."""
        end_x, end_y = self.ability_laser_end()
        for other in list(enemies):
            if other is self:
                continue
            dist = _distance_to_segment(other.x, other.y, self.x, self.y, end_x, end_y)
            if dist <= other.size + hit_padding:
                _split_enemy(other)

    # ------------------------------------------------------------------ #
    #  Shield                                                              #
    # ------------------------------------------------------------------ #
    def ability_shield_init(self, shield_radius=None, shield_width=60, shield_thickness=8, spin_speed=0.045):
        """Enable a rotating rectangular shield around this enemy."""
        self.shield_active = True
        self.shield_radius = (self.size + 14) if shield_radius is None else shield_radius
        self.shield_width = shield_width
        self.shield_thickness = shield_thickness
        self.shield_spin_speed = spin_speed

    def ability_shield_step(self):
        """Advance shield rotation. Call every frame from move()."""
        if not self.shield_active:
            return
        self.shield_angle = (self.shield_angle + self.shield_spin_speed) % (2 * math.pi)

    def ability_shield_contains_point(self, x, y):
        """Return True if a point falls inside the shield rectangle."""
        if not self.shield_active:
            return False
        cx = self.x + math.cos(self.shield_angle) * self.shield_radius
        cy = self.y + math.sin(self.shield_angle) * self.shield_radius
        dx = x - cx
        dy = y - cy
        # Project onto tangent (long axis) and radial (short axis) of the shield
        tangent_x = -math.sin(self.shield_angle)
        tangent_y = math.cos(self.shield_angle)
        radial_x = math.cos(self.shield_angle)
        radial_y = math.sin(self.shield_angle)
        local_x = dx * tangent_x + dy * tangent_y
        local_y = dx * radial_x + dy * radial_y
        return abs(local_x) <= self.shield_width / 2 and abs(local_y) <= self.shield_thickness / 2

    def ability_shield_blocks_bullet(self, bullet):
        """Return True if bullet's position falls inside the shield rectangle."""
        return self.ability_shield_contains_point(bullet.x, bullet.y)

    def ability_shield_draw(self, screen):
        """Draw the rotating shield rectangle. Call from draw()."""
        if not self.shield_active:
            return
        cx = self.x + math.cos(self.shield_angle) * self.shield_radius
        cy = self.y + math.sin(self.shield_angle) * self.shield_radius
        tx = -math.sin(self.shield_angle)
        ty = math.cos(self.shield_angle)
        rx = math.cos(self.shield_angle)
        ry = math.sin(self.shield_angle)
        hw = self.shield_width / 2
        hh = self.shield_thickness / 2
        corners = [
            (int(cx + tx * hw + rx * hh), int(cy + ty * hw + ry * hh)),
            (int(cx - tx * hw + rx * hh), int(cy - ty * hw + ry * hh)),
            (int(cx - tx * hw - rx * hh), int(cy - ty * hw - ry * hh)),
            (int(cx + tx * hw - rx * hh), int(cy + ty * hw - ry * hh)),
        ]
        pygame.draw.polygon(screen, (200, 210, 255), corners)
        pygame.draw.polygon(screen, (140, 160, 255), corners, 2)

    # ------------------------------------------------------------------ #
    #  Warp                                                                #
    # ------------------------------------------------------------------ #
    def ability_warp_target_step(self, player, engage_distance=300, charge_frames=60, cooldown_frames=200, overshoot=90):
        """
        Charge up then teleport self (and any nearby enemies) to a point
        behind the player. Call from target(). Returns True while active.
        """
        if self.warp_cooldown > 0:
            self.warp_cooldown -= 1
            return False
        if self.warp_charge == -1:
            if self.distance_to(player) < engage_distance:
                direction = Vector(player.x - self.x, player.y - self.y).normalize()
                self.warp_target_x = player.x + direction.x * overshoot
                self.warp_target_y = player.y + direction.y * overshoot
                self.warp_charge = 0
                self._warp_charge_frames = charge_frames
            return False
        # Charging — advance and emit trail particles toward target
        self.warp_charge += 1
        if self.warp_charge % 4 == 0:
            progress = min(1.0, self.warp_charge / self._warp_charge_frames)
            px = self.x + (self.warp_target_x - self.x) * progress + random.uniform(-6, 6)
            py = self.y + (self.warp_target_y - self.y) * progress + random.uniform(-6, 6)
            effect = particles_mod.HitParticle(px, py, 3, (180, 100, 255))
            effect.direction = Vector(random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3))
            particles.append(effect)
        if self.warp_charge >= self._warp_charge_frames:
            # Carry any nearby enemies along
            carried = [
                e for e in enemies
                if e is not self and self.distance_to(e) < self.warp_carry_radius + e.size
            ]
            self.x = self.warp_target_x
            self.y = self.warp_target_y
            for e in carried:
                e.x = self.warp_target_x + random.uniform(-self.size * 1.5, self.size * 1.5)
                e.y = self.warp_target_y + random.uniform(-self.size * 1.5, self.size * 1.5)
            # Arrival burst particles
            for i in range(12):
                effect = particles_mod.HitParticle(
                    self.x + random.uniform(-self.size, self.size),
                    self.y + random.uniform(-self.size, self.size),
                    5, (180, 100, 255),
                )
                effect.direction = Vector(random.uniform(-1, 1), random.uniform(-1, 1)).normalize().multiply(2.5)
                particles.append(effect)
            self.warp_charge = -1
            self.warp_cooldown = cooldown_frames
        return True

    def ability_warp_draw(self, screen):
        """Draw the charge-up line, target marker, and carry-range circle. Call from draw()."""
        if self.warp_charge <= 0:
            return
        total = getattr(self, "_warp_charge_frames", 60)
        progress = min(1.0, self.warp_charge / total)
        color = (min(255, int(100 + 155 * progress)), min(255, int(50 + 50 * progress)), 255)
        thickness = max(1, int(progress * 3))
        pygame.draw.line(
            screen, color,
            (int(self.x), int(self.y)),
            (int(self.warp_target_x), int(self.warp_target_y)),
            thickness,
        )
        marker_r = max(3, int(self.size * 0.7 * progress))
        pygame.draw.circle(screen, color, (int(self.warp_target_x), int(self.warp_target_y)), marker_r, 2)
        # Draw the carry-range indicator around the warper
        carry_r = int(self.warp_carry_radius)
        alpha = int(60 + 140 * progress)
        ring_color = (min(255, int(150 + 105 * progress)), min(255, int(80 + 80 * progress)), 255)
        # Pulsing dash pattern: alternate drawn/gap segments around the circle
        segment_count = 24
        for i in range(segment_count):
            if i % 2 == 0:
                angle_start = math.radians(i * 360 / segment_count)
                angle_end = math.radians((i + 1) * 360 / segment_count)
                p1 = (int(self.x + carry_r * math.cos(angle_start)), int(self.y + carry_r * math.sin(angle_start)))
                p2 = (int(self.x + carry_r * math.cos(angle_end)), int(self.y + carry_r * math.sin(angle_end)))
                pygame.draw.line(screen, ring_color, p1, p2, 2)

    def ability_shoot(self, player):
        if self.shoot_cooldown == 0:
            direction = Vector(player.x - self.x, player.y - self.y).normalize()
            bullet = Bullet(self.x, self.y, direction, self.damage, owner=self)
            self.bullets.append(bullet)
            self.shoot_cooldown = self.max_shoot_cooldown

    def ability_shoot_draw(self, screen):
        """Draw the bullets fired by this enemy. Call from draw()."""
        for bullet in self.bullets:
            bullet.draw(screen)

    def ability_shoot_update(self, player):
        """Update the bullets fired by this enemy. Call from update()."""
        for bullet in self.bullets:
            old_x, old_y = bullet.x, bullet.y
            bullet.move()
            if walls_mod.segment_hits_wall(old_x, old_y, bullet.x, bullet.y):
                bullet.remove = True
                continue
            bullet.collide(player)
        self.bullets = [b for b in self.bullets if not b.remove]

    def ability_iceshock_create(self, player):
        if self.iceshock_cooldown == 0:
            self.iceshock_point = (player.x, player.y)
            self.iceshock_charge = self.iceshock_max_charge

    def ability_iceshock_update(self, player):
        if self.iceshock_point is None:
            return
        if self.iceshock_charge > 0:
            self.iceshock_charge -= 1
        else:
            if (player.x - self.iceshock_point[0]) ** 2 + (player.y - self.iceshock_point[1]) ** 2 < self.iceshock_radius ** 2:
                effects_mod.apply_effect(player, "frozen", duration=self.iceshock_length, level=1)
            self.iceshock_point = None
            self.iceshock_charge = 0
            self.iceshock_cooldown = self.max_iceshock_cooldown

    def ability_iceshock_draw(self, screen):
        if self.iceshock_point is None:
            return
        progress = self.iceshock_charge / self.max_iceshock_charge
        pygame.draw.circle(screen, (0, 50, 150), (int(self.iceshock_point[0]), int(self.iceshock_point[1])), self.iceshock_radius)
        pygame.draw.circle(screen, (0, 150, 255), (int(self.iceshock_point[0]), int(self.iceshock_point[1])), self.iceshock_radius, 2)
        pygame.draw.circle(screen, (100, 100, 200), (int(self.iceshock_point[0]), int(self.iceshock_point[1])), round(self.iceshock_radius * progress))


class Bullet:
    def __init__(self, x, y, direction, damage, speed=5, owner=None):
        self.x = x
        self.y = y
        self.direction = direction
        self.damage = damage
        self.speed = speed
        self.owner = owner
        self.remove = False
        self.lifetime = 700

    def move(self):
        self.x += self.direction.x * self.speed
        self.y += self.direction.y * self.speed
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.remove = True

    def draw(self, screen):
        pygame.draw.circle(screen, (150, 25, 25), (int(self.x - self.direction.x * 3), int(self.y - self.direction.y * 3)), 2)
        pygame.draw.circle(screen, (255, 50, 50), (int(self.x), int(self.y)), 3)
        pygame.draw.circle(screen, (255, 255, 255), (int(self.x), int(self.y)), 3, 1)

    def collide(self, target):
        if (self.x - target.x) ** 2 + (self.y - target.y) ** 2 < 9:
            target.hurt(self.owner)
            self.remove = True


class Chaser(Enemy):
    def __init__(self, x, y, time=1):
        health = _scaled_health(2, time)
        damage = 1 + time/3000
        super().__init__(x, y, size=15, color=(250, 60, 60), health=health, damage=damage, speed=1.5)
    
    def move(self):
        super().move(friction=0.99)
        self.collide()
    
    def target(self, player):
        super().target(player)
        self.hit(player)
    
    def draw(self, screen):
        super().draw(screen)

    def hurt(self, bullet, direct_damage=False):
        super().hurt(bullet, direct_damage=direct_damage)
    
    def die(self):
        # Track achievement: record enemy kill
        run_stats.record_enemy_kill("chaser")
        
        if self in enemies:
            enemies.remove(self)
        if random.random() < 0.02:
            drop = drops_mod.MagnetDrop(self.x, self.y, 1)
            drops.append(drop)
        if random.random() < 0.1:
            drop = drops_mod.HealthDrop(self.x, self.y, 1)
            drops.append(drop)
        dropped_exp = self.maxHealth * .9
        while dropped_exp > 0:
                if dropped_exp > 2:
                    if dropped_exp > 5:
                        if dropped_exp > 10:
                            if dropped_exp > 30:
                                drop_amount = 30
                                size = 15
                                color = (255, 100, 0)
                            else:
                                drop_amount = 10
                                size = 10
                                color = (255, 150, 0)
                        else:
                            drop_amount = 5
                            size = 7
                            color = (255, 200, 0)
                    else:
                        drop_amount = 2
                        size = 5
                        color = (255, 255, 0)
                else:
                    drop_amount = 1
                    size = 3
                    color = (255, 255, 0)
                drops.append(drops_mod.ExpDrop(self.x, self.y, drop_amount, color, size))
                dropped_exp -= drop_amount


class Dasher(Enemy):
    def __init__(self, x, y, time=1):
        health = _scaled_health(3, time)
        damage = 1 + time/3000
        super().__init__(x, y, 20, (250, 200, 50), health, damage, 1)
        self.dash_cooldown = 0
        self.dash_time = 0
    
    def target(self, player):
        if self.dash_cooldown == 0 and self.dash_time == 0:
            self.ability_emit_hit_particles(1, self.size / 3, (250, 150, 0))
            if self.distance_to(player) < 200:
                self.ability_dash_prepare(player)
            else:
                super().target(player)
        elif self.dash_time == 0:
            super().target(player)
        self.hit(player)
    
    def move(self):
        if self.ability_dash_active_step(dash_speed=5, trail_count=3, trail_size=self.size / 4, trail_color=self.color):
            return
        super().move(friction=0.95)
        self.collide()
        self.ability_dash_cooldown_step(warning_threshold=10, warning_count=6, warning_size=self.size / 3, warning_color=(200, 150, 0))
    
    def hurt(self, bullet, direct_damage=False):
        super().hurt(bullet, direct_damage=direct_damage)
        self.ability_interrupt_dash(reset_cooldown_frames=60)

    def die(self): 
        super().die(multiplier=1.2)

class Blaster(Enemy):
    def __init__(self, x, y, time=1):
        health = _scaled_health(4, time)
        damage = 1 + time/3000
        super().__init__(x, y, 25, (150, 50, 250), health, damage, 0.5)
        self.blast_time = -1
        self.self_blast_death_recorded = False
    
    def target(self, player):
        super().target(player)
        self.ability_blast_trigger(player, trigger_distance=150)
        if self.blast_time != -1:
            self.ability_blast_tick(player, max_blast_time=60, radius_multiplier=2, pulse_color=(200, 100, 250))
        self.hit(player)
    
    def move(self):
        if not self.ability_blast_advance():
            super().move(friction=0.9)
        self.collide()
    
    def draw(self, screen):
        super().draw(screen)
        if self.blast_time != -1:
            pygame.draw.circle(screen, (200, 100, 250), (int(self.x), int(self.y)), self.blast_time *2 + self.size, 2)
            
class Ghost(Enemy):
    def __init__(self, x, y, time=1):
        health = _scaled_health(2, time)
        damage = 1 + time/3000
        super().__init__(x, y, 10, (100, 100, 255), health, damage, 1.5)
        self.feared = False
        self.avoids_walls = False

    def hurt(self, bullet, direct_damage=False):
        if self.feared:
            super().hurt(bullet, direct_damage=direct_damage)
            if self.harm_frames == 0:
                self.velocity = self.velocity.multiply(-1)
    
    def move(self):
        super().move(friction=0.98)
    
    def target(self, player):
        super().target(player)
        self.ability_apply_fear(player, fear_range=300, slow_multiplier=0.2, feared_color=(150, 150, 255), calm_color=(100, 100, 200))
        self.hit(player)


class Spiker(Enemy):
    def __init__(self, x, y, time=1):
        health = _scaled_health(6, time)
        damage = 2 + time / 3500
        super().__init__(x, y, 18, (80, 220, 140), health, damage, 0.85)
        self.laser_charge = -1
        self.laser_time = 0
        self.laser_cooldown = 0
        self.laser_direction = Vector(1, 0)
        self.laser_length = 220
        self.laser_damage_done = False

    def target(self, player):
        if self.ability_laser_target_step(player, engage_distance=260, charge_frames=24, beam_frames=8, cooldown_frames=70):
            return

        super().target(player)
        self.hit(player)

    def move(self):
        if self.health <= 0:
            self.die()
            return
        if self.ability_laser_move_step(active_friction=0.92):
            return
        super().move(friction=0.95)
        self.collide()

    def draw(self, screen):
        super().draw(screen)
        if self.laser_charge >= 0:
            end_x, end_y = self.ability_laser_end()
            pygame.draw.line(screen, (180, 255, 200), (int(self.x), int(self.y)), (int(end_x), int(end_y)), 4)
            pygame.draw.circle(screen, (220, 255, 230), (int(self.x), int(self.y)), self.size + 3, 1)
        elif self.laser_time > 0:
            end_x, end_y = self.ability_laser_end()
            pygame.draw.line(screen, (255, 120, 120), (int(self.x), int(self.y)), (int(end_x), int(end_y)), 8)
            pygame.draw.line(screen, (255, 230, 120), (int(self.x), int(self.y)), (int(end_x), int(end_y)), 4)
            pygame.draw.circle(screen, (255, 240, 200), (int(self.x), int(self.y)), self.size + 4, 1)

class Commander(Enemy):
    def __init__(self, x, y, time=1):
        health = _scaled_health(15, time)
        damage = 1 + time/3000
        super().__init__(x, y, 30, (200, 50, 50), health, damage, 1)
        self.spawn_time = 0
        self.time = time/2
        self.type = "boss"
    
    def move(self):
        super().move(friction=0.9)
        self.collide()
    
    def target(self, player):
        super().target(player)
        self.hit(player)
        self.ability_spawn_minion_wave(self.time, spawn_count=3, spread=50, cooldown_frames=120)


class Guardian(Enemy):
    def __init__(self, x, y, time=1):
        health = _scaled_health(10, time)
        damage = 1 + time/3000
        super().__init__(x, y, 22, (50, 100, 250), health, damage, 0.8)
        self.ability_shield_init(shield_radius=self.size + 14, shield_width=60, shield_thickness=8, spin_speed=0.045)
    
    def target(self, player):
        super().target(player)
        self.hit(player)
    
    def move(self):
        super().move(friction=0.9)
        self.collide()
        self.ability_shield_step()
    
    def draw(self, screen):
        super().draw(screen)
        self.ability_shield_draw(screen)

class Warper(Enemy):
    def __init__(self, x, y, time=1):
        health = _scaled_health(8, time)
        damage = 1 + time/3000
        super().__init__(x, y, 18, (170, 60, 255), health, damage, 0.9)
        self.warp_carry_radius = self.size * 4
        self.warp_charge = -1
        self.warp_cooldown = 0
    
    def target(self, player):
        if self.ability_warp_target_step(player, engage_distance=300, charge_frames=60, cooldown_frames=200, overshoot=90):
            return
        super().target(player)
        self.hit(player)
    
    def move(self):
        if self.warp_charge != -1:
            super().move(friction=0.96)
            self.collide()
            return
        super().move(friction=0.9)
        self.collide()
    
    def draw(self, screen):
        super().draw(screen)
        self.ability_warp_draw(screen)

class Turret(Enemy):
    def __init__(self, x, y, time=1):
        health = _scaled_health(12, time)
        damage = 1 + time/3000
        super().__init__(x, y, 20, (255, 150, 100), health, damage, 0)
        self.shoot_charge = 0
    
    def target(self, player):
        super().target(player)
        self.hit(player)
        if self.distance_to(player) < 500:
            self.shoot_charge += 1
        else:
            self.shoot_charge = 0
        if self.shoot_charge >= 30:
            self.ability_shoot(player)
        if self.shoot_charge >= 50:
            self.shoot_charge = 0
        self.ability_shoot_update(player)

    def move(self):
        if self.shoot_charge > 0:
            self.speed = 0
        else:
            self.speed = 1
        super().move(friction=0.9)
        self.collide()

    def draw(self, screen):
        super().draw(screen)
        self.ability_shoot_draw(screen)

class Shatterking(Enemy):
    #boss enemy, warps twoards player then fires lasers in a set of three. if not hit when firing, it will spawn two spikers.
    def __init__(self, x, y, time=1):
        health = _scaled_health(50, time)
        damage = 3 + time/2000
        super().__init__(x, y, 35, (255, 100, 170), health, damage, 0.9)
        self.warp_carry_radius = self.size * 5
        self.warp_charge = -1
        self.warp_cooldown = 0
        self.laser_charge = -1
        self.laser_time = 0
        self.laser_cooldown = 0
        self.laser_direction = Vector(1, 0)
        self.laser_length = 360
        self.laser_damage_done = False
        self.fired_lasers = 0
        self.harmed_during_laser = False
        self.spawn_time = 0
        self.type = "boss"

    def target(self, player):
        if self.ability_warp_target_step(player, engage_distance=500, charge_frames=40, cooldown_frames=300, overshoot=30):
            return
        if self.fired_lasers >= 3:
            self.fired_lasers = 0
            if self.harmed_during_laser:
                self.ability_spawn_minion_wave(30, 1, 60, 10, "Spiker")
            self.harmed_during_laser = False
        if self.fired_lasers < 3:
            if self.ability_laser_target_step(player, engage_distance=360, charge_frames=36, beam_frames=12, cooldown_frames=30):
                self.fired_lasers += 1
                return
        super().target(player)
        self.hit(player)

    def hurt(self, damage, direct_damage=False):
        super().hurt(damage, direct_damage=direct_damage)
        if self.fired_lasers > 0:
            self.harmed_during_laser = True

    def move(self):
        if self.warp_charge != -1:
            super().move(friction=0.96)
            self.collide()
            return
        if self.ability_laser_move_step(active_friction=0.92):
            return
        super().move(friction=0.9)
        self.collide()

    def draw(self, screen):
        super().draw(screen)
        self.ability_warp_draw(screen)
        if self.laser_charge >= 0:
            end_x, end_y = self.ability_laser_end()
            pygame.draw.line(screen, (180, 255, 200), (int(self.x), int(self.y)), (int(end_x), int(end_y)), 4)
            pygame.draw.circle(screen, (220, 255, 230), (int(self.x), int(self.y)), self.size + 3, 1)
        elif self.laser_time > 0:
            end_x, end_y = self.ability_laser_end()
            pygame.draw.line(screen, (255, 120, 120), (int(self.x), int(self.y)), (int(end_x), int(end_y)), 8)
            pygame.draw.line(screen, (255, 230, 120), (int(self.x), int(self.y)), (int(end_x), int(end_y)), 4)
            pygame.draw.circle(screen, (255, 240, 200), (int(self.x), int(self.y)), self.size + 4, 1)

class Freezer(Enemy):
    def __init__(self, x, y, time):
        health = _scaled_health(20, time)
        damage = 1 + time/3000
        super().__init__(x, y, 15, (100, 150, 255), health, damage, 0.9)
        self.iceshock_radius = 40
        self.iceshock_length = 60
        self.iceshock_charge = 0
        self.iceshock_cooldown = 0
        self.iceshock_point = None
        self.max_iceshock_cooldown = 300
        self.max_iceshock_charge = 60

    def target(self, player):
        super().target(player)
        self.hit(player)
        if self.distance_to(player) <= 420 and self.iceshock_point is None:
            self.ability_iceshock_create(player)
        self.ability_iceshock_update(player)

    def move(self):
        if self.iceshock_charge != 0:
            super().move(friction=0.96)
            self.collide()
            return
        super().move(friction=0.9)
        self.collide()

    def draw(self, screen):
        super().draw(screen)
        if self.iceshock_charge != 0:
            end_x, end_y = self.iceshock_point
            pygame.draw.line(screen, (100, 100, 200), (int(self.x), int(self.y)), (int(end_x), int(end_y)), 4)
            pygame.draw.circle(screen, (150, 220, 255), (int(self.x), int(self.y)), self.size + 3, 1)
            self.ability_iceshock_draw(screen)

