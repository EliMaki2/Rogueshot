"""Drop-in wave overlay for pygame projects.

Usage:
    overlay = WaveOverlay()
    ...
    overlay.spawn(pos)                      # e.g. on mouse motion
    overlay.update(rocks)                   # once per frame
    overlay.draw(screen)                    # before drawing your own sprites

A "rock" is any object with `position` (x, y) and `radius`. If it also has a
`velocity` (vx, vy), rock-to-rock bounces are resolved and emit waves.
"""

import pygame


def distance(p1, p2):
    return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5


class Wave:
    def __init__(self, center, max_age, parent_rock=None, green=0.0, value=0):
        self.center = center
        self.age = 0
        self.max_age = max_age
        self.parent_rock = parent_rock
        self.green = green
        self.value = value
        self.hit_rocks = set()
        self.crossed = set()


class WaveOverlay:
    def __init__(
        self,
        start_max_age=1000,
        collision_delay=20,
        min_impact_speed=0.5,
        max_wave_value=3,
        max_waves=300,
        spawn_cooldown=0,
    ):
        self.start_max_age = start_max_age
        self.collision_delay = collision_delay
        self.min_impact_speed = min_impact_speed
        self.max_wave_value = max_wave_value
        self.max_waves = max_waves
        self.spawn_cooldown = spawn_cooldown
        self.waves = []
        self._cooldown = 0

    def spawn(self, position, force=False):
        """Create a wave at `position`. Rate-limited unless force=True."""
        if not force and self._cooldown > 0:
            return None
        self._cooldown = self.spawn_cooldown
        wave = Wave(position, self.start_max_age)
        self.waves.append(wave)
        return wave

    def update(self, rocks=()):
        """Advance one frame: age waves, handle collisions, spawn children."""
        if self._cooldown > 0:
            self._cooldown -= 1
        self._update_waves(rocks)
        self._cross_waves()
        self._collide_rocks(rocks)
        del self.waves[: -self.max_waves]

    def draw(self, screen, scale_x=1, scale_y=1):
        """Draw waves onto `screen`. Scales are applied to positions and radii;
        unequal scales turn the rings into ellipses."""
        for wave in self.waves:
            brightness = min(
                255, max(25.5, 255 * (wave.max_age - wave.age) / self.start_max_age)
            )
            color = (
                0,
                int(brightness * wave.green),
                int(brightness * (1 - wave.green)),
            )
            width = round(10 * (wave.age / self.start_max_age)) + 1
            radius = wave.age + 0.1
            cx, cy = wave.center[0] * scale_x, wave.center[1] * scale_y
            rx, ry = radius * scale_x, radius * scale_y
            if scale_x == scale_y:
                pygame.draw.circle(
                    screen, color, (cx, cy), rx, max(1, round(width * scale_x))
                )
            else:
                rect = pygame.Rect(cx - rx, cy - ry, rx * 2, ry * 2)
                pygame.draw.ellipse(
                    screen, color, rect, max(1, round(width * min(scale_x, scale_y)))
                )

    def _update_waves(self, rocks):
        for wave in self.waves[:]:
            if wave.age >= self.collision_delay:
                for rock in rocks:
                    if rock is wave.parent_rock or rock in wave.hit_rocks:
                        continue
                    d = distance(wave.center, rock.position)
                    if d - rock.radius > wave.age:
                        continue
                    wave.hit_rocks.add(rock)
                    remaining = wave.max_age - wave.age
                    if remaining > 0 and d > 0:
                        # Child starts at the point on the rock nearest the parent's center.
                        k = rock.radius / d
                        spot = (
                            rock.position[0] + (wave.center[0] - rock.position[0]) * k,
                            rock.position[1] + (wave.center[1] - rock.position[1]) * k,
                        )
                        self.waves.append(
                            Wave(spot, remaining, rock, min(1.0, wave.green + 0.2))
                        )
                        wave.max_age *= 0.8
            wave.age += 1
            if wave.age > wave.max_age:
                self.waves.remove(wave)

    def _cross_waves(self):
        waves = self.waves
        for i, w1 in enumerate(waves):
            for w2 in waves[i + 1 :]:
                if w2 in w1.crossed:
                    continue
                d = distance(w1.center, w2.center)
                r1, r2 = w1.age, w2.age
                if d == 0 or d > r1 + r2 or d < abs(r1 - r2):
                    continue
                w1.crossed.add(w2)
                w2.crossed.add(w1)
                w1.max_age *= 0.95
                w2.max_age *= 0.95
                child_max_age = min(self.start_max_age, r1 * r2 / 10 - 10)
                child_value = max(w1.value, w2.value) + 1
                if child_max_age <= 0 or child_value > self.max_wave_value:
                    continue
                # One of the two points where the rings intersect.
                along = (r1**2 - r2**2 + d**2) / (2 * d)
                h = max(0, r1**2 - along**2) ** 0.5
                ux = (w2.center[0] - w1.center[0]) / d
                uy = (w2.center[1] - w1.center[1]) / d
                point = (
                    w1.center[0] + ux * along - uy * h,
                    w1.center[1] + uy * along + ux * h,
                )
                child = Wave(point, child_max_age, value=child_value)
                # Children don't cross the waves that made them.
                child.crossed.update((w1, w2))
                w1.crossed.add(child)
                w2.crossed.add(child)
                waves.append(child)

    def _collide_rocks(self, rocks):
        movers = [r for r in rocks if hasattr(r, "velocity")]
        for i, a in enumerate(movers):
            for b in movers[i + 1 :]:
                d = distance(a.position, b.position)
                overlap = a.radius + b.radius - d
                if overlap <= 0 or d == 0:
                    continue
                nx = (b.position[0] - a.position[0]) / d
                ny = (b.position[1] - a.position[1]) / d
                # Move each rock back half the overlap so they only touch.
                a.position = (
                    a.position[0] - nx * overlap / 2,
                    a.position[1] - ny * overlap / 2,
                )
                b.position = (
                    b.position[0] + nx * overlap / 2,
                    b.position[1] + ny * overlap / 2,
                )
                va = a.velocity[0] * nx + a.velocity[1] * ny
                vb = b.velocity[0] * nx + b.velocity[1] * ny
                approach = va - vb
                if approach > 0:
                    # Equal-mass elastic bounce: swap velocity along the contact normal.
                    a.velocity = (
                        a.velocity[0] + (vb - va) * nx,
                        a.velocity[1] + (vb - va) * ny,
                    )
                    b.velocity = (
                        b.velocity[0] + (va - vb) * nx,
                        b.velocity[1] + (va - vb) * ny,
                    )
                    if approach >= self.min_impact_speed:
                        spot = (
                            a.position[0] + nx * a.radius,
                            a.position[1] + ny * a.radius,
                        )
                        self.spawn(spot, force=True)
