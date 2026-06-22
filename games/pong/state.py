from __future__ import annotations

import random
import struct
from dataclasses import dataclass

# Wire format (network byte order):
#   player1_name[16] player2_name[16]
#   left_paddle:  x y width height move_counter
#   right_paddle: x y width height move_counter
#   puck:         x y size dir_x dir_y move_counter
#   score_left score_right game_over winner is_paused game_started frame_count countdown
from games.pong.config import pong_config

_FMT_PONG = "!16s16shhHHHhhHHHhhHbbHBBBBBBHf"  # 74 bytes

# Puck launch angles: always diagonal, never pure horizontal
_LAUNCH_ANGLES: list[tuple[int, int]] = [(-1, -1), (-1, 1), (1, -1), (1, 1)]


@dataclass
class PaddleState:
    x: int  # top-left pixel x
    y: int  # top-left pixel y
    width: int
    height: int
    move_counter: int = 0


@dataclass
class PuckState:
    x: int  # top-left pixel x
    y: int  # top-left pixel y
    size: int
    dir_x: int  # horizontal direction: -1 (left) or 1 (right)
    dir_y: int  # vertical direction:   -1 (up)   or 1 (down)
    move_counter: int = 0


@dataclass
class PongState:
    player1_name: str  # controls left paddle (BCI)
    player2_name: str  # right paddle (AI)
    left_paddle: PaddleState
    right_paddle: PaddleState
    puck: PuckState
    score_left: int = 0
    score_right: int = 0
    game_over: bool = False
    winner: int = 0  # 1 = left, 2 = right
    is_paused: bool = False
    game_started: bool = False
    frame_count: int = 0
    countdown: float = 0.0


class _PongStateAdapter:
    @staticmethod
    def dump_bytes(state: PongState) -> bytes:
        lp, rp, pk = state.left_paddle, state.right_paddle, state.puck
        return struct.pack(
            _FMT_PONG,
            state.player1_name.encode("utf-8")[:16].ljust(16, b"\x00"),
            state.player2_name.encode("utf-8")[:16].ljust(16, b"\x00"),
            lp.x,
            lp.y,
            lp.width,
            lp.height,
            lp.move_counter,
            rp.x,
            rp.y,
            rp.width,
            rp.height,
            rp.move_counter,
            pk.x,
            pk.y,
            pk.size,
            pk.dir_x,
            pk.dir_y,
            pk.move_counter,
            state.score_left,
            state.score_right,
            int(state.game_over),
            state.winner,
            int(state.is_paused),
            int(state.game_started),
            state.frame_count,
            state.countdown,
        )

    @staticmethod
    def validate_bytes(data: bytes) -> PongState:
        (
            p1_b,
            p2_b,
            lp_x,
            lp_y,
            lp_w,
            lp_h,
            lp_mc,
            rp_x,
            rp_y,
            rp_w,
            rp_h,
            rp_mc,
            pk_x,
            pk_y,
            pk_sz,
            pk_dx,
            pk_dy,
            pk_mc,
            score_left,
            score_right,
            game_over_b,
            winner,
            is_paused_b,
            game_started_b,
            frame_count,
            countdown,
        ) = struct.unpack(_FMT_PONG, data)
        return PongState(
            player1_name=p1_b.rstrip(b"\x00").decode("utf-8"),
            player2_name=p2_b.rstrip(b"\x00").decode("utf-8"),
            left_paddle=PaddleState(x=lp_x, y=lp_y, width=lp_w, height=lp_h, move_counter=lp_mc),
            right_paddle=PaddleState(x=rp_x, y=rp_y, width=rp_w, height=rp_h, move_counter=rp_mc),
            puck=PuckState(x=pk_x, y=pk_y, size=pk_sz, dir_x=pk_dx, dir_y=pk_dy, move_counter=pk_mc),
            score_left=score_left,
            score_right=score_right,
            game_over=bool(game_over_b),
            winner=winner,
            is_paused=bool(is_paused_b),
            game_started=bool(game_started_b),
            frame_count=frame_count,
            countdown=countdown,
        )


PongStateAdapter = _PongStateAdapter()


def create_initial_state(player1_name: str, player2_name: str = "COM") -> PongState:
    cfg = pong_config
    dir_x, dir_y = random.choice(_LAUNCH_ANGLES)

    return PongState(
        player1_name=player1_name,
        player2_name=player2_name,
        left_paddle=PaddleState(
            x=cfg.left_paddle_cx - cfg.paddle_width // 2,
            y=cfg.screen_cy - cfg.paddle_height // 2,
            width=cfg.paddle_width,
            height=cfg.paddle_height,
        ),
        right_paddle=PaddleState(
            x=cfg.right_paddle_cx - cfg.paddle_width // 2,
            y=cfg.screen_cy - cfg.paddle_height // 2,
            width=cfg.paddle_width,
            height=cfg.paddle_height,
        ),
        puck=PuckState(
            x=cfg.screen_cx - cfg.puck_size // 2,
            y=cfg.screen_cy - cfg.puck_size // 2,
            size=cfg.puck_size,
            dir_x=dir_x,
            dir_y=dir_y,
        ),
        is_paused=True,
    )
