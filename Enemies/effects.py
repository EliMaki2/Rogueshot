import pygame
import random


def apply_effect(entity, effect, duration, level):
    if effect == "burning":
        effect = Burning(entity, duration, level)
    elif effect == "poisoned":
        effect = Poisoned(entity, duration, level)
    elif effect == "frozen":
        effect = Frozen(entity, duration, level)
    effects.append(effect)


effects = []


def update_effects():
    # call every tick
    for effect in effects:
        effect.update()


def draw_effects(surface):
    # call before rendering the entity
    for effect in effects:
        effect.draw(surface)


class Burning:
    def __init__(self, entity, duration, level):
        self.entity = entity
        self.duration = duration
        self.elapsed = 0
        self.level = level
        self.tick_delay = 0
        self.tick_interval = 5

    def update(self):
        if self.entity.health <= 1:
            self.expire()
            return
        self.tick()
        self.elapsed += 1
        if self.elapsed >= self.duration:
            self.expire()

    def expire(self):
        if self.level > 0:
            self.level -= 1
            self.elapsed = 0
        else:
            if self in effects:
                effects.remove(self)

    def tick(self):
        if self.tick_delay < self.tick_interval:
            self.tick_delay += 1
            return
        self.entity.hurt(self.level * 2, direct_damage=True)
        self.tick_delay = 0

    def draw(self, surface):
        pygame.draw.circle(
            surface,
            (255, 0, 0),
            (self.entity.x, self.entity.y),
            self.entity.radius + 1,
            2,
        )
        pygame.draw.circle(
            surface,
            (200, 165, 0),
            (self.entity.x, self.entity.y),
            self.entity.radius + 4,
            round(5 * (self.tick_delay / self.tick_interval)),
        )
        for i in range(self.level):
            pygame.draw.circle(
                surface,
                (140, 69, 0),
                (
                    self.entity.x
                    + random.randint(
                        round(-self.entity.radius), round(self.entity.radius)
                    ),
                    self.entity.y
                    + random.randint(
                        round(-self.entity.radius), round(self.entity.radius)
                    ),
                ),
                round(self.entity.radius / 3),
                2,
            )


class Poisoned:
    def __init__(self, entity, duration, level):
        self.entity = entity
        self.duration = duration
        self.elapsed = 0
        self.level = level
        self.tick_delay = 0
        self.tick_interval = 15

    def update(self):
        if self.entity.health <= 0:
            self.expire()
            return
        self.tick()
        self.elapsed += 1
        if self.elapsed >= self.duration:
            self.expire()

    def expire(self):
        if self.level > 0:
            self.level -= 1
            self.elapsed = 0
        else:
            if self in effects:
                effects.remove(self)

    def tick(self):
        if self.tick_delay < self.tick_interval:
            self.tick_delay += 1
            return
        self.entity.hurt(self.level, direct_damage=True)
        self.entity.velocity = self.entity.velocity.multiply(1 - 0.2 * self.level)
        self.tick_delay = 0

    def draw(self, surface):
        pygame.draw.circle(
            surface,
            (0, 255, 0),
            (self.entity.x, self.entity.y),
            self.entity.size + 1,
            2,
        )
        pygame.draw.circle(
            surface,
            (0, 165, 0),
            (self.entity.x, self.entity.y),
            self.entity.size + 3,
            round(4 * (self.tick_delay / self.tick_interval)),
        )
        for i in range(self.level):
            pygame.draw.circle(
                surface,
                (0, 100, 0),
                (
                    self.entity.x
                    + random.randint(round(-self.entity.size), round(self.entity.size)),
                    self.entity.y
                    + random.randint(round(-self.entity.size), round(self.entity.size)),
                ),
                round(self.entity.size / 3),
                2,
            )


class Frozen:
    def __init__(self, entity, duration, level):
        self.entity = entity
        self.duration = duration
        self.elapsed = 0
        self.level = level
        self.tick_delay = 0
        self.tick_interval = 2
        self.lock_x = self.entity.x
        self.lock_y = self.entity.y

    def update(self):
        if self.entity.health <= 0:
            self.expire()
            return
        self.tick()
        self.elapsed += 1
        if self.elapsed >= self.duration:
            self.expire()

    def expire(self):
        if self.level > 0:
            self.level -= 1
            self.elapsed = 0
        else:
            if self in effects:
                effects.remove(self)

    def tick(self):
        if self.tick_delay < self.tick_interval:
            self.tick_delay += 1
            return
        self.entity.velocity = self.entity.velocity.multiply(0.1)
        if self.entity.x > self.lock_x - 3:
            self.entity.x -= 3
        if self.entity.x < self.lock_x + 3:
            self.entity.x += 3
        if self.entity.y > self.lock_y - 3:
            self.entity.y -= 3
        if self.entity.y < self.lock_y + 3:
            self.entity.y += 3
        self.tick_delay = 0

    def draw(self, surface):
        pygame.draw.circle(
            surface,
            (0, 0, 255),
            (self.entity.x, self.entity.y),
            self.entity.size + 1,
            2,
        )
        pygame.draw.circle(
            surface,
            (0, 0, 165),
            (self.entity.x, self.entity.y),
            self.entity.size + 3,
            round(4 * (self.tick_delay / self.tick_interval)),
        )
        pygame.draw.circle(surface, (0, 0, 200), (self.lock_x, self.lock_y), 6, 2)
        for i in range(self.level):
            pygame.draw.circle(
                surface,
                (0, 0, 100),
                (
                    self.entity.x
                    + random.randint(round(-self.entity.size), round(self.entity.size)),
                    self.entity.y
                    + random.randint(round(-self.entity.size), round(self.entity.size)),
                ),
                round(self.entity.size / 3),
                2,
            )
