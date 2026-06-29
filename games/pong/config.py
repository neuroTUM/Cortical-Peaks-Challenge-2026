import warnings
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

    def __post_init__(self) -> None:
        errors, warns = validate_pong_config(self)
        if errors:
            raise ValueError("invalid PongConfig:\n  " + "\n  ".join(errors))
        for message in warns:
            warnings.warn(message, stacklevel=3)


def validate_pong_config(cfg: PongConfig) -> tuple[list[str], list[str]]:
    # Pure check of a PongConfig against the invariants the game loop assumes.
    # Returns (errors, warnings): errors are configs that break the loop,
    # warnings are configs that run but are likely a mistake.
    errors: list[str] = []
    warnings_out: list[str] = []

    # Positive dimensions and movement.
    for name in ("paddle_width", "paddle_height", "puck_size", "paddle_step", "puck_step_x", "puck_step_y"):
        value = getattr(cfg, name)
        if value <= 0:
            errors.append(f"{name}={value} must be > 0")

    for name in ("paddle_move_interval", "puck_move_interval"):
        value = getattr(cfg, name)
        if value < 1:
            errors.append(f"{name}={value} must be >= 1")

    if cfg.winning_score < 1:
        errors.append(f"winning_score={cfg.winning_score} must be >= 1 (game would end on frame 1)")

    # Field fit: paddle and puck must fit inside the play area.
    if cfg.paddle_height >= HEIGHT:
        errors.append(f"paddle_height={cfg.paddle_height} must be < HEIGHT={HEIGHT}; paddle cannot fit or move")
    if cfg.puck_size >= HEIGHT:
        errors.append(f"puck_size={cfg.puck_size} must be < HEIGHT={HEIGHT}; wall bounce oscillates otherwise")
    if cfg.puck_size >= WIDTH:
        errors.append(f"puck_size={cfg.puck_size} must be < WIDTH={WIDTH}; puck cannot fit horizontally")

    # Tunneling: a single horizontal step must stay strictly below the collision
    # window (paddle_width + puck_size). The window is an open interval, so a step
    # equal to it can land on both excluded endpoints and skip the paddle.
    window = cfg.paddle_width + cfg.puck_size
    if cfg.puck_step_x >= window:
        errors.append(
            f"puck_step_x={cfg.puck_step_x} must be < paddle_width+puck_size={window}; puck tunnels through paddle",
        )

    # Paddle geometry, derived the same way create_initial_state and the
    # collision gate derive paddle boxes from the centre x.
    half_pw = cfg.paddle_width // 2
    left_x = cfg.left_paddle_cx - half_pw
    left_face = left_x + cfg.paddle_width  # right edge; the face the puck hits
    right_x = cfg.right_paddle_cx - half_pw
    right_face = right_x  # left edge; the face the puck hits
    left_center = left_x + cfg.paddle_width / 2
    right_center = right_x + cfg.paddle_width / 2
    field_mid = WIDTH / 2
    inner_gap = right_face - left_face

    # Placement: both paddles inside the field.
    if left_x < 0:
        errors.append(f"left paddle (cx={cfg.left_paddle_cx}) extends off the left edge to x={left_x}")
    if right_x + cfg.paddle_width > WIDTH:
        errors.append(
            f"right paddle (cx={cfg.right_paddle_cx}) extends past the right edge to x={right_x + cfg.paddle_width}",
        )

    # Velocity-gate assumption: the collision code decides a paddle's side by
    # comparing its centre to WIDTH/2. A paddle on the wrong half is misclassified
    # and stops bouncing, so the puck passes through or vibrates against it.
    if left_center >= field_mid:
        errors.append(
            f"left paddle center={left_center:.0f} must be left of field center={field_mid:.0f}; "
            f"collision gate misclassifies it",
        )
    if right_center < field_mid:
        errors.append(
            f"right paddle center={right_center:.0f} must be right of field center={field_mid:.0f}; "
            f"collision gate misclassifies it",
        )

    # Paddles must not overlap, and the puck must fit in the gap between their
    # faces, else it can contact both paddles at once and is batted between them.
    if inner_gap <= 0:
        errors.append(f"left and right paddles overlap (gap between faces is {inner_gap})")
    elif cfg.puck_size >= inner_gap:
        errors.append(
            f"puck_size={cfg.puck_size} does not fit between the paddles (gap between faces is {inner_gap})",
        )

    # The puck must bounce before reaching a goal: a single step may not exceed
    # the distance from a paddle face to the goal line behind it.
    if cfg.puck_step_x >= left_face:
        errors.append(
            f"puck_step_x={cfg.puck_step_x} can reach the left goal before the paddle stops it "
            f"(paddle face at x={left_face})",
        )
    right_goal_dist = WIDTH - right_face
    if cfg.puck_step_x >= right_goal_dist:
        errors.append(
            f"puck_step_x={cfg.puck_step_x} can reach the right goal before the paddle stops it "
            f"(distance to goal is {right_goal_dist})",
        )

    # Warnings: runs, but likely a mistake.
    if 2 * cfg.puck_step_x > window:
        warnings_out.append(
            f"puck_step_x={cfg.puck_step_x} is more than half the collision window ({window}); "
            f"thin margin before tunneling",
        )
    if cfg.paddle_step > cfg.paddle_height:
        warnings_out.append(
            f"paddle_step={cfg.paddle_step} exceeds paddle_height={cfg.paddle_height}; paddle can jump past the puck",
        )
    if 0 < HEIGHT - cfg.paddle_height < cfg.paddle_step:
        warnings_out.append(
            f"paddle_height={cfg.paddle_height} leaves less than one step of travel "
            f"(HEIGHT-paddle_height={HEIGHT - cfg.paddle_height} < paddle_step={cfg.paddle_step})",
        )

    return errors, warnings_out


pong_config = PongConfig()
