from __future__ import annotations

import random
import struct
from dataclasses import dataclass

from games.ski.config import ski_config
from shared.ui import Grid

# Wire format: username (16s), time_left(f), countdown(f), is_paused(B),
# player_x(f), player_y(f), player_angle(f), start_x(f), start_y(f),
# goal_x(f), goal_y(f), score(f), reached_goal(B), is_moving(B),
# knockback_timer(f), knockback_dx(f), knockback_dy(f), obs_count(H)
_FMT_GAME_HEADER = "!16sffBffffffffBBfffH"
_GAME_HEADER_SIZE = struct.calcsize(_FMT_GAME_HEADER)

# Obstacle format: x(f), y(f), min_x(f), max_x(f), speed(f), direction(f)
_FMT_OBSTACLE = "!ffffff"
_OBSTACLE_SIZE = struct.calcsize(_FMT_OBSTACLE)


@dataclass
class ObstacleState:
    x: float
    y: float
    min_x: float = 0.0
    max_x: float = 0.0
    speed: float = 0.0
    direction: float = 1.0


@dataclass
class SkiState:
    username: str
    time_left: float
    countdown: float
    is_paused: bool

    x: float
    y: float
    angle: float
    start_x: float
    start_y: float
    goal_x: float
    goal_y: float
    score: float
    reached_goal: bool
    is_moving: bool

    knockback_timer: float
    knockback_dx: float
    knockback_dy: float

    obstacles: list[ObstacleState]
    game_over: bool = False

    @property
    def current_time_bonus(self) -> float:
        time_spent = ski_config.time_limit - self.time_left

        is_dynamic = any(obs.speed > 0 for obs in self.obstacles)
        max_bonus = ski_config.time_bonus_max_dynamic if is_dynamic else ski_config.time_bonus_max_static

        if time_spent <= ski_config.time_bonus_grace_period:
            return float(max_bonus)

        time_over_grace = time_spent - ski_config.time_bonus_grace_period
        time_allowed_to_decay = ski_config.time_limit - ski_config.time_bonus_grace_period

        decay_ratio = 1.0 - (time_over_grace / max(1.0, time_allowed_to_decay))
        return max(0.0, max_bonus * decay_ratio)


class _SkiStateAdapter:
    @staticmethod
    def dump_bytes(state: SkiState) -> bytes:
        header = struct.pack(
            _FMT_GAME_HEADER,
            state.username.encode("utf-8")[:16].ljust(16, b"\x00"),
            state.time_left,
            state.countdown,
            int(state.is_paused),
            state.x,
            state.y,
            state.angle,
            state.start_x,
            state.start_y,
            state.goal_x,
            state.goal_y,
            state.score,
            int(state.reached_goal),
            int(state.is_moving),
            state.knockback_timer,
            state.knockback_dx,
            state.knockback_dy,
            len(state.obstacles),
        )
        obs_bytes = b"".join(
            struct.pack(_FMT_OBSTACLE, o.x, o.y, o.min_x, o.max_x, o.speed, o.direction) for o in state.obstacles
        )
        return header + obs_bytes

    @staticmethod
    def validate_bytes(data: bytes) -> SkiState:
        (
            username_b,
            time_left,
            countdown,
            is_paused_b,
            x,
            y,
            angle,
            start_x,
            start_y,
            goal_x,
            goal_y,
            score,
            reached_goal_b,
            is_moving_b,
            k_timer,
            k_dx,
            k_dy,
            obs_count,
        ) = struct.unpack_from(_FMT_GAME_HEADER, data, 0)

        obstacles = []
        off = _GAME_HEADER_SIZE
        for _ in range(obs_count):
            ox, oy, omin, omax, ospeed, odir = struct.unpack_from(_FMT_OBSTACLE, data, off)
            obstacles.append(ObstacleState(x=ox, y=oy, min_x=omin, max_x=omax, speed=ospeed, direction=odir))
            off += _OBSTACLE_SIZE

        return SkiState(
            username=username_b.rstrip(b"\x00").decode("utf-8"),
            time_left=time_left,
            countdown=countdown,
            is_paused=bool(is_paused_b),
            x=x,
            y=y,
            angle=angle,
            start_x=start_x,
            start_y=start_y,
            goal_x=goal_x,
            goal_y=goal_y,
            score=score,
            knockback_timer=k_timer,
            knockback_dx=k_dx,
            knockback_dy=k_dy,
            obstacles=obstacles,
            reached_goal=bool(reached_goal_b),
            is_moving=bool(is_moving_b),
        )


