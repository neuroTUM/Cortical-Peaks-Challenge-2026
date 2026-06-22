from games.dino.config import dino_config


def dino_is_blinking(invuln_timer: int) -> bool:
    """True on the 'off' phase of the post-hit flicker, so the viewer skips drawing the dino.

    Toggles every 4 frames while the invulnerability grace period is active; returns False once
    the timer has elapsed so the dino is always solid during normal play.
    """
    return invuln_timer > 0 and (invuln_timer // 4) % 2 == 1


def heart_x_positions(center_x: int, spacing: int, count: int | None = None) -> list[int]:
    """Evenly spaced, horizontally centered x-coordinates for the lives hearts.

    Defaults to one slot per configured life. The row is centered on center_x so it stays put as
    hearts fill or empty (the viewer dims spent ones rather than removing them).
    """
    n = dino_config.lives if count is None else count
    start_x = center_x - (n - 1) * spacing // 2
    return [start_x + i * spacing for i in range(n)]
