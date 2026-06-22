import contextlib
from typing import TYPE_CHECKING

import pygame

from shared.constants import (
    ACCENT_COLOR,
    BACKGROUND_COLOR,
    DEBUG,
    DISABLED_COLOR,
    HEIGHT,
    ICON_PATH,
    TEXT_COLOR,
    WIDTH,
)

if TYPE_CHECKING:
    from collections.abc import Callable

_GRID_LABELS = ("1/12", "1/6", "1/4", "1/3", "5/12", "1/2", "7/12", "2/3", "3/4", "5/6", "11/12")


def _draw_debug_grid(surface: pygame.Surface) -> None:
    font = pygame.font.SysFont("arial", 16)

    for i in range(1, 12):
        x = int(WIDTH * i / 12)
        y = int(HEIGHT * i / 12)
        pygame.draw.line(surface, "gray50", (x, 0), (x, HEIGHT), 2)
        pygame.draw.line(surface, "gray50", (0, y), (WIDTH, y), 2)

        lbl = font.render(_GRID_LABELS[i - 1], True, "gray50")
        surface.blit(lbl, (x + 4, 4))
        surface.blit(lbl, (4, y + 4))

    pygame.draw.line(surface, "indianred", (Grid.cx - 20, Grid.cy), (Grid.cx + 20, Grid.cy), 3)
    pygame.draw.line(surface, "indianred", (Grid.cx, Grid.cy - 20), (Grid.cx, Grid.cy + 20), 3)


def _noop(_: pygame.Surface) -> None:
    pass


draw_debug_grid = _draw_debug_grid if DEBUG else _noop


def init_pygame(caption: str = "BCI ARCADE") -> tuple[pygame.Surface, pygame.Surface]:
    pygame.init()
    pygame.display.set_caption(caption)
    with contextlib.suppress(FileNotFoundError, pygame.error):
        pygame.display.set_icon(pygame.image.load(str(ICON_PATH)))
    pygame.event.pump()
    screen = pygame.display.set_mode((0, 0), pygame.RESIZABLE)
    surface = pygame.Surface((WIDTH, HEIGHT))
    return surface, screen


def fill_surface(surface: pygame.Surface) -> None:
    surface.fill(BACKGROUND_COLOR)
    draw_debug_grid(surface)


def scale_to_screen(surface: pygame.Surface, screen: pygame.Surface) -> None:
    screen_w, screen_h = screen.get_size()
    scaled = pygame.transform.scale(surface, (screen_w, screen_h))
    screen.blit(scaled, (0, 0))
    pygame.display.flip()


def mouse_pos_to_surface(screen: pygame.Surface) -> tuple[int, int]:
    screen_w, screen_h = screen.get_size()
    scale_x, scale_y = screen_w / WIDTH, screen_h / HEIGHT
    raw_mouse = pygame.mouse.get_pos()
    return (int(raw_mouse[0] / scale_x), int(raw_mouse[1] / scale_y))


def scale_to_fit(img: pygame.Surface, width: int, height: int) -> pygame.Surface:
    orig_w, orig_h = img.get_size()

    # compute scaling factor while keeping aspect ratio
    scale_w = width / orig_w
    scale_h = height / orig_h
    scale = min(scale_w, scale_h)

    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)

    return pygame.transform.scale(img, (new_w, new_h))


def stretch_to_fill(img: pygame.Surface, width: int, height: int) -> pygame.Surface:
    orig_w, orig_h = img.get_size()

    scale_w = width / orig_w
    scale_h = height / orig_h

    new_w = int(orig_w * scale_w)
    new_h = int(orig_h * scale_h)
    return pygame.transform.scale(img, (new_w, new_h))


class Grid:
    """
    Screen positions using 12ths grid.

    `Grid.x(6) = center`, `Grid.pos(6, 3) = (center, 1/4)`
    """

    center = (WIDTH // 2, HEIGHT // 2)
    cx, cy = center

    @staticmethod
    def x(twelfths: float) -> int:
        return int(WIDTH * twelfths / 12)

    @staticmethod
    def y(twelfths: float) -> int:
        return int(HEIGHT * twelfths / 12)

    @staticmethod
    def pos(x_twelfths: float, y_twelfths: float) -> tuple[int, int]:
        return (Grid.x(x_twelfths), Grid.y(y_twelfths))


class Button:
    def __init__(
        self,
        pos: tuple[int, int],
        text_input: str,
        font: pygame.font.Font,
        text_color: str = TEXT_COLOR,
        accent_color: str = ACCENT_COLOR,
        disabled_color: str = DISABLED_COLOR,
        on_click: Callable[[], None] | None = None,
    ) -> None:
        self.x, self.y = pos
        self.font = font
        self.text_input = text_input
        self.text_color = text_color
        self.accent_color = accent_color
        self.disabled_color = disabled_color
        self.on_click = on_click
        self.disabled = False
        self._base_color = text_color if on_click else disabled_color
        self.text = self.font.render(text_input, True, self._base_color)
        self.text_rect = self.text.get_rect(center=(self.x, self.y))

    def update(self, surface: pygame.Surface, mouse_pos: tuple[int, int]) -> None:
        if not self.on_click or self.disabled:
            color = self.disabled_color
        else:
            mouse_over = self.text_rect.collidepoint(mouse_pos)
            color = self.accent_color if mouse_over else self.text_color

        text = self.font.render(self.text_input, True, color)
        surface.blit(text, self.text_rect)

    def handle_click(self, pos: tuple[int, int]) -> None:
        if self.on_click and not self.disabled and self.text_rect.collidepoint(pos):
            self.on_click()


class TextInput:
    def __init__(
        self,
        pos: tuple[int, int],
        font: pygame.font.Font,
        label: str = "",
        default_text: str = "",
        text_color: str = TEXT_COLOR,
        accent_color: str = ACCENT_COLOR,
        disabled_color: str = DISABLED_COLOR,
        max_length: int = 12,
    ) -> None:
        self.x, self.y = pos
        self.font = font
        self.label = label
        self.max_length = max_length
        self.text_color = text_color
        self.accent_color = accent_color
        self.disabled_color = disabled_color

        self.text = default_text  # prefilled but still editable
        self.active = False
        self.disabled = False  # external code may set this; a default value no longer locks the field

        # fixed dimensions using grid
        self.width = Grid.x(5)
        self.height = Grid.y(1)
        self.rect = pygame.Rect(0, 0, self.width, self.height)
        self.rect.center = (self.x, self.y)
        self.padding = 10

    def get_text(self) -> str:
        return self.text

    def handle_event(self, event: pygame.event.Event) -> None:
        if not self.active or self.disabled:
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.active = False
            elif len(self.text) < self.max_length and event.unicode.isprintable():
                self.text += event.unicode

    def handle_click(self, pos: tuple[int, int]) -> None:
        if not self.disabled:
            self.active = self.rect.collidepoint(pos)

    def update(self, surface: pygame.Surface, mouse_pos: tuple[int, int]) -> None:
        if self.label:
            label_surface = self.font.render(self.label, True, self.text_color)
            label_rect = label_surface.get_rect(midbottom=(self.rect.centerx, self.rect.y - 5))
            surface.blit(label_surface, label_rect)

        mouse_over = self.rect.collidepoint(mouse_pos)

        if self.disabled:
            border_color = self.disabled_color
        elif self.active or mouse_over:
            border_color = self.accent_color
        else:
            border_color = self.text_color

        pygame.draw.rect(surface, border_color, self.rect, 3)

        text_color = self.disabled_color if self.disabled else self.text_color
        text_surface = self.font.render(self.text, True, text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)

        surface.blit(text_surface, text_rect)
