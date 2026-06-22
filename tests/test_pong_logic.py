from games.pong.config import pong_config
from games.pong.state import PongState, PongStateAdapter, create_initial_state
from games.pong.update import update_game_state
from shared.constants import HEIGHT, WIDTH


def _running_state(player1: str = "p1", player2: str = "p2") -> PongState:
    """A pong state that will actually advance (not paused, game started)."""
    state = create_initial_state(player1, player2)
    state.is_paused = False
    state.game_started = True
    return state


def test_pong_state_serialization_roundtrip() -> None:
    state = create_initial_state("alice", "bob")
    data = PongStateAdapter.dump_bytes(state)
    restored = PongStateAdapter.validate_bytes(data)
    assert restored.player1_name == state.player1_name
    assert restored.player2_name == state.player2_name
    assert restored.score_left == state.score_left
    assert restored.score_right == state.score_right
    assert restored.game_over == state.game_over
    assert restored.winner == state.winner
    assert restored.is_paused == state.is_paused


def test_update_unchanged_when_paused() -> None:
    state = create_initial_state("p1")
    state.is_paused = True
    state.game_started = True
    before_frame = state.frame_count
    result = update_game_state(state, "up")
    assert result.frame_count == before_frame


def test_update_unchanged_when_not_started() -> None:
    state = create_initial_state("p1")
    state.is_paused = False
    state.game_started = False
    before_frame = state.frame_count
    result = update_game_state(state, "up")
    assert result.frame_count == before_frame


def test_update_unchanged_when_game_over() -> None:
    state = create_initial_state("p1")
    state.is_paused = False
    state.game_started = True
    state.game_over = True
    before_frame = state.frame_count
    result = update_game_state(state, None)
    assert result.frame_count == before_frame


def test_frame_count_increments() -> None:
    state = _running_state()
    result = update_game_state(state, None)
    assert result.frame_count == 1


def test_left_paddle_moves_up() -> None:
    state = _running_state()
    # Prime move_counter so the next tick triggers a move
    state.left_paddle.move_counter = pong_config.paddle_move_interval - 1
    initial_y = state.left_paddle.y
    result = update_game_state(state, "up")
    assert result.left_paddle.y < initial_y


def test_left_paddle_moves_down() -> None:
    state = _running_state()
    state.left_paddle.move_counter = pong_config.paddle_move_interval - 1
    initial_y = state.left_paddle.y
    result = update_game_state(state, "down")
    assert result.left_paddle.y > initial_y


def test_paddle_clamped_at_top() -> None:
    state = _running_state()
    state.left_paddle.y = 0
    state.left_paddle.move_counter = pong_config.paddle_move_interval - 1
    result = update_game_state(state, "up")
    assert result.left_paddle.y == 0


def test_paddle_clamped_at_bottom() -> None:
    state = _running_state()
    state.left_paddle.y = HEIGHT - state.left_paddle.height
    state.left_paddle.move_counter = pong_config.paddle_move_interval - 1
    result = update_game_state(state, "down")
    assert result.left_paddle.y == HEIGHT - state.left_paddle.height


def test_puck_bounces_top_wall() -> None:
    state = _running_state()
    state.puck.y = 0
    state.puck.dir_y = -1
    state.puck.move_counter = pong_config.puck_move_interval - 1
    result = update_game_state(state, None)
    assert result.puck.dir_y == 1


def test_puck_bounces_bottom_wall() -> None:
    state = _running_state()
    state.puck.y = HEIGHT - state.puck.size
    state.puck.dir_y = 1
    state.puck.move_counter = pong_config.puck_move_interval - 1
    result = update_game_state(state, None)
    assert result.puck.dir_y == -1


def test_right_scores_when_puck_exits_left() -> None:
    state = _running_state()
    # Position puck one step from the left edge, heading left
    state.puck.x = pong_config.puck_step_x
    state.puck.dir_x = -1
    state.puck.move_counter = pong_config.puck_move_interval - 1
    initial_score = state.score_right
    result = update_game_state(state, None)
    assert result.score_right == initial_score + 1


def test_left_scores_when_puck_exits_right() -> None:
    state = _running_state()
    state.puck.x = WIDTH - state.puck.size - pong_config.puck_step_x
    state.puck.dir_x = 1
    state.puck.move_counter = pong_config.puck_move_interval - 1
    initial_score = state.score_left
    result = update_game_state(state, None)
    assert result.score_left == initial_score + 1


