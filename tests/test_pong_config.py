from dataclasses import replace

import pytest

from games.pong.config import pong_config, validate_pong_config
from shared.constants import HEIGHT, WIDTH


def test_default_config_is_valid() -> None:
    errors, warnings = validate_pong_config(pong_config)
    assert errors == []
    assert warnings == []


# --- Impossible configs: must raise ValueError at construction --------------

IMPOSSIBLE = {
    "zero_paddle_width": ({"paddle_width": 0}, "paddle_width"),
    "negative_paddle_height": ({"paddle_height": -10}, "paddle_height"),
    "zero_puck_size": ({"puck_size": 0}, "puck_size"),
    "zero_puck_step_x": ({"puck_step_x": 0}, "puck_step_x"),
    "zero_puck_step_y": ({"puck_step_y": 0}, "puck_step_y"),
    "zero_paddle_step": ({"paddle_step": 0}, "paddle_step"),
    "zero_paddle_interval": ({"paddle_move_interval": 0}, "paddle_move_interval"),
    "zero_puck_interval": ({"puck_move_interval": 0}, "puck_move_interval"),
    "zero_winning_score": ({"winning_score": 0}, "winning_score"),
    "paddle_taller_than_field": ({"paddle_height": HEIGHT + 1}, "paddle_height"),
    "paddle_exactly_field_height": ({"paddle_height": HEIGHT}, "paddle_height"),
    "puck_taller_than_field": ({"puck_size": HEIGHT}, "puck_size"),
    "tunneling_step": ({"puck_step_x": 81}, "tunnel"),
    "paddle_off_left_edge": ({"left_paddle_cx": 0}, "off the left edge"),
    "paddle_off_right_edge": ({"right_paddle_cx": WIDTH}, "right edge"),
    "paddles_overlap": ({"left_paddle_cx": 500, "right_paddle_cx": 520}, "overlap"),
    # Cross-interactions: each only trips when two+ values change together.
    "left_paddle_on_right_half": ({"left_paddle_cx": WIDTH // 2 + 50}, "left of field center"),
    "right_paddle_on_left_half": ({"right_paddle_cx": WIDTH // 2 - 50}, "right of field center"),
    "puck_too_big_for_gap": ({"left_paddle_cx": 900, "right_paddle_cx": 1020, "puck_size": 150}, "between the paddles"),
    "step_overshoots_goal": ({"left_paddle_cx": 50, "puck_step_x": 75}, "before the paddle"),
}


@pytest.mark.parametrize(("overrides", "match"), list(IMPOSSIBLE.values()), ids=list(IMPOSSIBLE))
def test_impossible_config_raises(overrides: dict, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        replace(pong_config, **overrides)


def test_tunneling_boundary_is_exact() -> None:
    # window - 1 is the last safe value (verified against the real loop). A step
    # equal to the window can skip the paddle at one phase, so it must be
    # rejected. The last safe value is valid but warns about the thin margin.
    window = pong_config.paddle_width + pong_config.puck_size
    with pytest.warns(UserWarning, match="thin margin"):
        ok = replace(pong_config, puck_step_x=window - 1)
    assert validate_pong_config(ok)[0] == []
    with pytest.raises(ValueError, match="tunnel"):
        replace(pong_config, puck_step_x=window)


# --- Questionable configs: warn but do not raise ----------------------------

QUESTIONABLE = {
    "thin_tunneling_margin": ({"puck_step_x": pong_config.paddle_width + pong_config.puck_size - 1}, "thin margin"),
    "paddle_step_exceeds_height": ({"paddle_step": pong_config.paddle_height + 10}, "jump past the puck"),
    "paddle_barely_moves": ({"paddle_height": HEIGHT - 10}, "one step of travel"),
}


@pytest.mark.parametrize(("overrides", "match"), list(QUESTIONABLE.values()), ids=list(QUESTIONABLE))
def test_questionable_config_warns(overrides: dict, match: str) -> None:
    with pytest.warns(UserWarning, match=match):
        replace(pong_config, **overrides)
