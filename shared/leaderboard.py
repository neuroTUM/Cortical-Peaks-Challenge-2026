from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING, Any, ClassVar

import pygame

from shared.constants import ACCENT_COLOR, DATA_DIR, HEADING_FONT, SUBTEXT_FONT, TEXT_COLOR, TEXT_FONT
from shared.log import log
from shared.state import Scene, state
from shared.ui import Button, Grid, fill_surface, mouse_pos_to_surface, scale_to_screen

if TYPE_CHECKING:
    from pathlib import Path


class Leaderboard:
    _path: ClassVar[Path] = DATA_DIR / "leaderboard.json"
    _lock: ClassVar[threading.Lock] = threading.Lock()
    HEADERS: ClassVar[list[str]] = ["#", "NAME", "DINO", "PONG", "CHAIR", "TOTAL"]
    COL_X: ClassVar[tuple[int, ...]] = tuple(Grid.x(i) for i in [0.75, 2.5, 5, 7, 9, 11])
    ROW_Y: ClassVar[tuple[int, ...]] = tuple(Grid.y(i) for i in range(2, 10))

    @classmethod
    def record_dino(cls, name: str, score: int) -> None:
        with cls._lock:
            entries = cls._load()
            entry = cls._get_or_create(entries, name)
            entry["dino"] += score
            cls._commit(entries, entry)

    @classmethod
    def record_pong_win(cls, name: str) -> None:
        if name.upper() == "COM":
            return
        with cls._lock:
            entries = cls._load()
            entry = cls._get_or_create(entries, name)
            entry["pong"] += 1
            cls._commit(entries, entry)

    @classmethod
    def record_wheelchair(cls, name: str, score: int) -> None:
        with cls._lock:
            entries = cls._load()
            entry = cls._get_or_create(entries, name)
            entry["wheelchair"] += score
            cls._commit(entries, entry)

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._save([])

    @classmethod
    def snapshot(cls) -> list[dict[str, Any]]:
        """Return a point-in-time copy of all entries, sorted by total score."""
        with cls._lock:
            return cls._load()

    @classmethod
    def _load(cls) -> list[dict[str, Any]]:
        if cls._path.exists():
            try:
                return json.loads(cls._path.read_text())
            except json.JSONDecodeError:
                return []
        return []

    @classmethod
    def _save(cls, entries: list[dict[str, Any]]) -> None:
        try:
            cls._path.parent.mkdir(parents=True, exist_ok=True)
            cls._path.write_text(json.dumps(entries, indent=2))
        except OSError as e:
            log.error("Failed to save leaderboard: %s", e)

    @classmethod
    def _get_or_create(cls, entries: list[dict[str, Any]], name: str) -> dict[str, Any]:
        for entry in entries:
            if entry["name"] == name:
                return entry
        entry: dict[str, Any] = {"name": name, "dino": 0, "pong": 0, "wheelchair": 0, "total": 0}
        entries.append(entry)
        return entry

    @classmethod
    def _commit(cls, entries: list[dict[str, Any]], entry: dict[str, Any]) -> None:
        entry["total"] = entry["dino"] + entry["pong"] + entry["wheelchair"]
        entries.sort(key=lambda e: -e["total"])
        cls._save(entries)


def run_leaderboard(surface: pygame.Surface, screen: pygame.Surface) -> None:
    entries = Leaderboard.snapshot()
    scroll_offset = 0
    visible_rows = 7
    max_scroll = max(0, len(entries) - visible_rows)

    btn_back = Button(Grid.pos(6, 11), "BACK", TEXT_FONT, on_click=state.go_back)

    while state.scene == Scene.LEADERBOARD:
        mouse_pos = mouse_pos_to_surface(screen)

        for event in pygame.event.get():
            match event.type:
                case pygame.QUIT:
                    state.go_to(Scene.QUIT)
                    return
                case pygame.MOUSEBUTTONDOWN:
                    match event.button:
                        case 4:
                            scroll_offset = max(0, scroll_offset - 1)
                        case 5:
                            scroll_offset = min(max_scroll, scroll_offset + 1)
                        case _:
                            btn_back.handle_click(mouse_pos)
                case pygame.KEYDOWN:
                    match event.key:
                        case pygame.K_UP:
                            scroll_offset = max(0, scroll_offset - 1)
                        case pygame.K_DOWN:
                            scroll_offset = min(max_scroll, scroll_offset + 1)

        fill_surface(surface)

        title = HEADING_FONT.render("LEADERBOARD", True, TEXT_COLOR)
        surface.blit(title, title.get_rect(center=Grid.pos(6, 1)))

        for col, header in enumerate(Leaderboard.HEADERS):
            txt = TEXT_FONT.render(header, True, ACCENT_COLOR)
            surface.blit(txt, txt.get_rect(center=(Leaderboard.COL_X[col], Leaderboard.ROW_Y[0])))

        visible_entries = entries[scroll_offset : scroll_offset + visible_rows]
        for row, entry in enumerate(visible_entries):
            y = Leaderboard.ROW_Y[row + 1]
            rank = scroll_offset + row + 1
            values = [
                str(rank),
                entry["name"],
                str(entry["dino"]),
                str(entry["pong"]),
                str(entry["wheelchair"]),
                str(entry["total"]),
            ]
            for col, val in enumerate(values):
                txt = SUBTEXT_FONT.render(val, True, TEXT_COLOR)
                surface.blit(txt, txt.get_rect(center=(Leaderboard.COL_X[col], y)))

        if len(entries) > visible_rows:
            indicator = TEXT_FONT.render(
                f"↑↓ {scroll_offset + 1}-{scroll_offset + len(visible_entries)}/{len(entries)}",
                True,
                ACCENT_COLOR,
            )
            surface.blit(indicator, indicator.get_rect(center=Grid.pos(10, 11)))

        btn_back.update(surface, mouse_pos)
        scale_to_screen(surface, screen)
