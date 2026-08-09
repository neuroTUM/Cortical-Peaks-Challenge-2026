from dataclasses import dataclass


@dataclass
class SkiConfig:
    time_limit: int = 300
    move_speed: float = 20.0
    rotation_speed: float = 10.0

    # scoring
    max_score_static: float = 200.0
    max_score_dynamic: float = 250.0
    time_bonus_max_static: float = 50.0
    time_bonus_max_dynamic: float = 100.0
    time_bonus_grace_period: float = 0.0

    debug_colliders: bool = True  # enable/disable colliders

    player_bounding_radius: float = 70.0

    player_box1_width: float = 78.0
    player_box1_height: float = 42.0
    player_box1_offset_x: float = 0.0
    player_box1_offset_y: float = -41.0

    player_box2_width: float = 110.0
    player_box2_height: float = 82.0
    player_box2_offset_x: float = 0.0
    player_box2_offset_y: float = 23.0

    obstacle_radius: int = 120
    goal_radius: int = 40
    goal_distance_grid: float = 20.0

    obstacle_collider_radius: float = 115.0
    obstacle_collider_offset_x: float = 0.0
    obstacle_collider_offset_y: float = 0.0

    dynamic_capsule_p1_x: float = -84.0
    dynamic_capsule_p1_y: float = 17.0
    dynamic_capsule_p2_x: float = 81.0
    dynamic_capsule_p2_y: float = 17.0
    dynamic_capsule_radius: float = 22.0

    dynamic_sphere_offset_x: float = 0.0
    dynamic_sphere_offset_y: float = -22.0
    dynamic_sphere_radius: float = 64.0

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
