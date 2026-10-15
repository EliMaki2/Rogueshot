import pygame
import random
import math

from Player.gun import Shotgun, Blowdart, Cannon, Blade, Flamethrower
from Player.entity import Entity
import Player.bullets as bullets_file
import Enemies.particles as particles_file
from Background import run_stats
from helpers import Vector

class PlayerBody(Entity):
    def __init__(self, x, y, size=20, color=(250,250,250), health=10):
        super().__init__(x, y, size, color, health)
        # Gun stats are now on the player
        self.attack_speed = 20
        self.attack_spread = 0.05
        self.multishot = 3
        self.pierce = 3
        self.attack_range = 10
        self.damage = 1
        self.bullet_color = (255,255,255)
        self.knockback = 0.1
        self.bullet_speed = 5
        self.attack_cooldown = 0
        self.pickup = 200
        self.gun = Cannon(self)
        self.iframes = 0
        self.body_effect_unlocked = False
        self.gun_effect_unlocked = False
        self.body_boost_tier = 0
        self.gun_boost_tier = 0
        self.sword_guard_timer = 0
        self.post_hit_parry_timer = 0
        self.post_hit_refund_damage = 0
        self.pending_parry_death = False
        self.dash_stamp_timer = 0
    
    def shoot(self, direction):
        self.gun.shoot(direction, bullets_file.bullets)

    def move(self):
        self.sword_guard_timer = max(0, self.sword_guard_timer - 1)
        self.post_hit_parry_timer = max(0, self.post_hit_parry_timer - 1)
        self.dash_stamp_timer = max(0, self.dash_stamp_timer - 1)
        if self.post_hit_parry_timer == 0 and self.pending_parry_death:
            self.health = 0
            self.alive = False
            self.pending_parry_death = False
        if self.post_hit_parry_timer == 0:
            self.post_hit_refund_damage = 0
        self.gun.update()
        super().move()
        
    def hurt(self, enemy, direct_damage=False):
        if self.iframes > 0:
            return
        if direct_damage:
            self.health -= enemy
            self.iframes = 30
            return
        
        if (isinstance(self.gun, Blade) 
            #and getattr(self, "gun_effect_unlocked", False) 
            and not self.gun_effect_unlocked 
            and self.sword_guard_timer > 0):
            self._on_successful_parry(enemy)
            return
        
        self.iframes = 30
        damage_taken = max(0, round(enemy.damage))

        if damage_taken <= 0:
            return
        
        pre_hit_health = self.health
        self.health -= damage_taken
        would_die = self.health <= 0

        if would_die:
            self.health = 1
            self.alive = True
            
        actual_damage = min(pre_hit_health, damage_taken)
        self._start_post_hit_parry_window(actual_damage, would_die)

    def _start_post_hit_parry_window(self, damage_taken, lethal_hit):
        if damage_taken <= 0:
            return
        self.post_hit_parry_timer = max(self.post_hit_parry_timer, 10)
        self.post_hit_refund_damage = damage_taken
        if lethal_hit:
            self.pending_parry_death = True

    def try_post_hit_parry(self):
        if self.post_hit_parry_timer <= 0:
            return False
        if self.post_hit_refund_damage <= 0 and not self.pending_parry_death:
            return False
        self.health = min(self.max_health, self.health + self.post_hit_refund_damage)
        self.post_hit_refund_damage = 0
        self.post_hit_parry_timer = 0
        self.pending_parry_death = False
        self.alive = True
        self.iframes = max(self.iframes, 8)
        self._spawn_parry_burst()
        self._spawn_parry_particles()
        return True

    def _on_successful_parry(self, enemy=None):
        if enemy is not None and enemy.__class__.__name__ == "Spiker":
            run_stats.record_secret_progress("spiker_parries", 1)
        if not self.try_post_hit_parry():
            self._spawn_parry_burst()
        self.sword_guard_timer = 0
        self.iframes = 8

    def _spawn_parry_burst(self):
        burst_count = 10
        base_damage = max(1, round(self.damage * 1.5))
        burst_color = (255, 235, 80)
        lifetime = max(10, round(self.attack_range * 1.1))
        for index in range(burst_count):
            angle = (2 * math.pi * index) / burst_count
            velocity = Vector(math.cos(angle), math.sin(angle))
            bullets_file.bullets.append(
                bullets_file.Bullet(
                    self.x,
                    self.y,
                    velocity,
                    base_damage,
                    1,
                    lifetime,
                    4,
                    burst_color,
                    max(0.15, self.knockback * 1.5),
                )
            )

    def _spawn_parry_particles(self):
        particle_count = 22
        particle_color = (255, 235, 80)
        for _ in range(particle_count):
            particle = particles_file.HitParticle(
                self.x + random.randint(-8, 8),
                self.y + random.randint(-8, 8),
                random.randint(5, 10),
                particle_color,
            )
            particle.direction = Vector(
                random.randint(-180, 180) / 100,
                random.randint(-180, 180) / 100,
            )
            particles_file.particles.append(particle)
    
    def draw(self, screen, font=None):
        super().draw(screen, font)
        pygame.draw.circle(screen, (100, 100, 255), (int(self.x), int(self.y)), self.size-3, 8)
        self.gun.draw(self, screen)
        if self.iframes > 0:
            self.iframes -= 1
            pygame.draw.circle(screen, (255, 255, 255), (int(self.x), int(self.y)), self.size + self.iframes, 2)


