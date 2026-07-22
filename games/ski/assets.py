from typing import TYPE_CHECKING

from shared.asset_manager import Asset
from shared.constants import SKI_ASSETS_DIR

if TYPE_CHECKING:
    from pathlib import Path


class SkiAsset(Asset):
    @property
    def asset_dir(self) -> Path:
        return SKI_ASSETS_DIR

    BRAIN_MOVING = "Skier1.png"
    BRAIN_STOPPED = "Skier2.png"


class ObstacleAsset(Asset):
    @property
    def asset_dir(self) -> Path:
        return SKI_ASSETS_DIR

    SPRITE = "StaticObsticle.png"
    MOVING_SPRITE = "MovingObject.png"
    BARRIER = "Barrier.png"
