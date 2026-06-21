import random

import pytest

from games.dino.config import dino_config
from games.dino.state import (
    GameState,
    GameStateAdapter,
    ObstacleState,
    create_initial_state,
    generate_obstacle_plan,
    spawn_bird,
)
from games.dino.update import (
    safe_press_window,
    update_game_state,
    zone_marker_bounds,
)
from shared.constants import FPS
from shared.ui import Grid


def _active_state(username: str = "test") -> GameState:
    """Initial state with countdown cleared and paused=False so update() runs physics."""
    state = create_initial_state(username)
    state.is_paused = False
    state.countdown = 0.0
    return state


def test_dino_state_serialization_roundtrip() -> None:
    state = create_initial_state("testuser")
    state.lives = 4
    state.dino.invuln_timer = 17
    data = GameStateAdapter.dump_bytes(state)
    restored = GameStateAdapter.validate_bytes(data)
    assert restored.username == state.username
    assert restored.score == state.score
    assert restored.lives == state.lives
    assert restored.time_left == pytest.approx(state.time_left, abs=1e-3)
    assert restored.dino.is_jumping == state.dino.is_jumping
    assert restored.dino.is_ducking == state.dino.is_ducking
    assert restored.dino.invuln_timer == state.dino.invuln_timer
    assert restored.game_over == state.game_over


def test_dino_state_serialization_with_obstacles() -> None:
    state = create_initial_state("tester")
    state.obstacles = [
        ObstacleState(hitbox_x=800, hitbox_y=630, width=100, height=270, type="cactus"),
        ObstacleState(hitbox_x=1200, hitbox_y=700, width=80, height=90, type="bird"),
    ]
    data = GameStateAdapter.dump_bytes(state)
    restored = GameStateAdapter.validate_bytes(data)
    assert len(restored.obstacles) == 2
    assert restored.obstacles[0].type == "cactus"
    assert restored.obstacles[1].type == "bird"


def test_update_unchanged_when_game_over() -> None:
    state = _active_state()
    state.game_over = True
    before_timer = state.game_timer
    result = update_game_state(state, None)
    assert result.game_timer == before_timer


def test_score_tracks_survival_seconds() -> None:
    state = _active_state()
    for _ in range(FPS):
        state = update_game_state(state, None)
    assert state.score == 1


def test_survival_to_time_limit_awards_max_base_plus_life_bonus() -> None:
    state = _active_state()
    state.game_timer = dino_config.time_limit - 1  # one tick from the time limit, no obstacles in range
    result = update_game_state(state, None)
    assert result.game_over
    expected = dino_config.time_limit // FPS + dino_config.bonus_per_life * result.lives
    assert result.score == expected


def test_game_timer_increments_each_frame() -> None:
    state = _active_state()
    for _ in range(3):
        state = update_game_state(state, None)
    assert state.game_timer == 3


def test_time_left_decrements() -> None:
    state = _active_state()
    initial_time = state.time_left
    state = update_game_state(state, None)
    assert state.time_left == pytest.approx(initial_time - 1.0 / FPS)


def test_jump_input_directly_jumps() -> None:
    state = _active_state()
    result = update_game_state(state, "jump")
    assert result.dino.is_jumping


def test_duck_input_directly_ducks() -> None:
    state = _active_state()
    result = update_game_state(state, "duck")
    assert result.dino.is_ducking


def test_duck_ignored_while_jumping() -> None:
    state = _active_state()
    state = update_game_state(state, "jump")
    assert state.dino.is_jumping
    state = update_game_state(state, "duck")
    assert state.dino.is_jumping
    assert not state.dino.is_ducking


def test_duck_expires_when_timer_runs_out() -> None:
    state = _active_state()
    state = update_game_state(state, "duck")
    assert state.dino.is_ducking
    state.dino.duck_timer = 1  # one tick from expiry
    state = update_game_state(state, None)
    assert not state.dino.is_ducking


def test_spawn_releases_planned_obstacle_on_interval() -> None:
    state = _active_state()
    state.spawn_timer = dino_config.spawn_interval - 1
    planned_type = state.obstacle_plan[0].type
    result = update_game_state(state, None)
    assert len(result.obstacles) == 1
    assert result.obstacles[0].type == planned_type
    assert result.spawn_index == 1


