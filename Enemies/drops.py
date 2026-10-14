import random
import pygame

# Define drops list and exp here
drops = []
exp = 0
exp_bonus_multiplier = 1.0


def update_exp_bonus(haunting_options=None, swarm_options=None):
    """Update EXP gain multiplier from currently enabled options."""
    global exp_bonus_multiplier
    haunting_options = haunting_options or {}
    swarm_options = swarm_options or {}

    haunting_enabled_count = sum(1 for enabled in haunting_options.values() if bool(enabled))
    swarm_enabled = bool(swarm_options.get("enabled", False))
    selected_swarm_types = swarm_options.get("enemy_types", [])
    if not isinstance(selected_swarm_types, (list, tuple, set)):
        selected_swarm_types = []
    if not selected_swarm_types and swarm_options.get("enemy_type"):
        selected_swarm_types = [swarm_options.get("enemy_type")]
    swarm_selected_count = len({str(enemy_name).strip() for enemy_name in selected_swarm_types if str(enemy_name).strip()})
    exp_bonus_multiplier = 1.0 + (0.05 * haunting_enabled_count) + ((0.15 * swarm_selected_count) if swarm_enabled else 0.0)


def create_edge_exp_drop(amount, screen_width, screen_height):
    side = random.choice(("left", "right", "top", "bottom"))
    edge_offset = 50
    if side == "left":
        x = edge_offset
        y = random.randint(edge_offset, max(edge_offset, screen_height - edge_offset))
    elif side == "right":
        x = max(edge_offset, screen_width - edge_offset)
        y = random.randint(edge_offset, max(edge_offset, screen_height - edge_offset))
    elif side == "top":
        x = random.randint(edge_offset, max(edge_offset, screen_width - edge_offset))
        y = edge_offset
    else:
        x = random.randint(edge_offset, max(edge_offset, screen_width - edge_offset))
        y = max(edge_offset, screen_height - edge_offset)
    return ExpDrop(x, y, amount)

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

class ExpDrop:
    def __init__(self, x, y, amount, color=(255, 255, 0), size=5):
        self.x = x
        self.y = y
        self.amount = amount
        self.color = color
        self.size = size
        self.movement = Vector(random.uniform(-1, 1), random.uniform(-1, 1)).normalize().multiply(2)
        self.drop_friction = 1
        self.age = 0
        self.persistent = False

    def draw(self, screen):
        dark_color = (max(0, self.color[0] - 50), max(0, self.color[1] - 50), max(0, self.color[2] - 50))
        if not self.persistent and self.age > (1000/8)*7 and self.age % 20 < 10:
            pass
        else:
            pygame.draw.polygon(screen, dark_color, [(self.x - self.size, self.y+self.size), (self.x, self.y - self.size), (self.x + self.size, self.y+self.size)])
            pygame.draw.lines(screen, self.color, True, [(self.x - self.size, self.y+self.size), (self.x, self.y - self.size), (self.x + self.size, self.y+self.size)], 2)
    
    def move(self):
        self.age = 0 if self.persistent else self.age + 1
        if self.age > 1000:
            self.amount -= .1
        if self.amount <= 0:
            drops.remove(self)
        if self.amount > 1:
            if self.amount > 2:
                if self.amount > 5:
                    if self.amount > 10:
                        if self.amount > 30:
                            self.size = 15
                            self.color = (255, 100, 0)
                        else:
                            self.size = 10
                            self.color = (255, 150, 0)
                    else:
                         self.size = 7
                         self.color = (255, 200, 0)
                else:
                    self.size = 5
                    self.color = (255, 255, 0)
            else:
                self.size = 3
                self.color = (255, 255, 0)
        for other in drops:
            if other != self and isinstance(other, ExpDrop) and not (self.persistent or other.persistent):
                distance = Vector(other.x - self.x, other.y - self.y).magnitude()
                if distance < 5 + self.size + other.size:
                    if self.amount == other.amount:
                        self.amount += other.amount
                        self.amount = self.amount * 1.5
                        self.amount = round(self.amount)
                        self.age = 0
                        drops.remove(other)
        if self.movement.magnitude() > 0.2:
            self.x += self.movement.x
            self.y += self.movement.y
            self.movement.x += random.randint(-20, 20)/100
            self.movement.y += random.randint(-20, 20)/100
            self.drop_friction -= .01
            self.movement = self.movement.normalize()
            self.movement = self.movement.multiply(self.drop_friction)
        else:
            self.movement = Vector(0,0)
    
    def collect(self, player):
        global exp
        if (self.x - player.x) ** 2 + (self.y - player.y) ** 2 < (player.size + player.pickup) ** 2:
            target_vector = Vector(player.x - self.x, player.y - self.y).normalize()
            self.movement = self.movement.add(target_vector.multiply(player.speed * 6))
        if (self.x - player.x) ** 2 + (self.y - player.y) ** 2 < (player.size) ** 2:
            exp += round(self.amount * exp_bonus_multiplier)
            if self in drops:
                drops.remove(self)

