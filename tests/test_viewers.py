import pygame
import pytest

from games.dino.state import create_initial_state as create_dino_state
from games.dino.viewer import DinoViewerRenderer
from games.pong.state import create_initial_state as create_pong_state
from games.pong.viewer import PongViewerRenderer
from shared.constants import BACKGROUND_COLOR, WIDTH
from shared.ui import Grid, init_pygame

# These smoke tests render real frames headlessly. The SDL dummy video/audio drivers are exported by
# the justfile `test` recipe, so run them via `just test` / `just check` rather than bare pytest.


@pytest.fixture(scope="module")
def surfaces() -> tuple[pygame.Surface, pygame.Surface]:
    surface, screen = init_pygame("test")
    return surface, screen


def _non_background_pixels(surface: pygame.Surface, step: int = 40) -> int:
    bg = pygame.Color(BACKGROUND_COLOR)[:3]
    return sum(
        1
        for x in range(0, surface.get_width(), step)
        for y in range(0, surface.get_height(), step)
        if surface.get_at((x, y))[:3] != bg
    )


def test_dino_viewer_renders_without_raising(surfaces: tuple[pygame.Surface, pygame.Surface]) -> None:
    surface, screen = surfaces
    state = create_dino_state("tester", jump_only=False, seed=1)
    state.is_paused = False
    state.countdown = 0.0
    DinoViewerRenderer().render_frame(surface, screen, state)
    assert _non_background_pixels(surface) > 0


def test_dino_hud_draws_red_hearts(surfaces: tuple[pygame.Surface, pygame.Surface]) -> None:
    surface, screen = surfaces
    state = create_dino_state("tester", jump_only=False, seed=1)
    state.is_paused = False
    state.countdown = 0.0
    state.lives = 2
    DinoViewerRenderer().render_frame(surface, screen, state)

    row_y = Grid.y(3)
    reds = sum(1 for x in range(WIDTH) if surface.get_at((x, row_y))[:3] == (255, 0, 0))
    assert reds > 0, "expected red heart pixels along the lives row"


def test_pong_viewer_renders_without_raising(surfaces: tuple[pygame.Surface, pygame.Surface]) -> None:
    surface, screen = surfaces
    state = create_pong_state("p1", "p2")
    state.is_paused = False
    state.game_started = True
    PongViewerRenderer().render_frame(surface, screen, state)
    assert _non_background_pixels(surface) > 0
