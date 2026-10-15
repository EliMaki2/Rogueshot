import pygame

walls = []


class Wall:
    def __init__(self, x, y, width, height, enabled=True, goal_linked=False):
        self.enabled = enabled
        self.goal_linked = goal_linked
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def to_dict(self):
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "enabled": self.enabled,
            "goal_linked": self.goal_linked,
        }

    def contains_point(self, px, py, padding=0):
        return self.enabled and (
            self.x - padding <= px <= self.x + self.width + padding
            and self.y - padding <= py <= self.y + self.height + padding
        )

    def intersects_segment(self, x1, y1, x2, y2, padding=0):
        if not self.enabled:
            return False
        # Liang-Barsky clip of the segment against the padded rectangle.
        left, right = self.x - padding, self.x + self.width + padding
        top, bottom = self.y - padding, self.y + self.height + padding
        dx, dy = x2 - x1, y2 - y1
        t0, t1 = 0.0, 1.0
        for p, q in (
            (-dx, x1 - left),
            (dx, right - x1),
            (-dy, y1 - top),
            (dy, bottom - y1),
        ):
            if p == 0:
                if q < 0:
                    return False
                continue
            t = q / p
            if p < 0:
                if t > t1:
                    return False
                t0 = max(t0, t)
            else:
                if t < t0:
                    return False
                t1 = min(t1, t)
        return True

    def push_out(self, entity):
        """Move a circular entity out of this wall."""
        if not self.enabled:
            return
        radius = entity.size
        nearest_x = min(max(entity.x, self.x), self.x + self.width)
        nearest_y = min(max(entity.y, self.y), self.y + self.height)
        dx, dy = entity.x - nearest_x, entity.y - nearest_y
        dist_sq = dx * dx + dy * dy
        if dist_sq >= radius * radius:
            return
        if dist_sq > 0:
            dist = dist_sq**0.5
            entity.x = nearest_x + dx / dist * radius
            entity.y = nearest_y + dy / dist * radius
            return
        # Centre is inside the wall: exit through the closest face.
        gaps = (
            (entity.x - self.x, -1, 0),
            (self.x + self.width - entity.x, 1, 0),
            (entity.y - self.y, 0, -1),
            (self.y + self.height - entity.y, 0, 1),
        )
        gap, nx, ny = min(gaps, key=lambda g: g[0])
        entity.x += nx * (gap + radius)
        entity.y += ny * (gap + radius)

    def draw(self, screen):
        rect = pygame.Rect(int(self.x), int(self.y), int(self.width), int(self.height))
        if not self.enabled:
            pygame.draw.rect(screen, (60, 130, 100), rect, 1)
            return
        pygame.draw.rect(screen, (70, 75, 95), rect)
        pygame.draw.rect(screen, (170, 175, 200), rect, 2)


