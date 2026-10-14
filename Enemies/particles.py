import random
import pygame

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

class HitParticle:
    def __init__(self, x, y, size, color):
        self.x = x
        self.y = y
        self.size = size
        self.color = color
        self.direction = Vector(0,0)

    def move(self):
        self.x += self.direction.x
        self.y += self.direction.y
        self.size -= 0.35
        self.direction.x += random.uniform(-0.6, 0.6)
        self.direction.y += random.uniform(-0.6, 0.6)
        return self.size >= 1
    
    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), int(self.size))

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
