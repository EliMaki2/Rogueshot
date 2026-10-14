import math
import pygame
import random
import Enemies.effects as effects_mod

class Vector:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    def add(self, other):
        return Vector(self.x + other.x, self.y + other.y)
    def subtract(self, other):
        return Vector(self.x - other.x, self.y - other.y)
    def multiply(self, scalar):
        return Vector(self.x * scalar, self.y * scalar)
    def normalize(self):
        magnitude = (self.x ** 2 + self.y ** 2) ** 0.5
        if magnitude == 0:
            return Vector(0, 0)
        return Vector(self.x / magnitude, self.y / magnitude)
    def magnitude(self):
        return (self.x ** 2 + self.y ** 2) ** 0.5

bullets = []

class Bullet:
    def __init__(self, x, y, velocity, damage, pierce, lifetime, size, color, knockback):
        self.x = x
        self.y = y
        self.velocity = velocity
        self.damage = damage
        self.pierce = pierce
        self.knockback = knockback
        self.size = size
        self.color = color
        self.lifetime = lifetime
        self.age = 0
        self.speed = 25
    
    def collides(self, target):
        return (self.x - target.x) ** 2 + (self.y - target.y) ** 2 < (self.size + target.size) ** 2

    def _hits_shield(self, target):
        return hasattr(target, "ability_shield_contains_point") and target.ability_shield_contains_point(self.x, self.y)
    
    def move(self, targets):
        self.velocity = self.velocity.normalize().multiply(self.speed) 
        if self.age >= self.lifetime:
            return True  # Bullet should be removed
        self.x += self.velocity.x
        self.y += self.velocity.y
        self.age += 1
        for target in targets:
            if self._hits_shield(target):
                return True
            if self.collides(target):
                target.hurt(self)
                self.pierce -= 1
                if self.pierce <= 0:
                    return True  # Bullet should be removed
    
    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.size)

class Poison(Bullet):
    def __init__(self, x, y, velocity, damage, pierce, lifetime, size, color, knockback):
        super().__init__(x, y, velocity, damage, pierce, lifetime, size, color, knockback)
        self.damage = round(self.damage * .75)
        self.poison_duration = 60  # Duration of poison effect in frames
    
    def move(self, targets):
        self.velocity = self.velocity.normalize().multiply(self.speed) 
        if self.age >= self.lifetime:
            return True  # Bullet should be removed
        self.x += self.velocity.x
        self.y += self.velocity.y
        self.age += 1
        for target in targets:
            if self._hits_shield(target):
                return True
            if self.collides(target):
                target.hurt(self)
                poison_level = max(1, round(self.damage / 6))
                effects_mod.apply_effect(target, "poisoned", self.poison_duration, poison_level)
                self.pierce -= 1
                if self.pierce <= 0:
                    return True  # Bullet should be removed
    
    def draw(self, screen):
        super().draw(screen)
        pygame.draw.circle(screen, (0, 200, 0), (int(self.x - self.velocity.x), int(self.y - self.velocity.y)), int(self.size * 1.2), 2)