def _closest_on_segment(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    t = (
        0.0
        if length_sq == 0
        else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    )
    return ax + dx * t, ay + dy * t


def _segments_cross(p1, p2, p3, p4):
    def side(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    return (
        side(p1, p2, p3) * side(p1, p2, p4) < 0
        and side(p3, p4, p1) * side(p3, p4, p2) < 0
    )


class CircleWall:
    """Round wall. Exposes x/y/width/height as its bounding box for code that treats walls as rectangles."""

    def __init__(self, cx, cy, radius, enabled=True, goal_linked=False):
        self.enabled = enabled
        self.goal_linked = goal_linked
        self.cx, self.cy, self.radius = cx, cy, radius

    @property
    def x(self):
        return self.cx - self.radius

    @property
    def y(self):
        return self.cy - self.radius

    @property
    def width(self):
        return self.radius * 2

    @property
    def height(self):
        return self.radius * 2

    def to_dict(self):
        return {
            "kind": "circle",
            "cx": self.cx,
            "cy": self.cy,
            "radius": self.radius,
            "enabled": self.enabled,
            "goal_linked": self.goal_linked,
        }

    def contains_point(self, px, py, padding=0):
        return (
            self.enabled
            and (px - self.cx) ** 2 + (py - self.cy) ** 2
            <= (self.radius + padding) ** 2
        )

    def intersects_segment(self, x1, y1, x2, y2, padding=0):
        if not self.enabled:
            return False
        nx, ny = _closest_on_segment(self.cx, self.cy, x1, y1, x2, y2)
        return (nx - self.cx) ** 2 + (ny - self.cy) ** 2 <= (self.radius + padding) ** 2

    def push_out(self, entity):
        if not self.enabled:
            return
        reach = self.radius + entity.size
        dx, dy = entity.x - self.cx, entity.y - self.cy
        dist_sq = dx * dx + dy * dy
        if dist_sq >= reach * reach:
            return
        if dist_sq == 0:
            dx, dy, dist = 1.0, 0.0, 1.0
        else:
            dist = dist_sq**0.5
        entity.x = self.cx + dx / dist * reach
        entity.y = self.cy + dy / dist * reach

    def draw(self, screen):
        center = (int(self.cx), int(self.cy))
        if not self.enabled:
            pygame.draw.circle(screen, (60, 130, 100), center, int(self.radius), 1)
            return
        pygame.draw.circle(screen, (70, 75, 95), center, int(self.radius))
        pygame.draw.circle(screen, (170, 175, 200), center, int(self.radius), 2)


class TriangleWall:
    def __init__(self, points, enabled=True, goal_linked=False):
        if len(points) != 3:
            raise ValueError("a triangle wall needs exactly three points")
        self.enabled = enabled
        self.goal_linked = goal_linked
        self.points = [(float(px), float(py)) for px, py in points]

    @property
    def x(self):
        return min(p[0] for p in self.points)

    @property
    def y(self):
        return min(p[1] for p in self.points)

    @property
    def width(self):
        return max(p[0] for p in self.points) - self.x

    @property
    def height(self):
        return max(p[1] for p in self.points) - self.y

    def to_dict(self):
        return {
            "kind": "triangle",
            "points": [list(p) for p in self.points],
            "enabled": self.enabled,
            "goal_linked": self.goal_linked,
        }

    def _edges(self):
        a, b, c = self.points
        return ((a, b), (b, c), (c, a))

    def _inside(self, px, py):
        signs = []
        for (ax, ay), (bx, by) in self._edges():
            signs.append((bx - ax) * (py - ay) - (by - ay) * (px - ax))
        return all(s >= 0 for s in signs) or all(s <= 0 for s in signs)

    def _nearest_boundary(self, px, py):
        best = None
        for (ax, ay), (bx, by) in self._edges():
            nx, ny = _closest_on_segment(px, py, ax, ay, bx, by)
            dist_sq = (nx - px) ** 2 + (ny - py) ** 2
            if best is None or dist_sq < best[0]:
                best = (dist_sq, nx, ny)
        return best

    def contains_point(self, px, py, padding=0):
        if not self.enabled:
            return False
        if self._inside(px, py):
            return True
        return padding > 0 and self._nearest_boundary(px, py)[0] <= padding * padding

    def intersects_segment(self, x1, y1, x2, y2, padding=0):
        if not self.enabled:
            return False
        if self.contains_point(x1, y1, padding) or self.contains_point(x2, y2, padding):
            return True
        for a, b in self._edges():
            if _segments_cross((x1, y1), (x2, y2), a, b):
                return True
            if padding > 0:
                for px, py in ((x1, y1), (x2, y2)):
                    nx, ny = _closest_on_segment(px, py, a[0], a[1], b[0], b[1])
                    if (nx - px) ** 2 + (ny - py) ** 2 <= padding * padding:
                        return True
                for px, py in (a, b):
                    nx, ny = _closest_on_segment(px, py, x1, y1, x2, y2)
                    if (nx - px) ** 2 + (ny - py) ** 2 <= padding * padding:
                        return True
        return False

    def push_out(self, entity):
        if not self.enabled:
            return
        radius = entity.size
        dist_sq, nx, ny = self._nearest_boundary(entity.x, entity.y)
        inside = self._inside(entity.x, entity.y)
        if not inside and dist_sq >= radius * radius:
            return
        dist = dist_sq**0.5
        if dist == 0:
            # Centre lies on an edge; leave away from the triangle's centroid.
            cx = sum(p[0] for p in self.points) / 3
            cy = sum(p[1] for p in self.points) / 3
            dx, dy = nx - cx, ny - cy
            length = (dx * dx + dy * dy) ** 0.5 or 1.0
            entity.x = nx + dx / length * radius
            entity.y = ny + dy / length * radius
            return
        sign = 1 if inside else -1
        entity.x = nx + sign * (nx - entity.x) / dist * radius
        entity.y = ny + sign * (ny - entity.y) / dist * radius

    def draw(self, screen):
        points = [(int(px), int(py)) for px, py in self.points]
        if not self.enabled:
            pygame.draw.polygon(screen, (60, 130, 100), points, 1)
            return
        pygame.draw.polygon(screen, (70, 75, 95), points)
        pygame.draw.polygon(screen, (170, 175, 200), points, 2)


def set_walls(wall_list):
    walls.clear()
    walls.extend(wall_list)


def create_plus_walls(center_x, center_y, arm_length=140, thickness=30, gap=60):
    """Four rectangular walls forming a plus with an open centre of `gap` size."""
    half_gap = gap / 2
    return [
        Wall(
            center_x - thickness / 2,
            center_y - half_gap - arm_length,
            thickness,
            arm_length,
        ),
        Wall(center_x - thickness / 2, center_y + half_gap, thickness, arm_length),
        Wall(
            center_x - half_gap - arm_length,
            center_y - thickness / 2,
            arm_length,
            thickness,
        ),
        Wall(center_x + half_gap, center_y - thickness / 2, arm_length, thickness),
    ]


def walls_to_list():
    return [wall.to_dict() for wall in walls]


def walls_from_list(data):
    loaded = []
    if isinstance(data, list):
        for item in data:
            try:
                kind = item.get("kind")
                if kind == "circle":
                    loaded.append(
                        CircleWall(
                            float(item["cx"]),
                            float(item["cy"]),
                            float(item["radius"]),
                            bool(item.get("enabled", True)),
                            bool(item.get("goal_linked", False)),
                        )
                    )
                    continue
                if kind == "triangle":
                    loaded.append(
                        TriangleWall(
                            item["points"],
                            bool(item.get("enabled", True)),
                            bool(item.get("goal_linked", False)),
                        )
                    )
                    continue
                loaded.append(
                    Wall(
                        float(item["x"]),
                        float(item["y"]),
                        float(item["width"]),
                        float(item["height"]),
                        bool(item.get("enabled", True)),
                        bool(item.get("goal_linked", False)),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
    return loaded


def push_out_of_walls(entity):
    for wall in walls:
        wall.push_out(entity)


def point_in_wall(x, y, padding=0):
    return any(wall.contains_point(x, y, padding) for wall in walls)


def segment_hits_wall(x1, y1, x2, y2, padding=0):
    return any(wall.intersects_segment(x1, y1, x2, y2, padding) for wall in walls)


def bounce_off_walls(bullet, old_x, old_y):
    """Reflect a bullet off any wall it crossed this frame. Returns False if it can't bounce."""
    if not segment_hits_wall(old_x, old_y, bullet.x, bullet.y, bullet.size):
        return True
    if point_in_wall(old_x, old_y, bullet.size):
        return False
    new_x, new_y = bullet.x, bullet.y
    hit_x = segment_hits_wall(old_x, old_y, new_x, old_y, bullet.size)
    hit_y = segment_hits_wall(old_x, old_y, old_x, new_y, bullet.size)
    if not hit_x and not hit_y:
        hit_x = hit_y = True
    bullet.x, bullet.y = old_x, old_y
    if hit_x:
        bullet.velocity.x *= -0.5
    if hit_y:
        bullet.velocity.y *= -0.5
    bullet.speed *= 0.7
    return True


def draw_walls(screen):
    for wall in walls:
        wall.draw(screen)
