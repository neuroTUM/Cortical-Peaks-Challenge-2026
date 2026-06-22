from typing import TYPE_CHECKING

from shared.asset_manager import Asset
from shared.constants import PONG_ASSETS_DIR

if TYPE_CHECKING:
    from pathlib import Path


class PaddleAsset(Asset):
    @property
    def asset_dir(self) -> Path:
        return PONG_ASSETS_DIR

    BLUE = "sb_blue.png"
    GREEN = "sb_green.png"
    PINK = "sb_pink.png"
    RED = "sb_red.png"


class PuckAsset(Asset):
    @property
    def asset_dir(self) -> Path:
        return PONG_ASSETS_DIR

    SNOWBALL = "snowball.png"