class SlashBullet(Bullet):
    def __init__(
        self,
        x,
        y,
        velocity,
        damage,
        pierce,
        lifetime,
        size,
        color,
        knockback,
        owner=None,
        length=None,
        height=None,
        base_angle=0,
        sweep_angle=40,
    ):
        super().__init__(x, y, velocity, damage, pierce, lifetime, size, color, knockback)
        self.owner = owner
        self.length = max(16, round(length if length is not None else self.size * 6))
        self.height = max(5, round(height if height is not None else self.size * 1.2))
        self.base_angle = base_angle
        self.sweep_angle = sweep_angle
        self.start_angle = self.base_angle - math.radians(self.sweep_angle) / 2
        self.end_angle = self.base_angle + math.radians(self.sweep_angle) / 2
        self.rotation_speed_multiplier = 1.25
        self.rotation_degrees = math.degrees(self.start_angle)
        self.angle = self.start_angle
        # Expand collision footprint so the slash can connect along its full length.
        self.size = max(self.size, round(self.length * 0.5))
        self._update_pose(0)

    def _anchor(self):
        if self.owner is not None:
            return self.owner.x, self.owner.y
        return self.x, self.y

    def _update_pose(self, progress):
        angle = self.start_angle + (self.end_angle - self.start_angle) * progress
        self.angle = angle
        self.velocity = Vector(math.cos(angle), math.sin(angle))
        self.rotation_degrees = -math.degrees(angle)
        anchor_x, anchor_y = self._anchor()
        self.x = anchor_x + self.velocity.x * (self.length / 2)
        self.y = anchor_y + self.velocity.y * (self.length / 2)

    def _segment_hits_target(self, target, angle):
        anchor_x, anchor_y = self._anchor()
        dir_x = math.cos(angle)
        dir_y = math.sin(angle)
        tip_x = anchor_x + dir_x * self.length
        tip_y = anchor_y + dir_y * self.length
        seg_x = tip_x - anchor_x
        seg_y = tip_y - anchor_y
        seg_len_sq = seg_x * seg_x + seg_y * seg_y
        if seg_len_sq <= 0:
            return False

        proj = ((target.x - anchor_x) * seg_x + (target.y - anchor_y) * seg_y) / seg_len_sq
        proj = max(0, min(1, proj))
        closest_x = anchor_x + seg_x * proj
        closest_y = anchor_y + seg_y * proj
        dx = target.x - closest_x
        dy = target.y - closest_y
        hit_radius = (self.height / 2) + target.size
        return (dx * dx + dy * dy) <= (hit_radius * hit_radius)

    def _segment_hits_shield(self, target, angle, sample_count=7):
        if not hasattr(target, "ability_shield_contains_point"):
            return False
        anchor_x, anchor_y = self._anchor()
        dir_x = math.cos(angle)
        dir_y = math.sin(angle)
        for index in range(sample_count + 1):
            progress = index / sample_count
            sample_x = anchor_x + dir_x * self.length * progress
            sample_y = anchor_y + dir_y * self.length * progress
            if target.ability_shield_contains_point(sample_x, sample_y):
                return True
        return False

    def _swept_collides(self, target, start_angle, end_angle):
        if self._segment_hits_target(target, start_angle) or self._segment_hits_target(target, end_angle):
            return True

        angle_delta = end_angle - start_angle
        if abs(angle_delta) <= 1e-6:
            return False

        # Sample enough intermediate rays so the tip arc step is smaller than hit thickness.
        hit_radius = max(1.0, (self.height / 2) + target.size)
        tip_arc = abs(angle_delta) * self.length
        sample_step = max(1.0, hit_radius * 0.75)
        sample_count = max(1, math.ceil(tip_arc / sample_step))

        for i in range(1, sample_count):
            progress = i / sample_count
            sweep_angle = start_angle + angle_delta * progress
            if self._segment_hits_target(target, sweep_angle):
                return True
        return False

    def _swept_hits_shield(self, target, start_angle, end_angle):
        if self._segment_hits_shield(target, start_angle) or self._segment_hits_shield(target, end_angle):
            return True

        angle_delta = end_angle - start_angle
        if abs(angle_delta) <= 1e-6:
            return False

        sample_count = max(1, math.ceil(abs(angle_delta) * self.length / 24))
        for i in range(1, sample_count):
            progress = i / sample_count
            sweep_angle = start_angle + angle_delta * progress
            if self._segment_hits_shield(target, sweep_angle):
                return True
        return False

    def collides(self, target):
        return self._segment_hits_target(target, self.angle)

    def move(self, targets):
        if self.age >= self.lifetime:
            return True

        previous_angle = self.angle
        progress = 1 if self.lifetime <= 1 else (self.age * self.rotation_speed_multiplier) / (self.lifetime - 1)
        progress = min(1, progress)
        self._update_pose(progress)
        current_angle = self.angle
        self.age += 1
        for target in targets:
            if self._swept_hits_shield(target, previous_angle, current_angle):
                return True
            if self._swept_collides(target, previous_angle, current_angle):
                target.hurt(self)
                self.pierce -= 1
                if self.pierce <= 0:
                    return True

    def draw(self, screen):
        slash_surface = pygame.Surface((self.length, self.height), pygame.SRCALPHA)
        pygame.draw.rect(
            slash_surface,
            self.color,
            pygame.Rect(0, 0, self.length, self.height),
            border_radius=max(2, self.height // 2),
        )
        rotated_slash = pygame.transform.rotate(slash_surface, self.rotation_degrees)
        rotated_rect = rotated_slash.get_rect(center=(int(self.x), int(self.y)))
        screen.blit(rotated_slash, rotated_rect)


class Bomb(Bullet):
    def __init__(self, x, y, velocity, damage, pierce, lifetime, size, color, knockback, fuse=0):
        super().__init__(x, y, velocity, damage, pierce, lifetime, size, color, knockback)
        self.lifetime = self.lifetime
        self.age = fuse + random.randint(0, round(self.lifetime/5))  # Start at a random age to create staggered explosions
        self.explosion_radius = 50
        self.explosion_time = 0
        self.blasts = []
    
    def move(self, targets):
        for blast in self.blasts:
            location, damage, blast_age = blast
            if blast_age < self.explosion_radius/2:
                for target in targets:
                    if (target.x - location[0]) ** 2 + (target.y - location[1]) ** 2 < (blast_age + target.size) ** 2:
                        target.hurt(self)
                blast_age += 4  # Increase blast age to expand explosion
                self.blasts.remove(blast)
                if blast_age < self.explosion_radius/2 - 1:
                    blast = (location, damage, blast_age)
                    self.blasts.append(blast)
        self.velocity = self.velocity.normalize().multiply(self.speed)
        for target in targets:
                if hasattr(target, "ability_shield_contains_point") and target.ability_shield_contains_point(self.x, self.y):
                    return True
                if self.collides(target):
                    self.pierce -= 1
                    if self.pierce <= 0:
                        self.age = self.lifetime  # Trigger explosion immediately
                    else:
                        self.blasts.append(((target.x, target.y), self.damage, 1))  # Store blast for later application
        if self.age >= self.lifetime:
            self.explosion_time += 4
            if self.explosion_time > self.explosion_radius:
                return True  # Bullet should be removed
            # Create explosion effect
            for target in targets:
                if (self.x - target.x) ** 2 + (self.y - target.y) ** 2 < (self.explosion_time + target.size) ** 2:
                    target.hurt(self)
        else:
            self.age += 1
            self.x += self.velocity.x/2
            self.y += self.velocity.y/2
            return False
    
    def draw(self, screen):
        if self.age < self.lifetime:
            super().draw(screen)
        else:
            pygame.draw.circle(screen, (255, 200, 0), (int(self.x), int(self.y)), int(self.explosion_time), 2)
            pygame.draw.circle(screen, (255, 150, 0), (int(self.x), int(self.y)), int(self.explosion_time + self.size), 4)
        for blast in self.blasts:
            location, damage, blast_age = blast
            pygame.draw.circle(screen, (255, 100, 0), (int(location[0]), int(location[1])), int(blast_age), 2)

class Fire(Bullet):
    def __init__(self, x, y, direction, damage, pierce, lifetime, size, color, knockback):
        super().__init__(x, y, direction, damage, pierce, lifetime, size, color, knockback)
        self.lifetime = self.lifetime * 8
        self.damage = self.damage*.07
        self.glow_red_low = 200
        self.glow_red_high = 255
        self.glow_green_low = 100
        self.glow_green_high = 150
        self.glow_red = 200
        self.glow_green = 100


    def move(self, targets):
        self.age += 1
        self.x += self.velocity.x*2
        self.y += self.velocity.y*2
        self.velocity = self.velocity.multiply(.9)
        for target in targets:
            if self.collides(target):
                target.hurt(self)
        return self.age >= self.lifetime

    def draw(self, screen):
        self.glow_red += random.randint(-5, 5)
        self.glow_green += random.randint(-5, 5)
        self.glow_green = min(self.glow_green_high, max(self.glow_green_low, self.glow_green))
        self.glow_red = min(self.glow_red_high, max(self.glow_red_low, self.glow_red))
        remaining = max(0.2, 1 - self.age / self.lifetime)
        flame_size = max(1, round(self.size * (0.5 + remaining)))
        pygame.draw.circle(screen, (self.glow_red, self.glow_green, 0), (int(self.x), int(self.y)), flame_size + 2)
        pygame.draw.circle(screen, (255, 150, 0), (int(self.x), int(self.y)), flame_size)