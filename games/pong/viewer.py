from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import pygame

from games.pong.assets import PaddleAsset, PuckAsset
from shared.asset_manager import AssetManager
from shared.constants import HEIGHT, SUBTEXT_FONT, TEXT_COLOR, TEXT_FONT
from shared.ui import Grid, fill_surface, scale_to_screen

if TYPE_CHECKING:
    from collections.abc import Callable

    from games.pong.state import PaddleState, PongState, PuckState


class PaddleRenderer:
    def __init__(self, asset: PaddleAsset, *, flip: bool = False) -> None:
        # sb images are landscape (wide); rotate to portrait so they stand upright as paddles
        rotated = pygame.transform.rotate(AssetManager.get(asset), 90)
        self._source = pygame.transform.flip(rotated, True, False) if flip else rotated
        self._cache: dict[tuple[int, int], pygame.Surface] = {}

    def draw(self, surface: pygame.Surface, state: PaddleState) -> None:
        size = (state.width, state.height)
        if size not in self._cache:
            self._cache[size] = pygame.transform.scale(self._source, size)
        surface.blit(self._cache[size], (state.x, state.y))


class PuckRenderer:
    def __init__(self) -> None:
        self._source = AssetManager.get(PuckAsset.SNOWBALL)
        self._cache: dict[int, pygame.Surface] = {}

    def draw(self, surface: pygame.Surface, state: PuckState) -> None:
        if state.size not in self._cache:
            self._cache[state.size] = pygame.transform.scale(self._source, (state.size, state.size))
        surface.blit(self._cache[state.size], (state.x, state.y))


class PongViewerRenderer:
    def __init__(self) -> None:
        left_asset, right_asset = random.sample(list(PaddleAsset), 2)
        self.left_paddle = PaddleRenderer(left_asset)
        self.right_paddle = PaddleRenderer(right_asset, flip=True)
        self.puck = PuckRenderer()

    def render_frame(
        self,
        surface: pygame.Surface,
        screen: pygame.Surface,
        state: PongState,
        overlay: Callable[[pygame.Surface], None] | None = None,
    ) -> None:
        fill_surface(surface)

        # 1. Center divider
        pygame.draw.line(surface, TEXT_COLOR, (Grid.cx, 0), (Grid.cx, HEIGHT), 3)

        # 2. Paddles and puck
        self.left_paddle.draw(surface, state.left_paddle)
        self.right_paddle.draw(surface, state.right_paddle)
        self.puck.draw(surface, state.puck)

        # 3. Scores
        left_score = SUBTEXT_FONT.render(f"{state.player1_name}: {state.score_left}", True, TEXT_COLOR)
        right_score = SUBTEXT_FONT.render(f"{state.player2_name}: {state.score_right}", True, TEXT_COLOR)
        surface.blit(left_score, left_score.get_rect(center=(Grid.x(3), Grid.y(1))))
        surface.blit(right_score, right_score.get_rect(center=(Grid.x(9), Grid.y(1))))

        # 4. Overlays
        if state.countdown > 0:
            hint = TEXT_FONT.render(f"Game starting in {math.ceil(state.countdown)}...", True, TEXT_COLOR)
            surface.blit(hint, hint.get_rect(center=Grid.pos(6, 4)))
        elif state.is_paused:
            hint = TEXT_FONT.render("Waiting for all players...", True, TEXT_COLOR)
            surface.blit(hint, hint.get_rect(center=Grid.pos(6, 4)))

        # 5. Optional overlay (e.g. spectator hints) drawn into the same frame, then scale to window
        if overlay is not None:
            overlay(surface)
        scale_to_screen(surface, screen)
