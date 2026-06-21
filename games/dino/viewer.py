from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, ClassVar

import pygame

from games.dino.assets import BirdAsset, CactusAsset, DinoAsset
from games.dino.config import dino_config
from games.dino.constants import (
    ANIM_SPEED,
    DINO_GAME_ASSETS,
    ZONE_COLOR,
    ZONE_HEIGHT,
)
from games.dino.game_objects import CloudLayer, Track
from games.dino.hud import dino_is_blinking, heart_x_positions
from games.dino.update import zone_marker_bounds
from shared.asset_manager import AssetManager
from shared.constants import ACCENT_COLOR, DISABLED_COLOR, SUBTEXT_FONT, TEXT_COLOR, TEXT_FONT
from shared.ui import Grid, fill_surface, scale_to_screen, stretch_to_fill

if TYPE_CHECKING:
    from collections.abc import Callable

    from games.dino.state import DinoState, GameState, ObstacleState


@lru_cache(maxsize=32)
def _scaled(img: pygame.Surface, w: int, h: int) -> pygame.Surface:
    """Return img stretched to (w, h), cached by (surface identity, w, h).

    Sprite dimensions are effectively constant during a run, so this cache turns the
    per-frame pygame.transform.scale calls into ~7 one-time scales for the whole session.
    """
    return stretch_to_fill(img, w, h)


class DinoRenderer:
    _running_sprites: ClassVar[list[DinoAsset]] = [DinoAsset.RUN_1, DinoAsset.RUN_2]

    def __init__(self) -> None:
        self.run_imgs = [AssetManager.get(s) for s in self._running_sprites]
        self.jump_img = AssetManager.get(DinoAsset.JUMP)
        self.duck_img = AssetManager.get(DinoAsset.DUCK)

    def draw(self, surface: pygame.Surface, state: DinoState) -> None:
        # Flicker the sprite during the post-hit grace period so the lost life is legible.
        if dino_is_blinking(state.invuln_timer):
            return

        rect = pygame.Rect(state.hitbox_x, state.hitbox_y, state.width, state.height)

        if state.is_jumping:
            img = _scaled(self.jump_img, state.width, state.height)
        elif state.is_ducking:
            img = _scaled(self.duck_img, state.width, state.height)
        else:
            base_img = self.run_imgs[(state.frame_count // ANIM_SPEED) % len(self.run_imgs)]
            img = _scaled(base_img, state.width, state.height)

        surface.blit(img, rect.topleft)

        if dino_config.show_hitboxes:
            pygame.draw.rect(surface, "red", rect, width=2)


class ObstacleRenderer:
    def __init__(self) -> None:
        self.bird_sprites = [AssetManager.get(s) for s in list(BirdAsset)]
        self.cactus_sprite = AssetManager.get(CactusAsset.SPRITE)

    def draw(self, surface: pygame.Surface, state: ObstacleState) -> None:
        rect = pygame.Rect(state.hitbox_x, state.hitbox_y, state.width, state.height)

        if state.type == "bird":
            base_img = self.bird_sprites[(state.frame_count // ANIM_SPEED) % len(self.bird_sprites)]
        else:
            base_img = self.cactus_sprite

        img = _scaled(base_img, state.width, state.height)
        surface.blit(img, rect.topleft)

        if dino_config.show_hitboxes:
            pygame.draw.rect(surface, "red", rect, width=2)


def _draw_heart(surface: pygame.Surface, center: tuple[int, int], size: int, color: tuple[int, int, int] | str) -> None:
    """Draw a filled heart centered on `center`, roughly `size` pixels wide."""
    cx, cy = center
    r = size // 4
    pygame.draw.circle(surface, color, (cx - r, cy), r)
    pygame.draw.circle(surface, color, (cx + r, cy), r)
    pygame.draw.polygon(surface, color, [(cx - 2 * r, cy), (cx + 2 * r, cy), (cx, cy + 2 * r)])


def _draw_lives(surface: pygame.Surface, center_x: int, y: int, lives: int) -> None:
    """Draw a centered row of hearts: filled for remaining lives, dimmed for spent ones."""
    size = 28
    spacing = 40
    for i, x in enumerate(heart_x_positions(center_x, spacing)):
        color = ACCENT_COLOR if i < lives else DISABLED_COLOR
        _draw_heart(surface, (x, y), size, color)


def _draw_zone_marker(surface: pygame.Surface, obs: ObstacleState, ground_y: int, speed: int, dino: DinoState) -> None:
    # Width is invariant (only height shrinks while ducking), so the standing edges define the strip.
    bounds = zone_marker_bounds(obs, speed, dino.hitbox_x, dino.hitbox_x + dino.width)
    if bounds is None:
        return
    zone_x, zone_width = bounds

    zone = pygame.Surface((zone_width, ZONE_HEIGHT), pygame.SRCALPHA)
    zone.fill(ZONE_COLOR)
    surface.blit(zone, (zone_x, ground_y - ZONE_HEIGHT))


class DinoViewerRenderer:
    def __init__(self) -> None:
        AssetManager.load_all(*DINO_GAME_ASSETS)

        # Tiled background scrollers driven by server-supplied offsets.
        self.track = Track()
        self.clouds = CloudLayer()

        # Stateless visual renderers for dynamic objects
        self.dino_renderer = DinoRenderer()
        self.obstacle_renderer = ObstacleRenderer()

        self._ground_y = Grid.y(dino_config.ground_y)

    def render_frame(
        self,
        surface: pygame.Surface,
        screen: pygame.Surface,
        state: GameState,
        overlay: Callable[[pygame.Surface], None] | None = None,
    ) -> None:
        fill_surface(surface)

        # 1. Background
        self.clouds.draw(surface, state.clouds_offset)
        self.track.draw(surface, state.track_offset)

        # 2. Zone markers drawn beneath obstacle sprites
        for obs_state in state.obstacles:
            _draw_zone_marker(surface, obs_state, self._ground_y, state.current_speed, state.dino)

        # 3. Obstacles
        for obs_state in state.obstacles:
            self.obstacle_renderer.draw(surface, obs_state)

        # 4. Dino
        self.dino_renderer.draw(surface, state.dino)

        # 5. UI
        score_txt = TEXT_FONT.render(f"{state.username}: {state.score:04d}", True, TEXT_COLOR)
        surface.blit(score_txt, score_txt.get_rect(center=(Grid.x(9), Grid.y(1))))

        time_txt = SUBTEXT_FONT.render(f"Time: {state.time_left:.1f}s", True, TEXT_COLOR)
        surface.blit(time_txt, time_txt.get_rect(center=(Grid.x(9), Grid.y(2))))

        _draw_lives(surface, Grid.x(9), Grid.y(3), state.lives)

        # 6. Optional overlay (e.g. spectator hints) drawn into the same frame, then scale to window
        if overlay is not None:
            overlay(surface)
        scale_to_screen(surface, screen)
