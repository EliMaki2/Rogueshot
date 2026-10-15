"""Runtime for editor-format map objects: walls, triggers, spawners, kill zones, text and logic gates.

Objects are the dicts stored by the map editor (coordinates in the 1000x625 editor space). Sources
(triggers, enemy spawn points, gates) expose an on/off signal; whatever they list in "targets" is
driven by it:
  walls, spawn zones, kill zones   active only while a linked source is on (always active if unlinked)
  enemy spawn points               spawn their enemy once a linked source is on (at start if unlinked)
  gates                            combine their linked inputs
  level end                        ends the tutorial while a linked source is on
  wave / level triggers            on once the chosen tutorial wave is beaten / the player reaches the chosen level
  exp spawners                     drop permanent exp orbs once a linked source is on (at start if unlinked)
"""
import math
import random
import pygame
import Background.walls as walls_file
import Enemies.drops as drops_file
from Background.maps import DEFAULT_LEVEL_END_DELAY_TICKS, GATE_TYPES

TRIGGER_TYPES = ("trig_move", "trig_attack", "trig_ability")
WAVE_GAP_TICKS = 60
TRIGGER_COLORS = {
    "trig_move": ((30, 110, 70), (60, 200, 120)),
    "trig_attack": ((120, 45, 40), (240, 100, 80)),
    "trig_ability": ((80, 50, 130), (170, 120, 255)),
}
_fonts = {}


def _font(size):
    size = max(8, int(size))
    if size not in _fonts:
        _fonts[size] = pygame.font.SysFont(None, size)
    return _fonts[size]


def evaluate_gate(kind, inputs):
    """Output of a logic gate for a list of boolean inputs (no inputs -> off, except inverting gates -> on)."""
    inputs = list(inputs)
    if kind == "AND":
        return bool(inputs) and all(inputs)
    if kind == "OR":
        return any(inputs)
    if kind in ("NOT", "NOR"):
        return not any(inputs)
    if kind == "NAND":
        return not (bool(inputs) and all(inputs))
    if kind == "XOR":
        return sum(inputs) % 2 == 1
    if kind == "XNOR":
        return sum(inputs) % 2 == 0
    return False


