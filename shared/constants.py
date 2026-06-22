import sys
from pathlib import Path
from typing import Final

import pygame.font

ROOT_DIR: Final[Path] = Path(__file__).parent.parent

# directories
DATA_DIR: Final[Path] = ROOT_DIR / "data"
GAMES_DIR: Final[Path] = ROOT_DIR / "games"
SHARED_DIR: Final[Path] = ROOT_DIR / "shared"
ASSETS_DIR: Final[Path] = SHARED_DIR / "assets"

# games
DINO_DIR: Final[Path] = GAMES_DIR / "dino"
DINO_ASSETS_DIR: Final[Path] = DINO_DIR / "assets"
PONG_DIR: Final[Path] = GAMES_DIR / "pong"
PONG_ASSETS_DIR: Final[Path] = PONG_DIR / "assets"
WHEELCHAIR_DIR: Final[Path] = GAMES_DIR / "wheelchair"

# misc
DEBUG: Final[bool] = "--debug" in sys.argv
AUDIT: Final[bool] = "--audit" in sys.argv
FPS: Final[int] = 30

# games settings
PONG_WINNING_SCORE: Final[int] = 5

# surface dimensions
WIDTH: Final[int] = 1920
HEIGHT: Final[int] = 1080

# assets
FONT_PATH: Final[Path] = ASSETS_DIR / "font.ttf"
ICON_PATH: Final[Path] = ASSETS_DIR / "icon.png"


def _init_fonts() -> tuple[pygame.font.Font, pygame.font.Font, pygame.font.Font, pygame.font.Font]:
    pygame.font.init()
    if FONT_PATH.exists():
        return (
            pygame.font.Font(str(FONT_PATH), 96),
            pygame.font.Font(str(FONT_PATH), 64),
            pygame.font.Font(str(FONT_PATH), 48),
            pygame.font.Font(str(FONT_PATH), 32),
        )
    return (
        pygame.font.SysFont("arial", 96),
        pygame.font.SysFont("arial", 64),
        pygame.font.SysFont("arial", 48),
        pygame.font.SysFont("arial", 32),
    )


TITLE_FONT, HEADING_FONT, TEXT_FONT, SUBTEXT_FONT = _init_fonts()

# common colors
BACKGROUND_COLOR: Final[str] = "gray25"
TEXT_COLOR: Final[str] = "white"
ACCENT_COLOR: Final[str] = "red"
DISABLED_COLOR: Final[str] = "gray50"
STATUS_OK_COLOR: Final[tuple[int, int, int]] = (0, 220, 0)
STATUS_ERROR_COLOR: Final[tuple[int, int, int]] = (220, 50, 50)
HIGHLIGHT_COLOR: Final[tuple[int, int, int]] = (220, 200, 0)
