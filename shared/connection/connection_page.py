from __future__ import annotations

import time
from dataclasses import dataclass
from typing import ClassVar

import pygame

from shared.connection.protocol import GameType
from shared.connection.server import Player, get_server
from shared.constants import (
    ACCENT_COLOR,
    DISABLED_COLOR,
    HIGHLIGHT_COLOR,
    STATUS_ERROR_COLOR,
    STATUS_OK_COLOR,
    SUBTEXT_FONT,
    TEXT_COLOR,
    TEXT_FONT,
    TITLE_FONT,
)
from shared.state import Scene, state
from shared.ui import Button, Grid, fill_surface, mouse_pos_to_surface, scale_to_screen


@dataclass
class _Entry:
    uid: str
    name: str
    game: str
    in_match: bool
    bci: bool
    viewer_count: int


class ConnectionPage:
    HEADERS: ClassVar[list[str]] = ["#", "NAME", "GAME", "BCI", "VIEW", "BSDJ", "BSJ", "PVP", "AI"]
    COL_X: ClassVar[tuple[int, ...]] = tuple(Grid.x(i) for i in [1, 2.3, 5, 6.6, 7.7, 8.7, 9.7, 10.7, 11.6])
    ROW_Y: ClassVar[tuple[int, ...]] = tuple(Grid.y(i) for i in range(2, 10))
    DOT_R: ClassVar[int] = 8

    entries: list[_Entry]

    def __init__(self) -> None:
        self.entries = []

    def update(self, players: list[Player], viewers_for: dict[str, int]) -> None:
        self.entries = sorted(
            [
                _Entry(
                    uid=player.bci_token,
                    name=player.display_name,
                    game=player.game.value if player.game else "",
                    in_match=player.in_match,
                    bci=player.bci.is_connected,
                    viewer_count=viewers_for.get(player.bci_token, 0),
                )
                for player in players
            ],
            key=lambda e: e.name,
        )


