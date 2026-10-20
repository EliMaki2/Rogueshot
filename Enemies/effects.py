from typing import Dict, Union
import pygame
from typing import List
import random
from helpers import RGB_Color
from Enemies.enemies import Enemy

effects= []

class Effect:
    def __init__(self, entity:Enemy, duration:int, level:int, color:RGB_Color):
        self.name = "NothingYet"
        self.entity = entity
        self.duration = duration
        self.elapsed = 0
        self.level = level
        self.tick_delay = 0
        self.tick_interval = 5
        self.color = color  # Default color, can be overridden by subclasses

    def update(self):
        if self.entity.health <= 1:
            if self in effects:
                effects.remove(self)
            return
        if self.elapsed >= self.duration:
            self.expire()
        self.elapsed += 1
        if self.tick_delay < self.tick_interval:
            self.tick_delay += 1
            return
        self.tick()
        self.tick_delay = 0

    def expire(self):
        if self.level > 0:
            self.level -= 1
            self.elapsed = 0
        else:
            if self in effects:
                effects.remove(self)

    def tick(self):
        pass

    def draw(self, surface):
        pygame.draw.circle(surface, self.color.to_tuple(), (self.entity.x, self.entity.y), self.entity.size+1, 2)
        pygame.draw.circle(surface, self.color.brighten(.8).to_tuple(), (self.entity.x, self.entity.y), self.entity.size+5, round(6*(self.tick_delay/self.tick_interval)))
        for _ in range(self.level):
            pygame.draw.circle(surface, self.color.brighten(.6).to_tuple(), (self.entity.x + random.randint(round(-self.entity.size), round(self.entity.size)), self.entity.y + random.randint(round(-self.entity.size), round(self.entity.size))), round(self.entity.size/3), 2)
        

class Burning(Effect):
    def __init__(self, entity, duration, level):
        super().__init__(entity, duration, level, RGB_Color(255, 200, 100))
        self.name = "burning"
        self.color = RGB_Color(255, 100, 100)

    def tick(self):
        self.entity.hurt(self.level*2, direct_damage=True)

class Poisoned(Effect):
    def __init__(self, entity, duration, level):
        super().__init__(entity, duration, level, RGB_Color(150, 255, 50))
        self.name = "poisoned"
        self.color = RGB_Color(150, 255, 50)
        self.tick_interval = 15

    def tick(self):
        self.entity.hurt(self.level, direct_damage=True)
        self.entity.velocity = self.entity.velocity.multiply(1 - 0.2 * self.level)
        print(f"Poisoned tick on entity {self.entity} with level {self.level}")

class Frozen(Effect):
    def __init__(self, entity, duration, level):
        super().__init__(entity, duration, level, RGB_Color(120, 60, 255))
        self.name = "frozen"
        self.color = RGB_Color(120, 60, 255)
        self.tick_interval = 2
        self.lock_x = self.entity.x
        self.lock_y = self.entity.y

    def tick(self):
        self.entity.velocity = self.entity.velocity.multiply(.1)
        if self.entity.x > self.lock_x - 3:
            self.entity.x -= 3
        if self.entity.x < self.lock_x + 3:
            self.entity.x += 3
        if self.entity.y > self.lock_y - 3:
            self.entity.y -= 3
        if self.entity.y < self.lock_y + 3:
            self.entity.y += 3

    def draw(self, surface):
        super().draw(surface)
        pygame.draw.circle(surface, (0, 0, 200), (self.lock_x, self.lock_y), 6, 2)

class Mending(Effect):
    def __init__(self, entity, duration, level):
        super().__init__(entity, duration, level, RGB_Color(55, 255, 75))
        self.name = "mending"
        self.color = RGB_Color(55, 255, 75)

    def tick(self):
        self.entity.health = min(self.entity.max_health, self.entity.health + self.level)

class Shocked(Effect):
    def __init__(self, entity, duration, level):
        super().__init__(entity, duration, level, RGB_Color(255, 0, 250))
        self.name = "shocked"
        self.color = RGB_Color(255, 0, 250)
        self.tick_interval = 5

    def tick(self):
        self.entity.hurt(self.level/2, direct_damage=True)
        print(self.level)
        jump_target = self.entity.closest_enemy([(Shocked, self.level)])
        if self.entity.distance_to(jump_target) < 100:
            if random.random() < 0.3:
                apply_effect(entity=jump_target, effect_name="shocked", duration=120, level=max(1, self.level - 1))


def entity_has_effect(entity, effect_class, effect_level=None):
    for each_effect in effects:
        print(f"Checking effect {effect_class}, {effect_level} on entity {entity}")
        if each_effect.entity == entity and isinstance(each_effect, effect_class):
            if effect_level is None or each_effect.level >= effect_level:
                return each_effect
    return False

Effects_map = {"burning": Burning,
               "poisoned": Poisoned, 
               "frozen": Frozen, 
               "mending": Mending,
               "shocked": Shocked}

Effects_color_map = {
    "burning": RGB_Color(255, 100, 100),
    "poisoned": RGB_Color(150, 255, 50),
    "frozen": RGB_Color(120, 90, 255),
    "mending": RGB_Color(55, 255, 75),
    "shocked": RGB_Color(255, 0, 250)
}

def apply_effect(entity, effect_name: str, duration: int, level: int):
    effect_instance = Effects_map.get(effect_name, None)
    if effect_instance is None:
        return
    current_effect = entity_has_effect(entity, effect_class=effect_instance, effect_level=level)
    if current_effect:
        current_effect.level += level
        return
    effects.append(effect_instance(entity, duration, level))

def update_effects():
    #call every tick
    for effect in effects:
        effect.update()

def draw_effects(surface):
    #call before rendering the entity
    for effect in effects[:]:
        effect.draw(surface)
