from dataclasses import dataclass

from shared.constants import DEBUG, FPS


@dataclass
class DinoConfig:
    # --- Structural Mapping (Grid Units) ---
    # These represent twelfths of the logical screen (1-12)
    ground_y: int = 10  # Universal floor level for Dino and Ground Obstacles

    # Dino dimensions
    dino_width: int = 2
    dino_height: int = 3
    dino_duck_height: int = 2

    # Cactus dimensions
    # Kept at 1 grid unit so the jump safe-press window exceeds the dino's width, which lets the
    # zone marker be exact: any part of the dino touching the carpet guarantees a clear.
    cactus_width: int = 1.2
    cactus_height: int = 3.2

    # Bird dimensions (spawn height is derived from dino physics - see spawn_bird).
    # Tall enough that its top sits above the jump apex, so a bird can only be ducked, never jumped.
    bird_width: int = 1.8
    bird_height: int = 2.8
    # Cloud dimensions & spawn range
    cloud_width: int = 2
    cloud_height: int = 2
    cloud_y_min: int = 2
    cloud_y_max: int = 5

    # --- Physics & Movement (Logical Pixels) ---
    # These represent actual pixel adjustments per frame on the server
    gravity: float = 0.6
    jump_velocity: int = 24

    game_speed: int = 15  # pixels per frame (constant for the whole run)
    track_y_offset: int = 10  # visual tweak for the drawn track line

    # --- Game Mechanics (Frames & Timers) ---
    # Frame counts derive from FPS so the real-world durations stay correct if the tick rate changes.
    # 1.9s: long enough that the bird safe-press window exceeds the dino width, which keeps the bird
    # carpet touch-exact (any pixel of the dino on the strip clears the bird).
    duck_duration: int = 19 * FPS // 10
    spawn_interval: int = 5 * FPS  # 5 seconds
    max_obstacles: int = 10
    time_limit: int = 180 * FPS  # 3 minutes

    # --- Lives ---
    lives: int = 3  # hits the dino can take before the run ends
    invuln_frames: int = 2 * FPS  # grace period after a hit (2 seconds) - collisions ignored while it lasts

    # --- Scoring ---
    # Score is the survival time in whole seconds. Surviving the full run yields the maximum base
    # score (time_limit in seconds) plus a bonus for each remaining life.
    bonus_per_life: int = 30

    # --- Obstacle generation ---
    # Fixed seed so the obstacle sequence is identical for every competitor. The Jump & Duck variant
    # gets an equal number of jump and duck obstacles in a seeded-random order.
    obstacle_seed: int = 1337

    # --- Visuals & Debugging ---
    show_hitboxes: bool = DEBUG


dino_config = DinoConfig()
