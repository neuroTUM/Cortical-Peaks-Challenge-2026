from dataclasses import dataclass

from shared.constants import HEIGHT, PONG_WINNING_SCORE, WIDTH


@dataclass
class PongConfig:
    # --- Dimensions (pixels) ---
    paddle_width: int = 40
    paddle_height: int = 180
    puck_size: int = 40

    # --- Physics & Movement (pixels per step, step every N frames) ---
    paddle_step: int = 30
    puck_step_x: int = 20
    puck_step_y: int = 15
    paddle_move_interval: int = 3
    puck_move_interval: int = 3

    # --- Game Mechanics ---
    winning_score: int = PONG_WINNING_SCORE

    # --- Geometry (screen-relative, pixels) ---
    left_paddle_cx: int = WIDTH // 12
    right_paddle_cx: int = WIDTH * 11 // 12
    screen_cx: int = WIDTH // 2
    screen_cy: int = HEIGHT // 2


pong_config = PongConfig()