def test_spawning_stops_when_plan_is_exhausted() -> None:
    state = _active_state()
    state.spawn_index = len(state.obstacle_plan)  # nothing left to release
    state.spawn_timer = dino_config.spawn_interval - 1
    result = update_game_state(state, None)
    assert result.obstacles == []
    assert result.spawn_index == len(state.obstacle_plan)


def test_close_obstacle_does_not_trigger_game_over() -> None:
    """An obstacle immediately ahead of (but not touching) the dino must not falsely trigger game over."""
    state = _active_state()
    dino_right = state.dino.hitbox_x + state.dino.width
    state.obstacles = [ObstacleState(hitbox_x=dino_right + 10, hitbox_y=630, width=100, height=270, type="cactus")]
    result = update_game_state(state, None)
    assert not result.game_over


def test_bird_spawn_always_hits_standing_dino() -> None:
    rng = random.Random(0)
    ground = Grid.y(dino_config.ground_y)
    dino_standing_top = ground - Grid.y(dino_config.dino_height)
    for _ in range(200):
        bird = spawn_bird(0, rng)
        bird_bottom = bird.hitbox_y + bird.height
        assert bird_bottom > dino_standing_top, (
            f"bird_bottom={bird_bottom} does not reach standing dino top={dino_standing_top}"
        )


def test_bird_spawn_always_clearable_by_ducking_dino() -> None:
    rng = random.Random(0)
    ground = Grid.y(dino_config.ground_y)
    dino_ducking_top = ground - Grid.y(dino_config.dino_duck_height)
    for _ in range(200):
        bird = spawn_bird(0, rng)
        bird_bottom = bird.hitbox_y + bird.height
        assert bird_bottom <= dino_ducking_top, (
            f"bird_bottom={bird_bottom} would collide with ducking dino top={dino_ducking_top}"
        )


def _jump_apex_base_y() -> int:
    """The smallest base_y (highest point) the dino reaches in a jump - also its hitbox bottom there."""
    state = _active_state()
    state = update_game_state(state, "jump")
    apex = state.dino.base_y
    while state.dino.is_jumping:
        state = update_game_state(state, None)
        apex = min(apex, state.dino.base_y)
    return apex


def test_bird_cannot_be_jumped_over() -> None:
    # Every spawned bird's top is above the dino's bottom at jump apex, so even a perfect jump still
    # overlaps it - birds can only be ducked.
    apex_bottom = _jump_apex_base_y()
    rng = random.Random(0)
    for _ in range(200):
        bird = spawn_bird(0, rng)
        assert bird.hitbox_y < apex_bottom, f"bird top={bird.hitbox_y} is jumpable (apex bottom={apex_bottom})"


def test_obstacle_plan_jump_and_duck_is_balanced() -> None:
    plan = generate_obstacle_plan(jump_only=False, seed=1)
    types = [o.type for o in plan]
    assert types.count("cactus") == types.count("bird")
    assert len(plan) > 0


def test_obstacle_plan_jump_only_is_all_cacti() -> None:
    plan = generate_obstacle_plan(jump_only=True, seed=1)
    assert all(o.type == "cactus" for o in plan)
    assert len(plan) > 0


def test_obstacle_plan_is_deterministic_for_a_seed() -> None:
    """Same seed must yield a byte-identical sequence so every competitor faces the same run."""
    a = generate_obstacle_plan(jump_only=False, seed=42)
    b = generate_obstacle_plan(jump_only=False, seed=42)
    assert a == b
    different = generate_obstacle_plan(jump_only=False, seed=43)
    assert [o.type for o in a] != [o.type for o in different] or [o.hitbox_y for o in a] != [
        o.hitbox_y for o in different
    ]


def test_create_initial_state_seeds_the_obstacle_plan() -> None:
    state = create_initial_state("p", jump_only=True, seed=7)
    assert state.obstacle_plan == generate_obstacle_plan(jump_only=True, seed=7)
    assert state.spawn_index == 0


def _make_cactus(hitbox_x: int) -> ObstacleState:
    height = Grid.y(dino_config.cactus_height)
    return ObstacleState(
        hitbox_x=hitbox_x,
        hitbox_y=Grid.y(dino_config.ground_y) - height,
        width=Grid.x(dino_config.cactus_width),
        height=height,
        type="cactus",
    )