def test_game_over_when_left_wins() -> None:
    state = _running_state()
    state.score_left = pong_config.winning_score - 1
    state.puck.x = WIDTH - state.puck.size - pong_config.puck_step_x
    state.puck.dir_x = 1
    state.puck.move_counter = pong_config.puck_move_interval - 1
    result = update_game_state(state, None)
    assert result.game_over
    assert result.winner == 1


def test_game_over_when_right_wins() -> None:
    state = _running_state()
    state.score_right = pong_config.winning_score - 1
    state.puck.x = pong_config.puck_step_x
    state.puck.dir_x = -1
    state.puck.move_counter = pong_config.puck_move_interval - 1
    result = update_game_state(state, None)
    assert result.game_over
    assert result.winner == 2


def test_left_paddle_neutral_input_does_not_move() -> None:
    state = _running_state()
    state.left_paddle.move_counter = pong_config.paddle_move_interval - 1
    y0 = state.left_paddle.y
    result = update_game_state(state, None)  # direction 0 -> _move_paddle returns early
    assert result.left_paddle.y == y0


def test_ai_moves_toward_incoming_puck() -> None:
    state = _running_state()
    state.right_paddle.move_counter = pong_config.paddle_move_interval - 1
    state.right_paddle.y = pong_config.screen_cy
    state.puck.x = pong_config.screen_cx
    state.puck.y = HEIGHT - 100  # well below the paddle center
    state.puck.dir_x = 1  # heading toward the AI paddle
    y0 = state.right_paddle.y
    result = update_game_state(state, None, pvp=False)
    assert result.right_paddle.y > y0


def test_ai_drifts_back_to_center_when_puck_receding() -> None:
    state = _running_state()
    state.right_paddle.move_counter = pong_config.paddle_move_interval - 1
    state.right_paddle.y = 0  # parked at the top, above center
    state.puck.x = pong_config.screen_cx
    state.puck.dir_x = -1  # moving away from the AI
    result = update_game_state(state, None, pvp=False)
    assert result.right_paddle.y > 0  # drifts down toward center


def test_ai_moves_up_toward_high_incoming_puck() -> None:
    state = _running_state()
    state.right_paddle.move_counter = pong_config.paddle_move_interval - 1
    state.right_paddle.y = HEIGHT - state.right_paddle.height  # parked low
    state.puck.x = pong_config.screen_cx
    state.puck.y = 50  # near the top, above the paddle
    state.puck.dir_x = 1  # incoming
    y0 = state.right_paddle.y
    result = update_game_state(state, None, pvp=False)
    assert result.right_paddle.y < y0


def test_ai_drifts_up_to_center_when_below_and_puck_receding() -> None:
    state = _running_state()
    state.right_paddle.move_counter = pong_config.paddle_move_interval - 1
    state.right_paddle.y = HEIGHT - state.right_paddle.height  # below center
    state.puck.x = pong_config.screen_cx
    state.puck.dir_x = -1  # moving away
    y0 = state.right_paddle.y
    result = update_game_state(state, None, pvp=False)
    assert result.right_paddle.y < y0


def test_pvp_player2_input_moves_right_paddle() -> None:
    state = _running_state()
    state.right_paddle.move_counter = pong_config.paddle_move_interval - 1
    y0 = state.right_paddle.y
    result = update_game_state(state, None, "down", pvp=True)
    assert result.right_paddle.y > y0


def test_pvp_right_paddle_idle_without_input() -> None:
    state = _running_state()
    state.right_paddle.move_counter = pong_config.paddle_move_interval - 1
    y0 = state.right_paddle.y
    result = update_game_state(state, None, None, pvp=True)
    assert result.right_paddle.y == y0


def test_paddle_collision_reverses_and_deflects_down() -> None:
    state = _running_state()
    lp = state.left_paddle
    state.puck.move_counter = pong_config.puck_move_interval - 1
    state.puck.dir_x = -1
    state.puck.dir_y = -1
    state.puck.x = lp.x + 5  # ends up overlapping the paddle after the leftward step
    state.puck.y = lp.y + lp.height - state.puck.size  # low on the paddle face
    result = update_game_state(state, None)
    assert result.puck.dir_x == 1  # bounced off the paddle
    assert result.puck.dir_y == 1  # deflected downward


def test_paddle_collision_deflects_up() -> None:
    state = _running_state()
    lp = state.left_paddle
    state.puck.move_counter = pong_config.puck_move_interval - 1
    state.puck.dir_x = -1
    state.puck.dir_y = 1
    state.puck.x = lp.x + 5
    state.puck.y = lp.y  # high on the paddle face
    result = update_game_state(state, None)
    assert result.puck.dir_x == 1
    assert result.puck.dir_y == -1