def spawn_unlock_particles(player, count, color=None):
    burst_color = color or player.color
    for _ in range(count):
        particle = particles_file.HitParticle(player.x, player.y, random.randint(6, 14), burst_color)
        particle.x += random.randint(-8, 8)
        particle.y += random.randint(-8, 8)
        particle.direction = Vector(random.randint(-120, 120) / 100, random.randint(-120, 120) / 100)
        particles_file.particles.append(particle)


class Retribution(PlayerBody):
    def __init__(self, x, y, size=20, color=(250,200,200), health=10):
        super().__init__(x, y, size, color, health)
        self.retribution = True
        self.rage_time = 0
    
    def hurt(self, enemy, direct_damage=False):
        if self.iframes <= 0:
            if self.body_effect_unlocked:
                self.rage()
            super().hurt(enemy, direct_damage=direct_damage)
            if self.retribution:
                def fire_retribution_shot(direction):
                    if isinstance(self.gun, Blade):
                        self.gun.shoot(direction, bullets_file.bullets, ignore_cooldown=True, allow_parry=False)
                    else:
                        self.gun.shoot(direction, bullets_file.bullets, ignore_cooldown=True)

                for i in range(self.body_boost_tier + 1):
                    fire_retribution_shot("up")
                    fire_retribution_shot("down")
                    fire_retribution_shot("left")
                    fire_retribution_shot("right")
                for i in range(self.body_boost_tier//2):
                    fire_retribution_shot("up-left")
                    fire_retribution_shot("up-right")
                    fire_retribution_shot("down-left")
                    fire_retribution_shot("down-right")
    
    def rage(self):
        self.rage_time = 120 + self.body_boost_tier*30
        self.damage = round(self.damage * 1.3)
        self.attack_speed = max(3, self.attack_speed - 5)
        self.attack_spread += 0.02
        self.multishot += 2
    
    def draw(self, screen, font=None):
        super().draw(screen, font)
        if self.rage_time > 0:
            pygame.draw.circle(screen, (250, 100, 100), (int(self.x), int(self.y)), self.size + round(self.rage_time/5), 4)
            self.rage_time -= 1
            self.attack_cooldown -= 5
            if self.attack_cooldown < 0:
                self.attack_cooldown = 0
            if self.rage_time == 0:
                self.damage = round(self.damage / 1.3)
                self.attack_speed += 5
                self.attack_spread -= 0.02
                self.multishot -= 2

class Dasher(PlayerBody):
    def __init__(self, x, y, size=20, color=(250,250,200), health=10):
        super().__init__(x, y, size, color, health)
        self.dash_cooldown = 0
        self.dash_cooldown_duration = 60
    
    def dash(self, direction):
        if self.body_effect_unlocked:
            self.iframes = 20
        if self.dash_cooldown <= 0:
            dash_vector = Vector(0, 0)
            if direction == "up":
                dash_vector = Vector(0, -1)
            elif direction == "down":
                dash_vector = Vector(0, 1)
            elif direction == "left":
                dash_vector = Vector(-1, 0)
            elif direction == "right":
                dash_vector = Vector(1, 0)
            elif direction == "up-left":
                dash_vector = Vector(-1, -1).normalize()
            elif direction == "up-right":
                dash_vector = Vector(1, -1).normalize()
            elif direction == "down-left":
                dash_vector = Vector(-1, 1).normalize()
            elif direction == "down-right":
                dash_vector = Vector(1, 1).normalize()
            self.velocity = self.velocity.add(dash_vector.multiply(20))
            self.dash_stamp_timer = 8
            self.dash_cooldown = self.dash_cooldown_duration
    
    def move(self):
        if self.dash_cooldown > 0:
            self.dash_cooldown -= 1
        super().move()

class Nova(PlayerBody):
    def __init__(self, x, y, size=20, color=(200,250,250), health=10):
        super().__init__(x, y, size, color, health)
        self.nova_cooldown = 0
        self.nova_range = 150
        self.nova_duration = 25
        self.nova_time = 0
        self.affected_targets = []
    
    def nova(self, targets):
        if self.nova_cooldown <= 0:
            for target in targets:
                if (Vector(target.x - self.x, target.y - self.y).magnitude) <= self.nova_range:
                    self.affected_targets.append((target, self.nova_duration))
                    target.health -= round(self.damage * .5)
                elif self.body_effect_unlocked:
                    if (Vector(target.x - self.x, target.y - self.y).magnitude) <= self.nova_range*3:
                        self.affected_targets.append((target, self.nova_duration/2))
                        target.health -= round(self.damage * .2)
            if self.nova_time <= 0:
                self.nova_time = 25
            self.nova_cooldown = 120 
    
    def move(self):
        if self.nova_cooldown > 0:
            self.nova_cooldown -= 1
        if self.nova_time > 0:
            self.nova_time -= 1
        super().move()
    
    def draw(self, screen, font=None):
        super().draw(screen, font)
        if self.nova_time > 0:
            pygame.draw.circle(screen, (0, 200, 250), (int(self.x), int(self.y)), self.nova_range*((self.nova_time / 25)), 2)
            if self.body_effect_unlocked:
                pygame.draw.circle(screen, (0, 150, 200), (int(self.x), int(self.y)), self.nova_range*3*((self.nova_time / 25)), 2)
        for target, duration in self.affected_targets:
            if duration > 0:
                pygame.draw.circle(screen, (0, 100, 250), (int(target.x), int(target.y)), target.size + 5, 2)
                target.velocity = Vector(target.x - self.x, target.y - self.y).normalize().multiply(3)
                target.x += target.velocity.x
                target.y += target.velocity.y
                index = self.affected_targets.index((target, duration))
                self.affected_targets[index] = (target, duration - 1)
            else:
                self.affected_targets.remove((target, duration))


class Slime(PlayerBody):
    def __init__(self, x, y, size=20, color=(200,250,200), health=10):
        super().__init__(x, y, size, color, health)
        self.slime_trail = []
        self.trail_length = 1000
        self.slime_cooldown = 0
        self.slime_size = 15
    
    def move(self):
        updated_trail = []
        for x, y, size, color in self.slime_trail:
            new_size = size - 0.05
            if new_size > 1:
                updated_trail.append((x, y, new_size, color))
        self.slime_trail = updated_trail
        if self.slime_cooldown > 0:
            self.slime_cooldown -= 1
        super().move()
        last_slime_position = self.slime_trail[-1] if self.slime_trail else None
        distance_from_last_slime = ((self.x - last_slime_position[0]) ** 2 + (self.y - last_slime_position[1]) ** 2) ** 0.5 if last_slime_position else float('inf')
        if self.slime_cooldown <= 0 and distance_from_last_slime >= 5:
            self.slime_cooldown = 4
            self.slime_trail.append((self.x, self.y, self.slime_size, (100,150,100)))
            if len(self.slime_trail) > self.trail_length:
                self.slime_trail.pop(0)
    
    def slime_target(self, targets):
        for target in targets:
            for slimes in self.slime_trail:
                x, y, size, color = slimes
                if Vector(target.x - x, target.y - y).magnitude <= size + target.size:
                    if target.harm_frames <= 0:
                        target.health -= round(self.damage * 0.8)
                        target.harm_frames = 10 
                    target.velocity = target.velocity.multiply(-.3)
                    target.x += target.velocity.x
                    target.y += target.velocity.y
                    break
    
    def slime_effect(self):
        if self.body_effect_unlocked and self.slime_cooldown <= 5:
            for x in range(-200, 200, 35):
                for y in range(-200, 200, 35):
                    if Vector(x, y).magnitude <= 100:
                        self.slime_trail.append((self.x + x + random.randint(-10, 10), self.y + y + random.randint(-10, 10), self.slime_size+5, (100,150,100)))
            self.slime_cooldown = 40
    
    def draw(self, screen, font=None):
        super().draw(screen, font)
    
    def draw_slime_trail(self, screen):
        for x, y, size, color in self.slime_trail:
            if size > 0:
                pygame.draw.circle(screen, color, (int(x), int(y)), round(size))
    
    def hurt(self, enemy):
        if self.iframes <= 0:
            super().hurt(enemy)
            self.slime_trail.append((self.x, self.y, self.slime_size, (100,150,100)))


BODY_TYPES = {
    "Dasher": Dasher,
    "Retribution": Retribution,
    "Nova": Nova,
    "Slime" : Slime,
}

GUN_TYPES = {
    "Cannon": Cannon,
    "Shotgun": Shotgun,
    "Blowdart": Blowdart,
    "Sword" : Blade,
    "Flamethrower": Flamethrower,
}

BODY_SUMMARIES = {
    "Dasher": "Dash with shift \nfor quick repositioning.",
    "Retribution": "Fire a burst in  \nevery direction when hit.",
    "Nova": "Release a nova that \npushes nearby enemies with shift.",
    "Slime": "Leave a damaging slime \ntrail as you move.",
}

GUN_SUMMARIES = {
    "Cannon": "Heavy explosive shells \nwith a slower fire rate.",
    "Shotgun": "Wide spreads of standard bullets.",
    "Blowdart": "Fast poison shots \nwith tighter spread.",
    "Sword": "Short-range sweep that \nslashes in a wide line",
    "Flamethrower": "A close-range stream of \nlingering fire.",
}

_PRESERVED_PLAYER_FIELDS = [
    "x",
    "y",
    "size",
    "health",
    "max_health",
    "velocity",
    "speed",
    "alive",
    "attack_speed",
    "attack_spread",
    "multishot",
    "pierce",
    "attack_range",
    "damage",
    "bullet_color",
    "knockback",
    "bullet_speed",
    "attack_cooldown",
    "pickup",
    "body_effect_unlocked",
    "gun_effect_unlocked",
    "body_boost_tier",
    "gun_boost_tier",
    "sword_guard_timer",
    "post_hit_parry_timer",
    "post_hit_refund_damage",
    "pending_parry_death",
    "dash_cooldown_duration",
]


def apply_body_effect_unlock(player):
    player.body_effect_unlocked = True
    if isinstance(player, Dasher):
        player.dash_cooldown_duration = 45
    spawn_unlock_particles(player, 60, (255, 220, 120))


def apply_gun_effect_unlock(player):
    player.gun_effect_unlocked = True
    spawn_unlock_particles(player, 80, player.bullet_color)


def apply_body_stat_boost(player):
    if isinstance(player, Dasher):
        player.speed += 0.12
        player.dash_cooldown_duration = max(30, player.dash_cooldown_duration - 5)
    elif isinstance(player, Retribution):
        player.max_health += 3
        player.health = min(player.max_health, player.health + 3)
    elif isinstance(player, Nova):
        player.nova_range += 20
        player.damage += 0.5
    elif isinstance(player, Slime):
        player.damage += 0.5
        player.slime_size += 2


def apply_gun_stat_boost(player):
    gun = getattr(player, "gun", None)
    if isinstance(gun, Cannon):
        player.damage += 0.35
    elif isinstance(gun, Shotgun):
        player.attack_spread = max(0.01, player.attack_spread - 0.004)
    elif isinstance(gun, Blowdart):
        player.attack_speed = max(3, player.attack_speed - 1)
    elif isinstance(gun, Flamethrower):
        player.attack_speed = max(3, player.attack_speed - 1)
    elif isinstance(gun, Blade):
        player.damage += 0.5
        player.attack_range += 2


def apply_level_progression(player, level):
    events = []

    if level >= 5 and not getattr(player, "body_effect_unlocked", False):
        apply_body_effect_unlock(player)
        if isinstance(player, Dasher):
            descrip = "Player is now \n invincible while dashing."
        elif isinstance(player, Retribution):
            descrip = "Player rages \nwhen hit."
        elif isinstance(player, Nova):
            descrip = "Nova now has a larger \nbut weaker secondary blast."
        elif isinstance(player, Slime):
            descrip = "Can now slime \na large zone."
        else:
            descrip = f"{get_body_name(player)} unlocked \nits special effect."
        events.append({
            "kind": "body_unlock",
            "title": "Body Unlock",
            "description": descrip,
            "color": (255, 205, 120),
        })

    if level >= 10 and not getattr(player, "gun_effect_unlocked", False):
        apply_gun_effect_unlock(player)
        if isinstance(player.gun, Cannon):
            descrip = "Cannon shots are much larger."
        elif isinstance(player.gun, Shotgun):
            descrip = "Shotgun now fires much wider."
        elif isinstance(player.gun, Blowdart):
            descrip = "Blowdart shots poison longer."
        elif isinstance(player.gun, Blade):
            descrip = "Timed sword swings can \nblock incoming damage."
        elif isinstance(player.gun, Flamethrower):
            descrip = "Flamethrower now fires faster and wider."
        else:
            descrip = f"{get_gun_name(player)} unlocked \nits special effect."
        events.append({
            "kind": "gun_unlock",
            "title": "Gun Unlock",
            "description": descrip,
            "color": (120, 190, 255),
        })

    target_body_boost_tier = 0
    if level >= 20:
        target_body_boost_tier = ((level - 20) // 15) + 1

    target_gun_boost_tier = 0
    if level >= 25:
        target_gun_boost_tier = ((level - 25) // 15) + 1

    while player.body_boost_tier < target_body_boost_tier:
        apply_body_stat_boost(player)
        player.body_boost_tier += 1
        events.append({
            "kind": "body_boost",
            "title": "Body Boost",
            "description": f"{get_body_name(player)} gained a permanent stat boost.",
            "color": (120, 255, 160),
        })

    while player.gun_boost_tier < target_gun_boost_tier:
        apply_gun_stat_boost(player)
        player.gun_boost_tier += 1
        events.append({
            "kind": "gun_boost",
            "title": "Gun Boost",
            "description": f"{get_gun_name(player)} gained a permanent stat boost.",
            "color": (190, 140, 255),
        })

    return events


def get_body_name(player):
    for body_name, body_class in BODY_TYPES.items():
        if isinstance(player, body_class):
            return body_name
    return "Dasher"


def get_gun_name(player):
    gun = getattr(player, "gun", None)
    for gun_name, gun_class in GUN_TYPES.items():
        if isinstance(gun, gun_class):
            return gun_name
    return "Shotgun"


def create_player(body_name, x, y, size=20, health=10):
    body_class = BODY_TYPES.get(body_name, Dasher)
    return body_class(x=x, y=y, size=size, health=health)


def equip_gun(player, gun_name):
    gun_class = GUN_TYPES.get(gun_name, Shotgun)
    player.gun = gun_class(player)
    return player


def rebuild_player(player, body_name=None, gun_name=None):
    target_body_name = body_name or get_body_name(player)
    target_gun_name = gun_name or get_gun_name(player)
    target_body_class = BODY_TYPES.get(target_body_name, Dasher)

    if isinstance(player, target_body_class):
        updated_player = player
    else:
        base_health = max(1, round(getattr(player, "max_health", getattr(player, "health", 10))))
        updated_player = target_body_class(player.x, player.y, size=player.size, health=base_health)
        for field_name in _PRESERVED_PLAYER_FIELDS:
            if hasattr(player, field_name):
                setattr(updated_player, field_name, getattr(player, field_name))

    if hasattr(updated_player, "dash_cooldown") and hasattr(player, "dash_cooldown"):
        updated_player.dash_cooldown = player.dash_cooldown
    if hasattr(updated_player, "retribution") and hasattr(player, "retribution"):
        updated_player.retribution = player.retribution

    return equip_gun(updated_player, target_gun_name)