class MapRuntime:
    def __init__(self, preset, h_scale, v_scale, create_enemy, create_wave_enemy=None):
        self.h, self.v = h_scale, v_scale
        self.create_enemy = create_enemy
        self.create_wave_enemy = create_wave_enemy or create_enemy
        tutorial = preset.tutorial if preset.tutorial.get("active") else {}
        self.waves = list(tutorial.get("waves", [])) if tutorial.get("waves_enabled") else []
        self.waves_enabled = bool(self.waves)
        self.wave_groups = []
        self.waves_beaten = set()
        self.wave_spawn_tick = None
        self.level = 1
        self.objects = {o["id"]: o for o in preset.objects}
        self.incoming = {oid: [] for oid in self.objects}
        for obj in preset.objects:
            for target in obj["targets"]:
                if target in self.incoming:
                    self.incoming[target].append(obj["id"])
        self.signal = {oid: False for oid in self.objects}
        self.state = {}
        self.enemies = {}
        self.walls = {}
        self.end_requested = False
        self.end_delay_ticks = DEFAULT_LEVEL_END_DELAY_TICKS
        self.tick = 0
        for oid, obj in self.objects.items():
            self._init_object(oid, obj)
        self._apply_walls()

    # ---- setup ----
    def _init_object(self, oid, obj):
        kind = obj["type"]
        if kind in TRIGGER_TYPES:
            fulfilled = bool(obj.get("fulfilled", False))
            pulse = max(1, int(obj.get("pulse_ticks", 30))) if fulfilled and obj.get("mode") == "pulse" else 0
            self.state[oid] = {"progress": 0, "fulfilled": fulfilled, "pulse": pulse, "inside": False, "seen": set()}
            self.signal[oid] = fulfilled
        elif kind == "spawn_point":
            self.state[oid] = {"was_on": False, "killed": False, "pulse": 0}
        elif kind == "spawn_zone":
            self.state[oid] = {"was_on": False}
        elif kind == "gate":
            self.state[oid] = {}
        elif kind in ("wave_trigger", "level_trigger"):
            self.state[oid] = {"fulfilled": False}
        elif kind == "exp_spawner":
            self.state[oid] = {"was_on": False}
        h, v = self.h, self.v
        linked = bool(self.incoming[oid])
        if kind == "wall_rect":
            width, height = (obj["x2"] - obj["x1"]) * h, (obj["y2"] - obj["y1"]) * v
            self.walls[oid] = walls_file.Wall(obj["x1"] * h, obj["y1"] * v, width, height, not linked, linked)
        elif kind == "wall_circle":
            self.walls[oid] = walls_file.CircleWall(obj["x"] * h, obj["y"] * v, obj["r"] * h, not linked, linked)
        elif kind == "wall_tri":
            points = [(p[0] * h, p[1] * v) for p in obj["pts"]]
            self.walls[oid] = walls_file.TriangleWall(points, not linked, linked)

    def install_walls(self):
        walls_file.set_walls(list(self.walls.values()))

    # ---- queries ----
    def input_active(self, oid):
        """True/False from linked sources, or None if nothing is linked."""
        sources = self.incoming[oid]
        if not sources:
            return None
        return any(self.signal[s] for s in sources)

    def is_enabled(self, oid):
        active = self.input_active(oid)
        return True if active is None else active

    def of_type(self, kind):
        return [(oid, o) for oid, o in self.objects.items() if o["type"] == kind]

    @property
    def waves_pending(self):
        """True while tutorial waves are still to be spawned or beaten."""
        return self.waves_enabled and (len(self.wave_groups) < len(self.waves) or len(self.waves_beaten) < len(self.wave_groups))

    def active_spawn_zones(self):
        """Enabled spawn zones as editor-space Walls (unscaled)."""
        zones = []
        for oid, o in self.of_type("spawn_zone"):
            if self.is_enabled(oid):
                zones.append(walls_file.Wall(o["x1"], o["y1"], o["x2"] - o["x1"], o["y2"] - o["y1"]))
        return zones

    # ---- per-tick update ----
    def update(self, player, bullets, enemies, ability_used=False, level=1):
        self.tick += 1
        self.level = level
        self._update_triggers(player, bullets, ability_used)
        self._update_waves(enemies)
        self._update_spawn_points(enemies)
        self._update_exp_spawners()
        self._update_progress_triggers()
        self._update_gates()
        self._apply_walls()
        self._update_kill_zones(enemies)
        active_ends = [
            max(0, int(obj.get("delay_ticks", DEFAULT_LEVEL_END_DELAY_TICKS)))
            for oid, obj in self.of_type("level_end")
            if self.input_active(oid)
        ]
        self.end_requested = bool(active_ends)
        self.end_delay_ticks = min(active_ends, default=DEFAULT_LEVEL_END_DELAY_TICKS)

    def _update_triggers(self, player, bullets, ability_used):
        for oid, o in self.of_type_set(TRIGGER_TYPES):
            st = self.state[oid]
            cx, cy, radius = o["x"] * self.h, o["y"] * self.v, o["r"] * self.h
            kind = o["type"]
            required = 1 if kind == "trig_move" else max(1, int(o.get("count", 1)))
            events = 0
            if not self.is_enabled(oid):
                # Triggers fed by other objects ignore the player until they are enabled.
                st["inside"] = False
                st["seen"] = set()
            elif kind == "trig_move":
                inside = math.hypot(player.x - cx, player.y - cy) <= radius + player.size
                events = 1 if inside and not st["inside"] else 0
                st["inside"] = inside
            elif kind == "trig_attack":
                hits = {id(b) for b in bullets if math.hypot(b.x - cx, b.y - cy) <= radius + b.size}
                events = len(hits - st["seen"])
                st["seen"] = hits
            elif ability_used and math.hypot(player.x - cx, player.y - cy) <= radius + player.size:
                events = 1
            st["progress"] += events
            if o.get("mode") == "pulse":
                if st["progress"] >= required:
                    st["pulse"] = max(1, int(o.get("pulse_ticks", 30)))
                    st["progress"] = 0
                self.signal[oid] = st["pulse"] > 0
                st["fulfilled"] = self.signal[oid]
                if st["pulse"] > 0:
                    st["pulse"] -= 1
            else:
                if st["progress"] >= required:
                    st["fulfilled"] = True
                self.signal[oid] = st["fulfilled"]

    def of_type_set(self, kinds):
        return [(oid, o) for oid, o in self.objects.items() if o["type"] in kinds]

    def _update_waves(self, enemies):
        if not self.waves_enabled:
            return
        for index, group in enumerate(self.wave_groups):
            if index not in self.waves_beaten and all(e.health <= 0 or e not in enemies for e in group):
                self.waves_beaten.add(index)
        zones = [(oid, o) for oid, o in self.of_type("spawn_zone") if o.get("wave_mode")]
        if zones:
            # Wave-mode zones spawn the next wave on each rising edge of their input signal.
            for oid, o in zones:
                st = self.state[oid]
                active = self.is_enabled(oid)
                if active and not st["was_on"] and len(self.wave_groups) < len(self.waves):
                    self._spawn_wave(len(self.wave_groups), o)
                st["was_on"] = active
            return
        index = len(self.wave_groups)
        if index >= len(self.waves) or (index > 0 and index - 1 not in self.waves_beaten):
            return
        if self.wave_spawn_tick is None:
            self.wave_spawn_tick = self.tick + (WAVE_GAP_TICKS if index else 0)
        if self.tick >= self.wave_spawn_tick:
            self.wave_spawn_tick = None
            self._spawn_wave(index)

    def _spawn_wave(self, index, zone=None):
        def position():
            if zone is None:
                return None
            return (random.uniform(zone["x1"], zone["x2"]) * self.h, random.uniform(zone["y1"], zone["y2"]) * self.v)

        self.wave_groups.append([
            self.create_wave_enemy(name, 100, position())
            for name, count in self.waves[index].items() for _ in range(count)
        ])
    def _update_progress_triggers(self):
        for oid, o in self.of_type("wave_trigger"):
            st = self.state[oid]
            wave = max(1, int(o.get("wave", 1))) - 1
            st["fulfilled"] = st["fulfilled"] or wave in self.waves_beaten
            self.signal[oid] = st["fulfilled"]
        for oid, o in self.of_type("level_trigger"):
            st = self.state[oid]
            st["fulfilled"] = st["fulfilled"] or self.level >= max(1, int(o.get("level", 2)))
            self.signal[oid] = st["fulfilled"]

    def _update_exp_spawners(self):
        for oid, o in self.of_type("exp_spawner"):
            st = self.state[oid]
            active = self.is_enabled(oid)
            rising = active and not st["was_on"]
            st["was_on"] = active
            if not rising:
                continue
            for _ in range(max(1, int(o.get("count", 1)))):
                drop = drops_file.ExpDrop(o["x"] * self.h, o["y"] * self.v, max(1, int(o.get("amount", 5))))
                drop.persistent = True
                drops_file.drops.append(drop)

    def _update_spawn_points(self, enemies):
        for oid, o in self.of_type("spawn_point"):
            st = self.state[oid]
            active = self.is_enabled(oid)
            # Spawn on every rising edge of the input signal (at start if unlinked).
            if active and not st["was_on"]:
                self.enemies.setdefault(oid, []).append(
                    self.create_enemy(o.get("enemy", "Chaser"), 100, (o["x"] * self.h, o["y"] * self.v)))
            st["was_on"] = active
            alive = []
            for enemy in self.enemies.get(oid, []):
                if enemy.health <= 0 or enemy not in enemies:
                    st["killed"] = True
                    if o.get("mode") == "pulse":
                        st["pulse"] = max(1, int(o.get("pulse_ticks", 30)))
                else:
                    alive.append(enemy)
            self.enemies[oid] = alive
            if o.get("mode") == "pulse":
                self.signal[oid] = st["pulse"] > 0
                if st["pulse"] > 0:
                    st["pulse"] -= 1
            else:
                self.signal[oid] = st["killed"]

    def _update_gates(self):
        gates = self.of_type("gate")
        # Gates can feed each other; settle them from last tick's values (loops just lag a tick).
        for _ in range(len(gates) + 1):
            changed = False
            for oid, o in gates:
                kind = o.get("gate") if o.get("gate") in GATE_TYPES else "AND"
                value = evaluate_gate(kind, (self.signal[s] for s in self.incoming[oid]))
                if value != self.signal[oid]:
                    self.signal[oid] = value
                    changed = True
            if not changed:
                break

    def _apply_walls(self):
        for oid, wall in self.walls.items():
            wall.enabled = self.is_enabled(oid)

    def _update_kill_zones(self, enemies):
        for oid, o in self.of_type("kill_zone"):
            if not self.is_enabled(oid):
                continue
            left, right = o["x1"] * self.h, o["x2"] * self.h
            top, bottom = o["y1"] * self.v, o["y2"] * self.v
            for enemy in list(enemies):
                if left <= enemy.x <= right and top <= enemy.y <= bottom:
                    enemy.health = 0
                    if enemy in enemies:
                        enemies.remove(enemy)

    # ---- drawing ----
    def draw(self, screen, tick):
        pulse = 1 + 0.08 * math.sin(tick / 10)
        for oid, o in self.of_type_set(TRIGGER_TYPES):
            st = self.state[oid]
            latched_done = o.get("mode") != "pulse" and st["fulfilled"]
            if latched_done or not self.is_enabled(oid):
                continue
            fill, edge = TRIGGER_COLORS[o["type"]]
            center = (o["x"] * self.h, o["y"] * self.v)
            radius = o["r"] * self.h
            if self.signal[oid]:
                pygame.draw.circle(screen, edge, center, radius, 0)
            else:
                pygame.draw.circle(screen, edge, center, radius * pulse, 4)
                pygame.draw.circle(screen, fill, center, radius * 0.6)
            required = int(o.get("count", 1)) if o["type"] != "trig_move" else 1
            if required > 1:
                label = _font(24 * self.v).render(f"{st['progress']}/{required}", True, (240, 240, 240))
                screen.blit(label, label.get_rect(center=center))
        for oid, o in self.of_type("kill_zone"):
            if not self.is_enabled(oid):
                continue
            left, top = o["x1"] * self.h, o["y1"] * self.v
            rect = pygame.Rect(left, top, (o["x2"] - o["x1"]) * self.h, (o["y2"] - o["y1"]) * self.v)
            color = (200, 80, 255)
            pygame.draw.rect(screen, color, rect, 2)
            pygame.draw.line(screen, color, rect.topleft, rect.bottomright, 1)
            pygame.draw.line(screen, color, rect.topright, rect.bottomleft, 1)
        for oid, o in self.of_type("text"):
            if not self.is_enabled(oid):
                continue
            image = _font(o.get("size", 28) * self.v).render(str(o.get("text", "")), True, (230, 230, 230))
            screen.blit(image, image.get_rect(center=(o["x"] * self.h, o["y"] * self.v)))

    # ---- suspend / resume ----
    def snapshot(self):
        data = {}
        for oid, st in self.state.items():
            entry = {k: v for k, v in st.items() if k != "seen"}
            entry["signal"] = self.signal[oid]
            data[str(oid)] = entry
        return data

    def restore(self, data):
        if not isinstance(data, dict):
            return
        for key, entry in data.items():
            try:
                oid = int(key)
            except (TypeError, ValueError):
                continue
            st = self.state.get(oid)
            if st is None or not isinstance(entry, dict):
                continue
            for field in ("progress", "fulfilled", "pulse", "inside", "killed"):
                if field in entry and field in st:
                    st[field] = entry[field]
            if "signal" in entry:
                self.signal[oid] = bool(entry["signal"])
            if "was_on" in st and "killed" in st:
                # Enemies aren't saved, so an unkilled spawn point places its enemy again.
                st["was_on"] = bool(st.get("killed"))
            elif "was_on" in st:
                st["was_on"] = False
        self._apply_walls()
