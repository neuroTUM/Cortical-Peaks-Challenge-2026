from dataclasses import dataclass


@dataclass
class SkiConfig:
    time_limit: int = 300
    move_speed: float = 6.0
    rotation_speed: float = 4.0

    debug_colliders: bool = True  # enable/disable colliders

    player_radius: int = 80
    obstacle_radius: int = 120
    obstacle_hitbox_width: int = 160
    obstacle_hitbox_height: int = 190
    obstacle_hitbox_offset_y: float = 0.0
    dynamic_obstacle_hitbox_width: int = 240
    dynamic_obstacle_hitbox_height: int = 90
    dynamic_obstacle_hitbox_offset_y: float = 20.0
    goal_radius: int = 40
    goal_distance_grid: float = 40.0

    track_margin_px: float = 5.0
    track_top_margin: float = 200.0
    track_bottom_margin: float = 200.0
    barrier_overlap: int = 12
    barrier_radius: int = 40
    barrier_transparent_padding: int = 30

    obstacle_backsteps: int = 30
    knockback_duration: float = 2.0

    # Track Generation
    obstacle_seed: int = 1337
    # Distance between lanes.
    obstacle_lane_step: float = 1.5
    goal_lane_step: float = 2.0

    # SK2: Dynamic Obstacles
    dynamic_obstacles: bool = True
    obstacle_patrol_speed: float = 0.3  # Speed in grid units per second

    dynamic_track_bounds: float = 4.2  # How far left/right obstacles can go
    dynamic_side_gap: float = 1.5  # Size of the free space for patterns 1 & 2
    dynamic_center_gap: float = 3.5  # Size of the middle free space for pattern 3


ski_config = SkiConfig()
