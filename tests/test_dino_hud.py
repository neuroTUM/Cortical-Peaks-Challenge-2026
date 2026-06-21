from itertools import pairwise

from games.dino.config import dino_config
from games.dino.hud import dino_is_blinking, heart_x_positions


def test_no_blink_when_not_invulnerable() -> None:
    assert dino_is_blinking(0) is False


def test_blink_toggles_every_four_frames() -> None:
    # invuln_timer // 4 alternates 0,1,0,1...; the dino is hidden on the odd ('off') phases.
    assert dino_is_blinking(3) is False  # 3 // 4 == 0
    assert dino_is_blinking(4) is True  # 4 // 4 == 1
    assert dino_is_blinking(7) is True  # 7 // 4 == 1
    assert dino_is_blinking(8) is False  # 8 // 4 == 2


def test_heart_positions_count_defaults_to_configured_lives() -> None:
    assert len(heart_x_positions(center_x=500, spacing=40)) == dino_config.lives


def test_heart_positions_are_centered_and_evenly_spaced() -> None:
    positions = heart_x_positions(center_x=500, spacing=40, count=4)
    assert len(positions) == 4
    # symmetric around the center
    assert positions[0] + positions[-1] == 2 * 500
    # uniform spacing
    gaps = [b - a for a, b in pairwise(positions)]
    assert gaps == [40, 40, 40]


def test_single_heart_sits_on_center() -> None:
    assert heart_x_positions(center_x=500, spacing=40, count=1) == [500]
