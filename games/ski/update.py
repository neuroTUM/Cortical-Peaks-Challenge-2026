from __future__ import annotations

import math
from dataclasses import replace
from typing import TYPE_CHECKING

from games.ski.config import ski_config
from shared.constants import FPS
from shared.ui import Grid

if TYPE_CHECKING:
    from games.ski.state import SkiState


def _distance_from_start(state: SkiState) -> float:
    return max(0.0, state.start_y - state.y)


def _update_score(state: SkiState) -> None:
    distance = _distance_from_start(state)
    max_track_distance = max(1.0, state.start_y - state.goal_y)

    progress = max(0.0, min(1.0, distance / max_track_distance))

    is_dynamic = any(obs.speed > 0 for obs in state.obstacles)

    base_score = progress * ski_config.max_score_dynamic if is_dynamic else progress * ski_config.max_score_static

    state.score = base_score + state.current_time_bonus if state.reached_goal else base_score


def _check_goal(state: SkiState) -> bool:
    dist = math.hypot(state.x - state.goal_x, state.y - state.goal_y)
    if dist <= ski_config.goal_radius:
        state.reached_goal = True
        state.game_over = True
        _update_score(state)
        return True
    return False


def _dist_to_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx = x2 - x1
    dy = y2 - y1
    l2 = dx * dx + dy * dy
    if l2 == 0.0:
        return math.hypot(px - x1, py - y1)

    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _check_collisions(state: SkiState) -> None:
    if state.knockback_timer > 0:
        return

    pr = ski_config.player_radius

    for obs in state.obstacles:
        hit = False

        if obs.speed > 0:
            sx = obs.x + ski_config.dynamic_sphere_offset_x
            sy = obs.y + ski_config.dynamic_sphere_offset_y
            if math.hypot(state.x - sx, state.y - sy) < pr + ski_config.dynamic_sphere_radius:
                hit = True

            if not hit:
                x1 = obs.x + ski_config.dynamic_capsule_p1_x
                y1 = obs.y + ski_config.dynamic_capsule_p1_y
                x2 = obs.x + ski_config.dynamic_capsule_p2_x
                y2 = obs.y + ski_config.dynamic_capsule_p2_y

                dist = _dist_to_segment(state.x, state.y, x1, y1, x2, y2)
                if dist < pr + ski_config.dynamic_capsule_radius:
                    hit = True
        else:
            cx = obs.x + ski_config.obstacle_collider_offset_x
            cy = obs.y + ski_config.obstacle_collider_offset_y
            if math.hypot(state.x - cx, state.y - cy) < pr + ski_config.obstacle_collider_radius:
                hit = True

        if hit:
            state.knockback_timer = ski_config.knockback_duration
            total_dx = 0.0
            total_dy = -(ski_config.move_speed * ski_config.obstacle_backsteps)

            state.knockback_dx = total_dx / ski_config.knockback_duration
            state.knockback_dy = total_dy / ski_config.knockback_duration
            return


def _update_dynamic_obstacles(state: SkiState) -> None:
    for obs in state.obstacles:
        if obs.speed > 0:
            obs.x += obs.direction * obs.speed * (1.0 / FPS)

            if obs.x >= obs.max_x:
                obs.x = obs.max_x
                obs.direction = -1.0
            elif obs.x <= obs.min_x:
                obs.x = obs.min_x
                obs.direction = 1.0


def update_game_state(state: SkiState, player_input: str | None) -> SkiState:
    if state.game_over:
        return state

    state = replace(state, obstacles=[replace(o) for o in state.obstacles])

    if state.countdown > 0:
        state.countdown = max(0.0, state.countdown - 1.0 / FPS)
        return state

    if state.is_paused:
        return state

    state.time_left -= 1.0 / FPS
    if state.time_left <= 0:
        _update_score(state)
        state.game_over = True
        state.time_left = 0.0
        return state

    screen_w = Grid.x(12)
    p_rad = ski_config.player_radius
    margin = ski_config.track_margin_px
    b_vis_rad = ski_config.barrier_radius
    b_pad = ski_config.barrier_transparent_padding

    left_b_center_x = margin + b_vis_rad
    right_b_center_x = screen_w - margin - b_vis_rad
    top_b_center_y = state.goal_y - ski_config.track_top_margin
    bottom_b_center_y = state.start_y + ski_config.track_bottom_margin

    left_bound = left_b_center_x + (b_vis_rad - b_pad) + p_rad
    right_bound = right_b_center_x - (b_vis_rad - b_pad) - p_rad
    top_bound = top_b_center_y + (b_vis_rad - b_pad) + p_rad
    bottom_bound = bottom_b_center_y - (b_vis_rad - b_pad) - p_rad

    if state.knockback_timer > 0:
        state.knockback_timer = max(0.0, state.knockback_timer - 1.0 / FPS)
        state.x -= state.knockback_dx / FPS
        state.y -= state.knockback_dy / FPS
        state.is_moving = False

        if state.x < left_bound:
            state.x = left_bound
        elif state.x > right_bound:
            state.x = right_bound

        if state.y < top_bound:
            state.y = top_bound
        elif state.y > bottom_bound:
            state.y = bottom_bound

    else:
        if player_input == "rotate_left":
            state.angle -= ski_config.rotation_speed
        elif player_input == "rotate_right":
            state.angle += ski_config.rotation_speed

        state.angle %= 360.0

        old_x = state.x
        old_y = state.y

        if player_input in ("forward", "backward"):
            state.is_moving = True
            rad = math.radians(state.angle - 90)

            dx = math.cos(rad) * ski_config.move_speed
            dy = math.sin(rad) * ski_config.move_speed

            if player_input == "forward":
                state.x += dx
                state.y += dy
            elif player_input == "backward":
                state.x -= dx
                state.y -= dy
        else:
            state.is_moving = False

        if state.x < left_bound or state.x > right_bound or state.y < top_bound or state.y > bottom_bound:
            state.x = old_x
            state.y = old_y
            state.is_moving = False

            if state.x < left_bound:
                state.x = left_bound
            elif state.x > right_bound:
                state.x = right_bound

            if state.y < top_bound:
                state.y = top_bound
            elif state.y > bottom_bound:
                state.y = bottom_bound

    if _check_goal(state):
        return state

    _update_dynamic_obstacles(state)
    _update_score(state)
    _check_collisions(state)

    return state