class HealthDrop:
    def __init__(self, x, y, amount):
        self.x = x
        self.y = y
        self.amount = amount
        self.movement = Vector(random.uniform(-1, 1), random.uniform(-1, 1)).normalize().multiply(2)
        self.drop_friction = 1
    
    def draw(self, screen):
        pygame.draw.rect(screen, (0, 255, 0), (self.x - self.amount*2, self.y - self.amount*2, self.amount*4, self.amount*4))
    
    def move(self):
        if self.movement.magnitude() > 0.1:
            self.x += self.movement.x
            self.y += self.movement.y
            self.movement.x += random.randint(-20, 20)/100
            self.movement.y += random.randint(-20, 20)/100
            self.drop_friction -= .01
            self.movement = self.movement.normalize()
            self.movement = self.movement.multiply(self.drop_friction)
        else:
            self.movement = Vector(0,0)        
    
    def collect(self, player):
        if (self.x - player.x) ** 2 + (self.y - player.y) ** 2 < (player.size + player.pickup) ** 2:
            target_vector = Vector(player.x - self.x, player.y - self.y).normalize()
            self.movement = self.movement.add(target_vector.multiply(4))
        if (self.x - player.x) ** 2 + (self.y - player.y) ** 2 < (player.size) ** 2:
            player.health = min(player.max_health, player.health + round(player.health*self.amount*.05))
            drops.remove(self)

class MagnetDrop:
    def __init__(self, x, y, amount):
        self.x = x
        self.y = y
        self.amount = amount
        self.movement = Vector(random.uniform(-1, 1), random.uniform(-1, 1)).normalize().multiply(2)
        self.drop_friction = 1
    
    def move(self):
        if self.movement.magnitude() > 0.1:
            self.x += self.movement.x
            self.y += self.movement.y
            self.movement.x += random.randint(-20, 20)/100
            self.movement.y += random.randint(-20, 20)/100
            self.drop_friction -= .01
            self.movement = self.movement.normalize()
            self.movement = self.movement.multiply(self.drop_friction)
        else:
            self.movement = Vector(0,0)   
    
    def draw(self, screen):
        pygame.draw.circle(screen, (0, 255, 255), (int(self.x), int(self.y)), 5)

    def collect(self, player):
        if (self.x - player.x) ** 2 + (self.y - player.y) ** 2 < (player.size + player.pickup) ** 2:
            target_vector = Vector(player.x - self.x, player.y - self.y).normalize()
            self.movement = self.movement.add(target_vector.multiply(4))
        if (self.x - player.x) ** 2 + (self.y - player.y) ** 2 < (player.size) ** 2:
            for drop in drops:
                drop.movement = drop.movement.add(Vector(player.x - drop.x, player.y - drop.y).normalize().multiply(10))
                drop.drop_friction = 5
            drops.remove(self)
