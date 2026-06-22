from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from typing import TYPE_CHECKING, Literal

import pygame

from games.dino.config import dino_config
from shared.constants import FPS
from shared.ui import Grid

if TYPE_CHECKING:
    from games.dino.state import GameState, ObstacleState


@lru_cache(maxsize=8)
def _jump_safe_frames(jv: int, g: float, obs_height: int) -> tuple[int, int] | None:
    """Run the actual discrete jump physics; return (first, last) frame indices where the
    dino's airborne height >= obs_height, or None if the jump can't reach that height.

    The game's physics use `int(y_speed)` per frame, which truncates fractional velocity
    toward zero and yields a slightly lower peak / shorter safe window than the closed-form
    continuous solution would predict. Simulating the same recurrence keeps the zone marker
    in lock-step with what the player will actually experience at the obstacle.
    """
    y_speed = -float(jv)
    base_y = 0  # signed offset from ground; rises negative
    frame = 0
    safe: list[int] = []
    while True:
        frame += 1
        y_speed += g
        base_y += int(y_speed)
        if base_y >= 0:
            break
        if -base_y >= obs_height:
            safe.append(frame)
    if not safe:
        return None
    return safe[0], safe[-1]


def safe_press_window(obs: ObstacleState, speed: int, dino_left: int, dino_right: int) -> tuple[float, float]:
    """Range of obs.hitbox_x at press time where pressing jump/duck clears the obstacle.

    Returns (safe_min, safe_max). safe_min is the latest safe press (obstacle closest);
    safe_max is the earliest safe press (obstacle furthest). Returns (0, 0) when no
    safe window exists (e.g. cactus too tall to clear given jump physics).
    """
    if obs.type == "bird":
        # Duck timer must outlast the bird-dino horizontal overlap.
        safe_min = float(dino_right)
        safe_max = float(dino_left - obs.width + dino_config.duck_duration * speed)
        return safe_min, safe_max

    frames = _jump_safe_frames(dino_config.jump_velocity, dino_config.gravity, obs.height)
    if frames is None:
        return 0.0, 0.0
    first_safe, last_safe = frames
    # Overlap at game-frame N requires obs.hitbox_x < dino_right and > dino_left - obs.width.
    # safe_min/safe_max are the X0 bounds that shift the integer overlap range into
    # [first_safe, last_safe] exactly.
    safe_min = float(dino_right + (first_safe - 1) * speed)
    safe_max = float(dino_left + (last_safe + 1) * speed - obs.width)
    return safe_min, safe_max


def zone_marker_bounds(obs: ObstacleState, speed: int, dino_left: int, dino_right: int) -> tuple[int, int] | None:
    """Screen-space (x, width) of the safe-press carpet, using touch (edge-overlap) semantics.

    Sized and placed so the dino's full hitbox overlaps it exactly across the safe press window:
    pressing whenever any part of the dino touches the strip clears the obstacle. The width is the
    safe window minus the dino width, so it requires the window to exceed the dino width; returns
    None when no such carpet exists (window too narrow, or the obstacle is unclearable). Its length
    varies with the obstacle - a short duck window yields a short strip, a tall jump window a long one.
    """
    safe_min, safe_max = safe_press_window(obs, speed, dino_left, dino_right)
    width = int(safe_max - safe_min) - (dino_right - dino_left)
    if width <= 0:
        return None
    zone_x = obs.hitbox_x - int(safe_max - dino_right)
    return zone_x, width


def _apply_input(state: GameState, player_input: Literal["jump", "duck"] | None) -> None:
    """Translate the current player input into dino physics intent (jump impulse or duck timer)."""
    dino = state.dino
    if player_input == "jump" and not dino.is_jumping and not dino.is_ducking:
        dino.y_speed = -dino_config.jump_velocity
        dino.is_jumping = True
    elif player_input == "duck" and not dino.is_jumping:
        dino.is_ducking = True
        dino.duck_timer = dino_config.duck_duration


