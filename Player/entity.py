import math
import pygame

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

class Entity:
    def __init__(self, x, y, size, color, health):
        self.x = x
        self.y = y
        self.size = size
        self.color = color
        self.health = health
        self.max_health = health
        self.velocity = Vector(0, 0)
        self.speed = 1
        self.alive = True

    def draw(self, screen, font=None):
        import pygame
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.size)
        pygame.draw.circle(screen, (255, 255, 255), (int(self.x), int(self.y)), self.size, 2)
        if self.health < self.max_health:
            health_ratio = self.health / self.max_health
            pygame.draw.rect(screen, (100, 100, 100), (self.x - self.size, self.y - self.size - 10, self.size*2, 5))
            pygame.draw.rect(screen, (0, 255, 0), (self.x - self.size, self.y - self.size - 10, self.size * 2 * health_ratio, 5))
            if font:
                text_surface = font.render(f"Health: {self.health}/{self.max_health}", True, (150,150,150))
                text_rect = text_surface.get_rect(center=((self.x + self.size/2), (self.y - self.size - 20)))
                screen.blit(text_surface, text_rect)

    def move(self):
        self.x += self.velocity.x
        self.y += self.velocity.y
        self.velocity = self.velocity.multiply(0.9)

    def hurt(self, damage):
        self.health -= damage
        if self.health <= 0:
            self.health = 0
            self.alive = False
