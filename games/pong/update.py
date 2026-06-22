from __future__ import annotations

import random
from dataclasses import replace
from typing import Literal

from games.pong.config import pong_config
from games.pong.state import _LAUNCH_ANGLES, PaddleState, PongState, PuckState
from shared.constants import HEIGHT, WIDTH

PongInput = Literal["up", "down"] | None


def update_game_state(
    state: PongState,
    player_input: PongInput,
    player2_input: PongInput = None,
    *,
    pvp: bool = False,
) -> PongState:
    """Advance the game by one tick.

    player_input controls the left (player 1) paddle.
    player2_input controls the right (player 2) paddle.
    When pvp=False and player2_input is None, AI controls the right paddle.
    When pvp=True and player2_input is None, the right paddle stays still.

    Pure with respect to the input: returns a fresh PongState; the caller's
    instance and its nested PaddleState/PuckState records are not mutated.
    """
    if state.game_over or state.is_paused or not state.game_started:
        return state

    state = replace(
        state,
        left_paddle=replace(state.left_paddle),
        right_paddle=replace(state.right_paddle),
        puck=replace(state.puck),
    )

    cfg = pong_config

    direction = -1 if player_input == "up" else (1 if player_input == "down" else 0)
    state.left_paddle.move_counter += 1
    if state.left_paddle.move_counter >= cfg.paddle_move_interval:
        _move_paddle(state.left_paddle, direction, cfg.paddle_step)
        state.left_paddle.move_counter = 0

    state.right_paddle.move_counter += 1
    if state.right_paddle.move_counter >= cfg.paddle_move_interval:
        if player2_input is not None:
            direction2 = -1 if player2_input == "up" else 1
            _move_paddle(state.right_paddle, direction2, cfg.paddle_step)
        elif not pvp:
            _ai_move(state.right_paddle, state.puck, cfg.paddle_step)
        state.right_paddle.move_counter = 0

    state.puck.move_counter += 1
    if state.puck.move_counter >= cfg.puck_move_interval:
        state.puck.x += state.puck.dir_x * cfg.puck_step_x
        state.puck.y += state.puck.dir_y * cfg.puck_step_y
        state.puck.move_counter = 0

        # Top / bottom wall bounce
        if state.puck.y <= 0:
            state.puck.y = 0
            state.puck.dir_y = 1
        elif state.puck.y + state.puck.size >= HEIGHT:
            state.puck.y = HEIGHT - state.puck.size
            state.puck.dir_y = -1

        # Paddle collisions
        _check_paddle_collision(state.puck, state.left_paddle)
        _check_paddle_collision(state.puck, state.right_paddle)

        # Scoring: puck left of screen → right paddle scores; puck right → left scores
        if state.puck.x <= 0:
            state.score_right += 1
            _reset_round(state)
        elif state.puck.x + state.puck.size >= WIDTH:
            state.score_left += 1
            _reset_round(state)

    if state.score_left >= cfg.winning_score:
        state.game_over = True
        state.winner = 1
    elif state.score_right >= cfg.winning_score:
        state.game_over = True
        state.winner = 2

    state.frame_count += 1
    return state


def _move_paddle(paddle: PaddleState, direction: int, step: int) -> None:
    if direction == 0:
        return
    paddle.y = max(0, min(HEIGHT - paddle.height, paddle.y + direction * step))


def _ai_move(paddle: PaddleState, puck: PuckState, step: int) -> None:
    if puck.dir_x <= 0:
        # Puck moving away - drift back toward center
        paddle_center_y = paddle.y + paddle.height // 2
        if paddle_center_y < pong_config.screen_cy - step:
            paddle.y = min(HEIGHT - paddle.height, paddle.y + step)
        elif paddle_center_y > pong_config.screen_cy + step:
            paddle.y = max(0, paddle.y - step)
        return

    puck_center_y = puck.y + puck.size // 2
    paddle_center_y = paddle.y + paddle.height // 2
    if puck_center_y > paddle_center_y + step:
        paddle.y = min(HEIGHT - paddle.height, paddle.y + step)
    elif puck_center_y < paddle_center_y - step:
        paddle.y = max(0, paddle.y - step)


def _check_paddle_collision(puck: PuckState, paddle: PaddleState) -> None:
    puck_right = puck.x + puck.size
    puck_bottom = puck.y + puck.size
    paddle_right = paddle.x + paddle.width
    paddle_bottom = paddle.y + paddle.height

    if puck.x < paddle_right and puck_right > paddle.x and puck.y < paddle_bottom and puck_bottom > paddle.y:
        puck.dir_x = -puck.dir_x

        # Deflect vertical direction based on where the puck hit the paddle face
        puck_center_y = puck.y + puck.size // 2
        paddle_center_y = paddle.y + paddle.height // 2
        hit_ratio = (puck_center_y - paddle_center_y) / (paddle.height / 2) if paddle.height else 0.0
        if hit_ratio > 0.3:
            puck.dir_y = 1
        elif hit_ratio < -0.3:
            puck.dir_y = -1


def _reset_round(state: PongState) -> None:
    cfg = pong_config
    dir_x, dir_y = random.choice(_LAUNCH_ANGLES)

    # Reset paddles to vertical center
    state.left_paddle.y = cfg.screen_cy - cfg.paddle_height // 2
    state.left_paddle.move_counter = 0
    state.right_paddle.y = cfg.screen_cy - cfg.paddle_height // 2
    state.right_paddle.move_counter = 0

    # Reset puck to center
    state.puck.x = cfg.screen_cx - cfg.puck_size // 2
    state.puck.y = cfg.screen_cy - cfg.puck_size // 2
    state.puck.dir_x = dir_x
    state.puck.dir_y = dir_y
    state.puck.move_counter = 0

    # Brief countdown before next ball; server worker sets game_started when it reaches 0
    state.game_started = False
    state.countdown = 3.0