def _update_dino(state: GameState) -> None:
    """Advance dino physics for one frame and refresh its dimensions and hitbox."""
    dino = state.dino
    dino_w = Grid.x(dino_config.dino_width)
    dino_h = Grid.y(dino_config.dino_height)
    dino_duck_h = Grid.y(dino_config.dino_duck_height)
    ground_level = Grid.y(dino_config.ground_y)

    if dino.invuln_timer > 0:
        dino.invuln_timer -= 1

    if dino.is_jumping:
        dino.y_speed += dino_config.gravity
        dino.base_y += int(dino.y_speed)
        if dino.base_y >= ground_level:
            dino.base_y = ground_level
            dino.y_speed = 0.0
            dino.is_jumping = False
        dino.height = dino_h
    elif dino.is_ducking:
        dino.duck_timer -= 1
        dino.height = dino_duck_h
        if dino.duck_timer <= 0:
            dino.is_ducking = False
            dino.height = dino_h
    else:
        dino.height = dino_h

    dino.width = dino_w
    dino.hitbox_x = dino.base_x - (dino.width // 2)
    dino.hitbox_y = dino.base_y - dino.height
    dino.frame_count += 1


def _advance_environment(state: GameState) -> None:
    """Scroll the parallax cloud and track layers by the current game speed."""
    # Floor of 1 keeps clouds visibly drifting even if game_speed drops below 3 (defensive).
    state.clouds_offset += max(1, state.current_speed // 3)
    state.track_offset += state.current_speed


def _advance_obstacles(state: GameState) -> None:
    """Move every obstacle left by current speed and drop any that have fully left the screen."""
    speed = state.current_speed
    for obs in state.obstacles:
        obs.hitbox_x -= speed
        obs.frame_count += 1
    state.obstacles = [obs for obs in state.obstacles if obs.hitbox_x + obs.width >= 0]


def _advance_timers(state: GameState) -> None:
    """Tick the game timer, set the score to the survival time in seconds, and update remaining time."""
    state.game_timer += 1
    state.time_left = max(0.0, (dino_config.time_limit - state.game_timer) / FPS)
    state.score = min(state.game_timer, dino_config.time_limit) // FPS


def _maybe_spawn_obstacle(state: GameState) -> None:
    """Release the next obstacle from the pre-generated plan when the spawn timer elapses."""
    state.spawn_timer += 1
    if state.spawn_timer >= dino_config.spawn_interval:
        if state.spawn_index < len(state.obstacle_plan):
            state.obstacles.append(replace(state.obstacle_plan[state.spawn_index]))
            state.spawn_index += 1
        state.spawn_timer = 0


def _check_collisions(state: GameState) -> None:
    """Spend a life on the first obstacle overlap, then grant brief invulnerability.

    While invuln_timer is active the dino passes through obstacles unharmed, which stops a
    single obstacle from draining every life across the frames it overlaps the hitbox. The
    run only ends once lives reach zero.
    """
    dino = state.dino
    if dino.invuln_timer > 0:
        return
    dino_rect = pygame.Rect(dino.hitbox_x, dino.hitbox_y, dino.width, dino.height)
    for obs in state.obstacles:
        obs_rect = pygame.Rect(obs.hitbox_x, obs.hitbox_y, obs.width, obs.height)
        if dino_rect.colliderect(obs_rect):
            state.lives -= 1
            dino.invuln_timer = dino_config.invuln_frames
            if state.lives <= 0:
                state.game_over = True
            return


def update_game_state(state: GameState, player_input: Literal["jump", "duck"] | None) -> GameState:
    """Advance the dino game by one frame: input -> dino -> world -> timers -> spawning -> collisions.

    Pure with respect to the input: returns a fresh GameState; the caller's instance and
    its nested DinoState/ObstacleState records are not mutated.
    """
    if state.game_over:
        return state
    state = replace(
        state,
        dino=replace(state.dino),
        obstacles=[replace(o) for o in state.obstacles],
    )
    _apply_input(state, player_input)
    _update_dino(state)
    _advance_environment(state)
    _advance_obstacles(state)
    _advance_timers(state)
    _maybe_spawn_obstacle(state)
    _check_collisions(state)
    if not state.game_over and state.game_timer >= dino_config.time_limit:
        # Survived the full run: maximum base score plus a bonus for each remaining life.
        state.game_over = True
        state.score = dino_config.time_limit // FPS + dino_config.bonus_per_life * state.lives
    return state