def run_connections(surface: pygame.Surface, screen: pygame.Surface) -> None:
    game_srv = get_server()
    connection_page = ConnectionPage()
    scroll_offset = 0
    visible_rows = 6
    pong_staging: set[str] = set()

    def make_dino_cb(u: str) -> None:
        pong_staging.discard(u)
        game_srv.start_game(u, GameType.DINO)

    def make_dino_jump_cb(u: str) -> None:
        pong_staging.discard(u)
        game_srv.start_game(u, GameType.DINO_JUMP)

    def make_pong_ai_cb(u: str) -> None:
        pong_staging.discard(u)
        game_srv.start_game(u, GameType.PONG_AI)

    def toggle_pong(u: str) -> None:
        if u in pong_staging:
            pong_staging.discard(u)
        else:
            pong_staging.add(u)
            if len(pong_staging) == 2:
                for staged_uid in list(pong_staging):
                    game_srv.start_game(staged_uid, GameType.PONG)
                pong_staging.clear()

    btn_back = Button(Grid.pos(6, 11), "BACK", TEXT_FONT, on_click=state.go_back)

    while state.scene == Scene.CONNECTION:
        now = time.time()
        players_snapshot, viewers_snapshot = game_srv.snapshot_players_viewers()
        players = players_snapshot
        viewers_for = {
            player.bci_token: sum(
                1
                for v in viewers_snapshot.values()
                if v.watching == player.bci_token and now - v.last_seen <= game_srv.timeout.total_seconds()
            )
            for player in players_snapshot
        }
        connection_page.update(players, viewers_for)
        max_scroll = max(0, len(connection_page.entries) - visible_rows)
        scroll_offset = min(scroll_offset, max_scroll)

        # Remove staged players that are no longer eligible (disconnected, in game, etc.)
        eligible_uids = {e.uid for e in connection_page.entries if e.bci and not e.in_match and not e.game}
        pong_staging &= eligible_uids

        mouse_pos = mouse_pos_to_surface(screen)

        # Build per-row action buttons for visible entries
        visible_entries = connection_page.entries[scroll_offset : scroll_offset + visible_rows]
        row_buttons: list[tuple[Button, Button, Button, Button]] = []
        for row, entry in enumerate(visible_entries):
            y = ConnectionPage.ROW_Y[row + 1]
            uid = entry.uid
            bci_ok = entry.bci
            dino_ready = bci_ok and not entry.in_match
            game_eligible = bci_ok and not entry.in_match and not entry.game

            dino_btn = Button(
                (ConnectionPage.COL_X[5], y),
                "BSDJ",
                SUBTEXT_FONT,
                on_click=(lambda u=uid: make_dino_cb(u)) if dino_ready else None,
            )
            jump_btn = Button(
                (ConnectionPage.COL_X[6], y),
                "BSJ",
                SUBTEXT_FONT,
                on_click=(lambda u=uid: make_dino_jump_cb(u)) if dino_ready else None,
            )
            pong_btn = Button(
                (ConnectionPage.COL_X[7], y),
                "P",
                SUBTEXT_FONT,
                on_click=(lambda u=uid: toggle_pong(u)) if game_eligible else None,
            )
            ai_btn = Button(
                (ConnectionPage.COL_X[8], y),
                "A",
                SUBTEXT_FONT,
                on_click=(lambda u=uid: make_pong_ai_cb(u)) if game_eligible else None,
            )
            row_buttons.append((dino_btn, jump_btn, pong_btn, ai_btn))

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
                            for dino_btn, jump_btn, pong_btn, ai_btn in row_buttons:
                                dino_btn.handle_click(mouse_pos)
                                jump_btn.handle_click(mouse_pos)
                                pong_btn.handle_click(mouse_pos)
                                ai_btn.handle_click(mouse_pos)
                case pygame.KEYDOWN:
                    match event.key:
                        case pygame.K_UP:
                            scroll_offset = max(0, scroll_offset - 1)
                        case pygame.K_DOWN:
                            scroll_offset = min(max_scroll, scroll_offset + 1)

        fill_surface(surface)

        title = TITLE_FONT.render("CONNECTIONS", True, TEXT_COLOR)
        surface.blit(title, title.get_rect(center=Grid.pos(6, 1)))

        # Summary bottom-right, to the right of the BACK button
        bci_ready = sum(1 for e in connection_page.entries if e.bci)
        total = len(connection_page.entries)
        viewer_total = sum(e.viewer_count for e in connection_page.entries)
        summary_color = STATUS_OK_COLOR if bci_ready == total and total > 0 else ACCENT_COLOR
        summary = SUBTEXT_FONT.render(f"{bci_ready}/{total} BCI  {viewer_total} viewers", True, summary_color)
        surface.blit(summary, summary.get_rect(midright=(Grid.x(11.75), Grid.y(11))))

        # Column headers
        for col, header in enumerate(ConnectionPage.HEADERS):
            txt = SUBTEXT_FONT.render(header, True, ACCENT_COLOR)
            surface.blit(txt, txt.get_rect(center=(ConnectionPage.COL_X[col], ConnectionPage.ROW_Y[0])))

        if not visible_entries:
            no_conn = TEXT_FONT.render("NO CONNECTIONS", True, DISABLED_COLOR)
            surface.blit(no_conn, no_conn.get_rect(center=Grid.pos(6, 5)))
        else:
            for row, (entry, (dino_btn, jump_btn, pong_btn, ai_btn)) in enumerate(
                zip(visible_entries, row_buttons, strict=True)
            ):
                y = ConnectionPage.ROW_Y[row + 1]
                rank = scroll_offset + row + 1

                txt = SUBTEXT_FONT.render(str(rank), True, TEXT_COLOR)
                surface.blit(txt, txt.get_rect(center=(ConnectionPage.COL_X[0], y)))

                txt = SUBTEXT_FONT.render(entry.name[:10], True, TEXT_COLOR)
                surface.blit(txt, txt.get_rect(center=(ConnectionPage.COL_X[1], y)))

                game_label = entry.game or "-"
                game_color = HIGHLIGHT_COLOR if entry.in_match else (TEXT_COLOR if entry.game else DISABLED_COLOR)
                txt = SUBTEXT_FONT.render(game_label, True, game_color)
                surface.blit(txt, txt.get_rect(center=(ConnectionPage.COL_X[2], y)))

                pygame.draw.circle(
                    surface,
                    STATUS_OK_COLOR if entry.bci else STATUS_ERROR_COLOR,
                    (ConnectionPage.COL_X[3], y),
                    ConnectionPage.DOT_R,
                )

                vc = str(entry.viewer_count)
                vc_color = STATUS_OK_COLOR if entry.viewer_count > 0 else DISABLED_COLOR
                txt = SUBTEXT_FONT.render(vc, True, vc_color)
                surface.blit(txt, txt.get_rect(center=(ConnectionPage.COL_X[4], y)))

                dino_btn.update(surface, mouse_pos)
                jump_btn.update(surface, mouse_pos)
                pong_btn.update(surface, mouse_pos)
                ai_btn.update(surface, mouse_pos)
                if entry.uid in pong_staging:
                    pygame.draw.rect(surface, ACCENT_COLOR, pong_btn.text_rect.inflate(12, 8), 2)

        if len(connection_page.entries) > visible_rows:
            indicator = SUBTEXT_FONT.render(
                f"{scroll_offset + 1}-{scroll_offset + len(visible_entries)}/{len(connection_page.entries)}",
                True,
                ACCENT_COLOR,
            )
            surface.blit(indicator, indicator.get_rect(center=Grid.pos(10, 11)))

        btn_back.update(surface, mouse_pos)
        scale_to_screen(surface, screen)
