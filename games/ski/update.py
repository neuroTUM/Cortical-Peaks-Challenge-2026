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
    if is_dynamic:
        base_score = progress * ski_config.max_score_dynamic
    else:
        base_score = progress * ski_config.max_score_static

    if state.reached_goal:
        state.score = base_score + state.current_time_bonus
    else:
        state.score = base_score


def _check_goal(state: SkiState) -> bool:
    dist = math.hypot(state.x - state.goal_x, state.y - state.goal_y)
    if dist <= ski_config.goal_radius:
        state.reached_goal = True
        state.game_over = True
        _update_score(state)
        return True
    return False


def _check_collisions(state: SkiState) -> None:

    if state.knockback_timer > 0:
        return

    pr = ski_config.player_radius

    for obs in state.obstacles:
        if obs.speed > 0:
            hw = ski_config.dynamic_obstacle_hitbox_width / 2.0
            hh = ski_config.dynamic_obstacle_hitbox_height / 2.0
            offset_y = ski_config.dynamic_obstacle_hitbox_offset_y
        else:
            hw = ski_config.obstacle_hitbox_width / 2.0
            hh = ski_config.obstacle_hitbox_height / 2.0
            offset_y = ski_config.obstacle_hitbox_offset_y

        hitbox_center_y = obs.y + offset_y

        rect_left = obs.x - hw
        rect_right = obs.x + hw
        rect_top = hitbox_center_y - hh
        rect_bottom = hitbox_center_y + hh

        closest_x = max(rect_left, min(state.x, rect_right))
        closest_y = max(rect_top, min(state.y, rect_bottom))

        dist = math.hypot(state.x - closest_x, state.y - closest_y)

        if dist < pr:
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