def _make_bird(hitbox_x: int) -> ObstacleState:
    width = Grid.x(dino_config.bird_width)
    height = Grid.y(dino_config.bird_height)
    # Place at the lowest spawn height so it just barely hits a standing dino but clears a ducker.
    ground = Grid.y(dino_config.ground_y)
    return ObstacleState(
        hitbox_x=hitbox_x,
        hitbox_y=ground - Grid.y(dino_config.dino_height) - height + 1,
        width=width,
        height=height,
        type="bird",
    )


def _simulate_until_obstacle_passes(state: GameState, max_frames: int = 200) -> GameState:
    for _ in range(max_frames):
        if state.game_over or not state.obstacles:
            return state
        state = update_game_state(state, None)
    return state


def _dino_edges(state: GameState) -> tuple[int, int]:
    return state.dino.hitbox_x, state.dino.hitbox_x + state.dino.width


def test_safe_press_window_cactus_positive_at_game_speed() -> None:
    state = _active_state()
    dino_left, dino_right = _dino_edges(state)
    safe_min, safe_max = safe_press_window(_make_cactus(0), dino_config.game_speed, dino_left, dino_right)
    assert safe_max > safe_min, f"No safe press window for cactus (min={safe_min:.1f}, max={safe_max:.1f})"


def test_safe_press_window_widens_with_speed() -> None:
    state = _active_state()
    dino_left, dino_right = _dino_edges(state)
    cactus = _make_cactus(0)
    low = safe_press_window(cactus, dino_config.game_speed, dino_left, dino_right)
    high = safe_press_window(cactus, dino_config.game_speed * 2, dino_left, dino_right)
    assert (high[1] - high[0]) > (low[1] - low[0]), "Faster speed should widen the safe-press range"


def test_safe_press_window_returns_zero_when_jump_cannot_reach_obstacle() -> None:
    state = _active_state()
    dino_left, dino_right = _dino_edges(state)
    # Synthetic cactus taller than any possible jump apex.
    impossible = ObstacleState(hitbox_x=0, hitbox_y=0, width=320, height=10_000, type="cactus")
    safe_min, safe_max = safe_press_window(impossible, 10, dino_left, dino_right)
    assert (safe_min, safe_max) == (0.0, 0.0)


def test_safe_press_window_bird_uses_duck_duration() -> None:
    state = _active_state()
    dino_left, dino_right = _dino_edges(state)
    speed = dino_config.game_speed
    bird = _make_bird(0)
    safe_min, safe_max = safe_press_window(bird, speed, dino_left, dino_right)
    # Closed-form for bird: latest press is when bird.left meets dino.right; earliest is
    # set by duck_duration outlasting the full horizontal overlap.
    assert safe_min == float(dino_right)
    assert safe_max == float(dino_left - bird.width + dino_config.duck_duration * speed)


def test_perfectly_timed_jump_clears_cactus_at_game_speed() -> None:
    state = _active_state()
    dino_left, dino_right = _dino_edges(state)
    cactus = _make_cactus(0)
    safe_min, _ = safe_press_window(cactus, state.current_speed, dino_left, dino_right)
    cactus.hitbox_x = int(safe_min)
    state.obstacles = [cactus]

    state = update_game_state(state, "jump")
    assert state.dino.is_jumping
    state = _simulate_until_obstacle_passes(state)
    assert not state.game_over, "Latest-safe-press jump must clear the cactus"


def test_earliest_safe_jump_clears_cactus_at_game_speed() -> None:
    """The OTHER bound of the safe window must also yield a clean clearance."""
    state = _active_state()
    dino_left, dino_right = _dino_edges(state)
    cactus = _make_cactus(0)
    _, safe_max = safe_press_window(cactus, state.current_speed, dino_left, dino_right)
    # int() truncates downward, which keeps us inside the safe range rather than past it.
    cactus.hitbox_x = int(safe_max)
    state.obstacles = [cactus]

    state = update_game_state(state, "jump")
    state = _simulate_until_obstacle_passes(state)
    assert not state.game_over, "Earliest-safe-press jump must clear the cactus"


