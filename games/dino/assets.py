from typing import TYPE_CHECKING

from shared.asset_manager import Asset
from shared.constants import DINO_ASSETS_DIR

if TYPE_CHECKING:
    from pathlib import Path


class DinoAsset(Asset):
    @property
    def asset_dir(self) -> Path:
        return DINO_ASSETS_DIR

    RUN_1 = "brain_1.png"
    RUN_2 = "brain_2.png"
    JUMP = "brain_jump.png"
    DUCK = "brain_duck.png"


class CactusAsset(Asset):
    @property
    def asset_dir(self) -> Path:
        return DINO_ASSETS_DIR

    SPRITE = "small_axontree1.png"


class BirdAsset(Asset):
    @property
    def asset_dir(self) -> Path:
        return DINO_ASSETS_DIR

    FLAP_1 = "flyingneurons_1.png"
    FLAP_2 = "flyingneurons_2.png"


class BackgroundAsset(Asset):
    @property
    def asset_dir(self) -> Path:
        return DINO_ASSETS_DIR

    CLOUD = "cloud.png"
    TRACK = "track_white.png"