SkiStateAdapter = _SkiStateAdapter()


def generate_track_plan(
    seed: int,
    start_col: float,
    start_y: float,
    goal_y: float,
    dynamic: bool,  # noqa: FBT001
) -> tuple[float, float, list[ObstacleState]]:
    rng = random.Random(seed)
    track_length = start_y - goal_y
    lanes = [-2, -1, 0, 1, 2]

    goal_lane = rng.choice(lanes)
    goal_x = Grid.x(start_col + ski_config.goal_lane_step * goal_lane)

    obstacles = []
    percentages = [0.25, 0.50, 0.75]

    if not dynamic:
        obs_lanes = [rng.choice(lanes) for _ in range(3)]
        if goal_lane == 0 and 0 not in obs_lanes:
            obs_lanes[rng.randrange(3)] = 0

        for percent, lane in zip(percentages, obs_lanes, strict=True):
            obs_x = Grid.x(start_col + ski_config.obstacle_lane_step * lane)
            obs_y = start_y - (track_length * percent)
            obstacles.append(ObstacleState(x=obs_x, y=obs_y))
    else:
        types = [rng.choice([1, 2, 3]) for _ in range(3)]
        if goal_lane == 0 and all(t == 3 for t in types):
            types[rng.randrange(3)] = rng.choice([1, 2])

        speed_px = Grid.x(ski_config.obstacle_patrol_speed)
        bounds = ski_config.dynamic_track_bounds
        side_gap = ski_config.dynamic_side_gap
        center_gap = ski_config.dynamic_center_gap / 2.0

        for percent, obs_type in zip(percentages, types, strict=True):
            obs_y = start_y - (track_length * percent)
            if obs_type == 1:
                min_x = Grid.x(start_col - bounds)
                max_x = Grid.x(start_col + bounds - side_gap)
                obstacles.append(
                    ObstacleState(
                        x=rng.uniform(min_x, max_x),
                        y=obs_y,
                        min_x=min_x,
                        max_x=max_x,
                        speed=speed_px,
                        direction=rng.choice([-1.0, 1.0]),
                    )
                )
            elif obs_type == 2:
                min_x = Grid.x(start_col - bounds + side_gap)
                max_x = Grid.x(start_col + bounds)
                obstacles.append(
                    ObstacleState(
                        x=rng.uniform(min_x, max_x),
                        y=obs_y,
                        min_x=min_x,
                        max_x=max_x,
                        speed=speed_px,
                        direction=rng.choice([-1.0, 1.0]),
                    )
                )
            elif obs_type == 3:
                l_min = Grid.x(start_col - bounds)
                l_max = Grid.x(start_col - center_gap)
                r_min = Grid.x(start_col + center_gap)
                r_max = Grid.x(start_col + bounds)
                obstacles.append(
                    ObstacleState(
                        x=rng.uniform(l_min, l_max),
                        y=obs_y,
                        min_x=l_min,
                        max_x=l_max,
                        speed=speed_px,
                        direction=rng.choice([-1.0, 1.0]),
                    )
                )
                obstacles.append(
                    ObstacleState(
                        x=rng.uniform(r_min, r_max),
                        y=obs_y,
                        min_x=r_min,
                        max_x=r_max,
                        speed=speed_px,
                        direction=rng.choice([-1.0, 1.0]),
                    )
                )

    return goal_x, goal_y, obstacles


def create_initial_state(username: str, seed: int | None = None, dynamic: bool = False) -> SkiState:  # noqa: FBT001
    start_col = 6.0
    start_x = Grid.x(start_col)
    start_y = Grid.y(10)
    base_goal_y = Grid.y(10 - ski_config.goal_distance_grid)

    actual_seed = ski_config.obstacle_seed if seed is None else seed

    goal_x, goal_y, obstacles = generate_track_plan(actual_seed, start_col, start_y, base_goal_y, dynamic)

    return SkiState(
        username=username,
        time_left=float(ski_config.time_limit),
        countdown=10.0,
        is_paused=True,
        x=start_x,
        y=start_y,
        angle=0.0,
        start_x=start_x,
        start_y=start_y,
        goal_x=goal_x,
        goal_y=goal_y,
        score=0.0,
        reached_goal=False,
        is_moving=False,
        knockback_timer=0.0,
        knockback_dx=0.0,
        knockback_dy=0.0,
        obstacles=obstacles,
    )
