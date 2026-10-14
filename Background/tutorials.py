import math
import pygame
import Background.maps as maps_file
from Background.maps import DEFAULT_LEVEL_END_DELAY_TICKS
import Background.ui_assets as ui_assets
import Enemies.enemies as enemy_file

# Spawn points as fractions of the screen, used for scripted (non-random) enemy placement.
_SPAWN_POINTS = ((0.88, 0.2), (0.88, 0.8), (0.92, 0.5), (0.5, 0.08), (0.5, 0.92))
_COMPLETE_DELAY_TICKS = DEFAULT_LEVEL_END_DELAY_TICKS

def _build_tutorials():
    # Tutorials are map presets whose tutorial flag is active; the map is referenced by file name.
    return [dict(preset.tutorial, map=map_name) for map_name, preset in maps_file.load_tutorial_maps()]


TUTORIALS = _build_tutorials()


class TutorialRun:
    def __init__(self, tutorial):
        self.tutorial = tutorial
        self.ticks = 0
        self.spawn_index = 0
        self.spawned_any = False
        self.complete_ticks = None
        self.completion_delay_ticks = _COMPLETE_DELAY_TICKS
        self.screen_width = ui_assets.Horizontal_Scale * ui_assets.Width
        self.screen_height = ui_assets.Vertical_Scale * ui_assets.Height

    @property
    def complete(self):
        return self.complete_ticks is not None

    @property
    def finished(self):
        return self.complete_ticks is not None and self.complete_ticks >= self.completion_delay_ticks

    def _spawn_enemies(self, count):
        for _ in range(count):
            fx, fy = _SPAWN_POINTS[self.spawn_index % len(_SPAWN_POINTS)]
            self.spawn_index += 1
            enemy_file.Chaser(fx * self.screen_width, fy * self.screen_height, 1)
            self.spawned_any = True

    def update(self, player, end_requested=False, end_delay_ticks=None, runtime=None):
        if self.complete:
            self.complete_ticks += 1
            return

        waves = runtime is not None and runtime.waves_enabled
        if not waves:
            for spawn_tick, count in self.tutorial.get("spawns", []):
                if spawn_tick == self.ticks:
                    self._spawn_enemies(count)
        else:
            self.spawned_any = bool(runtime.wave_groups)
        self.ticks += 1

        goal = self.tutorial["goal"]
        if goal == "reach":
            reached = False
        elif goal == "kill":
            reached = self.spawned_any and not any(enemy.health > 0 for enemy in enemy_file.enemies)
            reached = reached and not (waves and runtime.waves_pending)
        else:
            reached = self.ticks >= self.tutorial["duration"]

        if reached or end_requested:
            if end_requested and end_delay_ticks is not None:
                self.completion_delay_ticks = max(0, int(end_delay_ticks))
            self.complete_ticks = 0
            enemy_file.enemies.clear()