def test_perfectly_timed_duck_clears_bird_at_initial_speed() -> None:
    state = _active_state()
    dino_left, dino_right = _dino_edges(state)
    bird = _make_bird(0)
    safe_min, _ = safe_press_window(bird, state.current_speed, dino_left, dino_right)
    bird.hitbox_x = int(safe_min)
    state.obstacles = [bird]

    state = update_game_state(state, "duck")
    assert state.dino.is_ducking
    state = _simulate_until_obstacle_passes(state)
    assert not state.game_over, "Latest-safe-press duck must clear the bird"


def test_jumping_well_after_safe_window_collides_with_cactus() -> None:
    """Sanity-check the safe-window math by violating it: collision must occur."""
    state = _active_state()
    state.lives = 1  # a single hit must be fatal so the safe-window violation is observable
    dino_left, dino_right = _dino_edges(state)
    cactus = _make_cactus(0)
    safe_min, _ = safe_press_window(cactus, state.current_speed, dino_left, dino_right)
    # Place the cactus well inside the dino's hitbox - pressing jump now cannot save us.
    cactus.hitbox_x = int(safe_min) - dino_config.dino_width * dino_config.game_speed
    state.obstacles = [cactus]

    state = update_game_state(state, "jump")
    state = _simulate_until_obstacle_passes(state)
    assert state.game_over, "A jump pressed far past the safe window must collide"


def test_zone_marker_none_when_obstacle_unclearable() -> None:
    state = _active_state()
    dino_left, dino_right = _dino_edges(state)
    impossible = ObstacleState(hitbox_x=0, hitbox_y=0, width=320, height=10_000, type="cactus")
    assert zone_marker_bounds(impossible, state.current_speed, dino_left, dino_right) is None


def _assert_touch_tracks_window(obs: ObstacleState, state: GameState) -> None:
    """Any part of the dino's hitbox touching the carpet means a safe press (exactly the window)."""
    dino_left, dino_right = _dino_edges(state)
    speed = state.current_speed
    dino_width = dino_right - dino_left
    safe_min, safe_max = safe_press_window(obs, speed, dino_left, dino_right)
    assert safe_max - safe_min > dino_width, "window must exceed dino width for a touch-based carpet"

    def dino_touches_strip(obs_x: int) -> bool:
        obs.hitbox_x = obs_x
        result = zone_marker_bounds(obs, speed, dino_left, dino_right)
        assert result is not None
        zone_x, zone_width = result
        return dino_right > zone_x and dino_left < zone_x + zone_width

    # Inside the window: any part of the dino over the strip means a safe press.
    assert dino_touches_strip(int((safe_min + safe_max) // 2))
    assert dino_touches_strip(int(safe_min) + 2)
    assert dino_touches_strip(int(safe_max) - 2)
    # Outside the window: no part of the dino touches the strip.
    assert not dino_touches_strip(int(safe_max) + dino_width + 20)
    assert not dino_touches_strip(int(safe_min) - dino_width - 20)


def test_zone_marker_touch_safe_for_cactus() -> None:
    _assert_touch_tracks_window(_make_cactus(0), _active_state())


def test_zone_marker_touch_safe_for_bird() -> None:
    _assert_touch_tracks_window(_make_bird(0), _active_state())


def _overlapping_cactus(state: GameState) -> ObstacleState:
    dino = state.dino
    return ObstacleState(
        hitbox_x=dino.hitbox_x,
        hitbox_y=dino.hitbox_y,
        width=dino.width,
        height=dino.height,
        type="cactus",
    )


def test_collision_spends_a_life_without_ending_run() -> None:
    state = _active_state()
    state.lives = 3
    state.obstacles = [_overlapping_cactus(state)]
    result = update_game_state(state, None)
    assert result.lives == 2
    assert not result.game_over
    assert result.dino.invuln_timer == dino_config.invuln_frames


def test_grace_period_prevents_losing_multiple_lives_to_one_obstacle() -> None:
    state = _active_state()
    state.lives = 3
    state.obstacles = [_overlapping_cactus(state)]
    state = update_game_state(state, None)  # first overlap costs one life, grants invuln
    state.obstacles = [_overlapping_cactus(state)]  # still overlapping next frame
    state = update_game_state(state, None)
    assert state.lives == 2, "invulnerability must absorb the consecutive overlap"


def test_depleting_last_life_sets_game_over() -> None:
    state = _active_state()
    state.lives = 1
    state.obstacles = [_overlapping_cactus(state)]
    result = update_game_state(state, None)
    assert result.lives == 0
    assert result.game_over
