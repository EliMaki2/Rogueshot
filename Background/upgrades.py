import inspect
import pygame
import random

luck = 1

class Upgrade:
    def __init__(self, name = "", description = "", stat = None, amount = 0, minimum=0, luck=0):
        self.name = name
        self.description = description
        self.stat = stat
        self.base = amount
        self.amount = amount
        self.luck = luck    
        self.color = (200, 200, 200)
        self.minimum = minimum
        self.strength = 1
    
    def randomize_strength(self, luck):
        temp = random.randint(0, 100)
        temp += luck
        if temp < 70:
            self.strength = 1
        elif temp < 85:
            self.strength = 2
        elif temp < 95:
            self.strength = 3
        elif temp < 98:
            self.strength = 4
        else:
            self.strength = 5
        self.color = self.strength_to_color()
        self.amount = self.raise_amount()

    def strength_to_color(self):
        if self.strength == 1:
            return (200, 200, 200)
        elif self.strength == 2:
            return (150, 250, 150)
        elif self.strength == 3:
            return (150, 150, 250)
        elif self.strength == 4:
            return (250, 150, 150)
        elif self.strength == 5:
            return (250, 200, 100)
    
    def raise_amount(self):
        if self.strength == 1:
            return self.base
        elif self.strength == 2:
            return self.base * 2
        elif self.strength == 3:
            return self.base * 3
        elif self.strength == 4:
            return self.base * 7
        elif self.strength == 5:
            return self.base * 10
    
    def apply(self, player):
        global luck
        if self.strength > 2 and luck < 80:
            luck += 1
        # List of all possible upgradable stats on PlayerBody
        upgradable_stats = [
            "health", "max_health", "attack_speed", "attack_spread", "multishot", "pierce", "attack_range", "damage", "bullet_color", "knockback", "bullet_speed", "pickup", "speed"
        ]
        if self.stat == "health":
            player.max_health += self.amount
            player.health += self.amount
        elif hasattr(player, self.stat):
            setattr(player, self.stat, getattr(player, self.stat) + self.amount)
        else:
            # fallback: try to set on gun if stat is not on player
            if hasattr(player, "gun") and hasattr(player.gun, self.stat):
                setattr(player.gun, self.stat, getattr(player.gun, self.stat) + self.amount)
        # Optionally, you can print/log for debugging
        # print(f"Applied upgrade: {self.stat} +{self.amount}")
    

total_Upgrades = [
    Upgrade("Sharp Bullets", "Increases bullet damage", "damage", 1),
    Upgrade("Fast Reload", "Decreases time\nbetween shots", "attack_speed", -0.1),
    Upgrade("High Velocity", "Increases bullet pierce", "pierce", 1, 2),
    Upgrade("Long Sights", "Increases bullet range", "attack_range", 4),
    Upgrade("Quick Feet", "Increases player speed", "speed", 0.05),
    Upgrade("Extra Barrel", "Add more bullets per shot", "multishot", 1, 3),
    Upgrade("Tough Skin", "Increases max health", "health", 5),
    Upgrade("Pocket Magnets", "Increases pickup range", "pickup", 20),
    Upgrade("Lead Tips", "Increases knockback", "knockback", .1, 2)
]