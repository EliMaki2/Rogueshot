import random
import pygame
from helpers import Vector

MAX_PARTICLES = 1200
SOFT_PARTICLE_CAP = 800


class ParticleList(list):
    def append(self, item):
        count = len(self)
        if count >= MAX_PARTICLES:
            return
        if count >= SOFT_PARTICLE_CAP:
            overload = (count - SOFT_PARTICLE_CAP) / (MAX_PARTICLES - SOFT_PARTICLE_CAP)
            if random.random() < overload:
                return
        super().append(item)


particles = ParticleList()


class HitParticle:
    def __init__(self, x, y, size, color):
        self.x = x
        self.y = y
        self.size = size
        self.color = color
        self.direction = Vector(0, 0)

    def move(self):
        self.x += self.direction.x
        self.y += self.direction.y
        self.size -= 0.35
        self.direction.x += random.uniform(-0.6, 0.6)
        self.direction.y += random.uniform(-0.6, 0.6)
        return self.size >= 1

    def draw(self, screen):
        pygame.draw.circle(
            screen, self.color, (int(self.x), int(self.y)), int(self.size)
        )

    def remove(self):
        self.size = 0


def update_and_draw(screen):
    if not particles:
        return
    alive_particles = []
    append_alive = alive_particles.append
    for effect in particles:
        if effect.move():
            effect.draw(screen)
            append_alive(effect)
    particles[:] = alive_particles
