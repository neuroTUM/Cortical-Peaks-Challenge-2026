from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

import pygame

from games.dino.viewer import DinoViewerRenderer
from games.pong.viewer import PongViewerRenderer
from shared.connection.connection_page import run_connections
from shared.connection.protocol import GameType, SessionInfo
from shared.connection.server import get_server
from shared.connection.spectator_client import spectator_client
from shared.constants import (
    ACCENT_COLOR,
    DISABLED_COLOR,
    FPS,
    HEADING_FONT,
    HIGHLIGHT_COLOR,
    STATUS_ERROR_COLOR,
    STATUS_OK_COLOR,
    SUBTEXT_FONT,
    TEXT_COLOR,
    TEXT_FONT,
    TITLE_FONT,
)
from shared.leaderboard import Leaderboard, run_leaderboard
from shared.spectator_connect import run_connect_page
from shared.state import Scene, state
from shared.ui import Button, Grid, fill_surface, init_pygame, mouse_pos_to_surface, scale_to_screen

if TYPE_CHECKING:
    from collections.abc import Callable


def _run_server_launcher(surface: pygame.Surface, screen: pygame.Surface) -> None:
    buttons = [
        Button(Grid.pos(6, 4), "CONNECTIONS", TEXT_FONT, on_click=lambda: state.go_to(Scene.CONNECTION)),
        Button(Grid.pos(6, 6), "LEADERBOARD", TEXT_FONT, on_click=lambda: state.go_to(Scene.LEADERBOARD)),
        Button(Grid.pos(6, 11), "QUIT", TEXT_FONT, on_click=lambda: state.go_to(Scene.QUIT)),
    ]

    while state.scene == Scene.LAUNCHER:
        mouse_pos = mouse_pos_to_surface(screen)

        for event in pygame.event.get():
            match event.type:
                case pygame.QUIT:
                    state.go_to(Scene.QUIT)
                    return
                case pygame.MOUSEBUTTONDOWN:
                    for btn in buttons:
                        btn.handle_click(mouse_pos)

        fill_surface(surface)

        title = TITLE_FONT.render("BCI ARCADE", True, TEXT_COLOR)
        surface.blit(title, title.get_rect(center=Grid.pos(6, 1)))

        server = get_server()
        bci_count = sum(1 for p in server.players.values() if p.bci.is_connected)
        viewer_count = sum(1 for v in server.viewers.values() if v.is_connected)
        status_txt = TEXT_FONT.render(f"{bci_count} BCI  {viewer_count} viewers", True, TEXT_COLOR)
        surface.blit(status_txt, status_txt.get_rect(center=Grid.pos(6, 8)))

        for btn in buttons:
            btn.update(surface, mouse_pos)

        scale_to_screen(surface, screen)


def _run_server_app(surface: pygame.Surface, screen: pygame.Surface) -> None:
    while state.scene != Scene.QUIT:
        match state.scene:
            case Scene.LAUNCHER:
                _run_server_launcher(surface, screen)
            case Scene.LEADERBOARD:
                run_leaderboard(surface, screen)
            case Scene.CONNECTION:
                run_connections(surface, screen)


def _run_spectator_launcher(surface: pygame.Surface, screen: pygame.Surface) -> None:
    buttons = [
        Button(
            Grid.pos(6, 5), "CONNECT TO SERVER", TEXT_FONT, on_click=lambda: state.go_to(Scene.SPECTATOR_CONNECTION)
        ),
        Button(Grid.pos(4, 11), "DISCONNECT", TEXT_FONT, on_click=spectator_client.disconnect),
        Button(Grid.pos(8, 11), "QUIT", TEXT_FONT, on_click=lambda: state.go_to(Scene.QUIT)),
    ]

    while state.scene == Scene.LAUNCHER:
        if spectator_client.connected:
            state.go_to(Scene.SESSION_PICKER)
            return

        mouse_pos = mouse_pos_to_surface(screen)

        for event in pygame.event.get():
            match event.type:
                case pygame.QUIT:
                    state.go_to(Scene.QUIT)
                    return
                case pygame.MOUSEBUTTONDOWN:
                    for btn in buttons:
                        btn.handle_click(mouse_pos)

        fill_surface(surface)

        title = TITLE_FONT.render("BCI ARCADE", True, TEXT_COLOR)
        surface.blit(title, title.get_rect(center=Grid.pos(6, 1)))

        subtitle = SUBTEXT_FONT.render("SPECTATOR MODE", True, ACCENT_COLOR)
        surface.blit(subtitle, subtitle.get_rect(center=Grid.pos(6, 3)))

        color = STATUS_OK_COLOR if spectator_client.connected else STATUS_ERROR_COLOR
        pygame.draw.circle(surface, color, Grid.pos(11, 11), 10)

        for btn in buttons:
            btn.update(surface, mouse_pos)

        scale_to_screen(surface, screen)


def _build_session_row_buttons(
    visible: list[SessionInfo],
    col_x: tuple[int, ...],
    row_y: tuple[int, ...],
    on_spectate: Callable[[str], None],
) -> list[Button]:
    return [
        Button(
            (col_x[1], row_y[i + 1]),
            session.display_name[:12],
            SUBTEXT_FONT,
            on_click=lambda uid=session.uid: on_spectate(uid),
        )
        for i, session in enumerate(visible)
    ]


def _render_session_table(
    surface: pygame.Surface,
    sessions: list[SessionInfo],
    visible: list[SessionInfo],
    row_buttons: list[Button],
    scroll_offset: int,
    col_x: tuple[int, ...],
    row_y: tuple[int, ...],
    visible_rows: int,
    mouse_pos: tuple[int, int],
    headers: list[str],
) -> None:
    for col, header in enumerate(headers):
        txt = SUBTEXT_FONT.render(header, True, ACCENT_COLOR)
        surface.blit(txt, txt.get_rect(center=(col_x[col], row_y[0])))

    if not sessions:
        txt = TEXT_FONT.render("NO ACTIVE SESSIONS", True, DISABLED_COLOR)
        surface.blit(txt, txt.get_rect(center=Grid.pos(6, 5)))
    else:
        for i, (session, row_btn) in enumerate(zip(visible, row_buttons, strict=True)):
            y = row_y[i + 1]
            rank = scroll_offset + i + 1

            txt = SUBTEXT_FONT.render(str(rank), True, TEXT_COLOR)
            surface.blit(txt, txt.get_rect(center=(col_x[0], y)))

            row_btn.text_color = HIGHLIGHT_COLOR if spectator_client.spectating_uid == session.uid else TEXT_COLOR
            row_btn.update(surface, mouse_pos)

            game_label = session.game or "-"
            game_color = ACCENT_COLOR if session.game else DISABLED_COLOR
            txt = SUBTEXT_FONT.render(game_label, True, game_color)
            surface.blit(txt, txt.get_rect(center=(col_x[2], y)))

            bci_color = STATUS_OK_COLOR if session.bci_connected else STATUS_ERROR_COLOR
            pygame.draw.circle(surface, bci_color, (col_x[3], y), 8)

    if len(sessions) > visible_rows:
        indicator = SUBTEXT_FONT.render(
            f"{scroll_offset + 1}-{scroll_offset + len(visible)}/{len(sessions)}",
            True,
            ACCENT_COLOR,
        )
        surface.blit(indicator, indicator.get_rect(center=Grid.pos(6, 10)))


def _handle_scroll_event(event: pygame.event.Event, offset: int, max_scroll: int) -> int:
    match event.type:
        case pygame.MOUSEBUTTONDOWN if event.button == 4:
            return max(0, offset - 1)
        case pygame.MOUSEBUTTONDOWN if event.button == 5:
            return min(max_scroll, offset + 1)
        case pygame.KEYDOWN if event.key == pygame.K_UP:
            return max(0, offset - 1)
        case pygame.KEYDOWN if event.key == pygame.K_DOWN:
            return min(max_scroll, offset + 1)
    return offset


def _run_session_picker(surface: pygame.Surface, screen: pygame.Surface) -> None:
    clock = pygame.time.Clock()

    def go_back() -> None:
        spectator_client.disconnect()
        state.go_back()

    def make_spectate(uid: str) -> None:
        spectator_client.spectate(uid)

    btn_back = Button(Grid.pos(6, 11), "DISCONNECT", TEXT_FONT, on_click=go_back)

    col_x = tuple(Grid.x(i) for i in [1, 4, 7, 9.5, 11])
    row_y = tuple(Grid.y(i) for i in range(2, 10))
    headers = ["#", "PLAYER", "GAME", "BCI", "VIEWERS"]
    visible_rows = 6
    scroll_offset = 0

    while state.scene == Scene.SESSION_PICKER:
        clock.tick(FPS)

        if not spectator_client.connected:
            state.reset_to(Scene.LAUNCHER)
            return

        sessions = spectator_client.sessions
        max_scroll = max(0, len(sessions) - visible_rows)
        scroll_offset = min(scroll_offset, max_scroll)
        visible = sessions[scroll_offset : scroll_offset + visible_rows]

        mouse_pos = mouse_pos_to_surface(screen)

        row_buttons = _build_session_row_buttons(visible, col_x, row_y, make_spectate)

        for event in pygame.event.get():
            scroll_offset = _handle_scroll_event(event, scroll_offset, max_scroll)
            match event.type:
                case pygame.QUIT:
                    state.go_to(Scene.QUIT)
                    return
                case pygame.MOUSEBUTTONDOWN if event.button not in (4, 5):
                    btn_back.handle_click(mouse_pos)
                    for btn in row_buttons:
                        btn.handle_click(mouse_pos)
                case pygame.KEYDOWN if event.key == pygame.K_ESCAPE:
                    go_back()
                    return

        if (
            spectator_client.spectating_game in (GameType.DINO, GameType.DINO_JUMP)
            and spectator_client.latest_dino_state
        ):
            state.go_to(Scene.DINO_GAME)
            return
        if spectator_client.spectating_game in (GameType.PONG, GameType.PONG_AI) and spectator_client.latest_pong_state:
            state.go_to(Scene.PONG_GAME)
            return

        fill_surface(surface)

        title = TITLE_FONT.render("SESSIONS", True, TEXT_COLOR)
        surface.blit(title, title.get_rect(center=Grid.pos(6, 1)))

        color = STATUS_OK_COLOR if spectator_client.connected else STATUS_ERROR_COLOR
        pygame.draw.circle(surface, color, Grid.pos(11.5, 1), 8)

        if spectator_client.spectating_uid and not spectator_client.spectating_game:
            waiting = SUBTEXT_FONT.render(
                f"Waiting for game: {spectator_client.spectating_uid}...", True, HIGHLIGHT_COLOR
            )
            surface.blit(waiting, waiting.get_rect(center=Grid.pos(6, 9.5)))

        _render_session_table(
            surface, sessions, visible, row_buttons, scroll_offset, col_x, row_y, visible_rows, mouse_pos, headers
        )

        btn_back.update(surface, mouse_pos)
        scale_to_screen(surface, screen)


def _draw_keep_watching_overlay(surface: pygame.Surface) -> None:
    """Draw the keep-watching status hint onto the logical surface.

    Drawn as part of the frame (before it is scaled and flipped) so there is a single present per
    frame and the hint does not flicker. Game renderers receive this via an overlay hook, so they
    stay unaware of spectator controls.
    """
    on = spectator_client.keep_watching
    label = "KEEP WATCHING: ON  (K)" if on else "KEEP WATCHING: OFF  (K)"
    color = STATUS_OK_COLOR if on else DISABLED_COLOR
    txt = SUBTEXT_FONT.render(label, True, color)
    surface.blit(txt, txt.get_rect(midleft=(Grid.x(0.3), Grid.y(11.3))))


def _run_dino_game(surface: pygame.Surface, screen: pygame.Surface) -> None:
    clock = pygame.time.Clock()
    renderer = DinoViewerRenderer()

    while state.scene == Scene.DINO_GAME:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                state.go_to(Scene.QUIT)
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                spectator_client.stop_watching()
                state.reset_to(Scene.SESSION_PICKER)
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_k:
                spectator_client.toggle_keep_watching()

        if not spectator_client.connected:
            state.reset_to(Scene.LAUNCHER)
            return

        # The watched player switched to Pong while we were following them.
        if spectator_client.spectating_game in (GameType.PONG, GameType.PONG_AI) and spectator_client.latest_pong_state:
            state.go_to(Scene.PONG_GAME)
            return

        game_state = spectator_client.latest_dino_state

        # When keeping watch, treat the finished run as 'wait for the next game' instead of leaving.
        if (
            spectator_client.keep_watching
            and game_state is not None
            and (game_state.game_over or game_state.time_left <= 0)
        ):
            spectator_client.await_next_game()
            game_state = None

        if game_state is None:
            fill_surface(surface)
            message = "Waiting for next game..." if spectator_client.keep_watching else "Waiting for game state..."
            txt = TEXT_FONT.render(message, True, TEXT_COLOR)
            surface.blit(txt, txt.get_rect(center=Grid.pos(6, 5)))
            _draw_keep_watching_overlay(surface)
            scale_to_screen(surface, screen)
            continue

        if game_state.game_over or game_state.time_left <= 0:
            state.username_one = game_state.username
            state.score_one = game_state.score
            spectator_client.stop_watching()
            state.go_to(Scene.LEADERBOARD)
            return

        if game_state.countdown > 0:
            fill_surface(surface)
            txt = HEADING_FONT.render(f"Game starting in {int(game_state.countdown) + 1}...", True, TEXT_COLOR)
            surface.blit(txt, txt.get_rect(center=Grid.pos(6, 5)))
            _draw_keep_watching_overlay(surface)
            scale_to_screen(surface, screen)
            continue

        renderer.render_frame(surface, screen, game_state, overlay=_draw_keep_watching_overlay)


def _run_spectator_leaderboard(surface: pygame.Surface, screen: pygame.Surface) -> None:
    entries = Leaderboard.snapshot()

    # Build a one-line result summary from whatever game just finished
    if state.winner:
        winner_name = state.username_one if state.winner == 1 else state.username_two
        result_line = (
            f"{winner_name} WINS!  {state.username_one} {state.score_one} — {state.username_two} {state.score_two}"
        )
    else:
        result_line = f"{state.username_one}: {state.score_one}" if state.username_one else ""

    col_x = tuple(Grid.x(i) for i in [0.75, 2.5, 5, 7, 9, 11])
    row_y = tuple(Grid.y(i) for i in range(3, 11))
    headers = ["#", "NAME", "DINO", "PONG", "CHAIR", "TOTAL"]
    visible_rows = 6
    scroll_offset = 0
    max_scroll = max(0, len(entries) - visible_rows)

    def watch_another() -> None:
        state.reset_to(Scene.SESSION_PICKER)

    def disconnect() -> None:
        spectator_client.disconnect()
        state.reset_to(Scene.LAUNCHER)

    btn_watch = Button(Grid.pos(4, 11), "WATCH ANOTHER", TEXT_FONT, on_click=watch_another)
    btn_disconnect = Button(Grid.pos(8, 11), "DISCONNECT", TEXT_FONT, on_click=disconnect)

    while state.scene == Scene.LEADERBOARD:
        mouse_pos = mouse_pos_to_surface(screen)

        for event in pygame.event.get():
            scroll_offset = _handle_scroll_event(event, scroll_offset, max_scroll)
            match event.type:
                case pygame.QUIT:
                    state.go_to(Scene.QUIT)
                    return
                case pygame.MOUSEBUTTONDOWN if event.button not in (4, 5):
                    btn_watch.handle_click(mouse_pos)
                    btn_disconnect.handle_click(mouse_pos)

        fill_surface(surface)

        title = HEADING_FONT.render("LEADERBOARD", True, TEXT_COLOR)
        surface.blit(title, title.get_rect(center=Grid.pos(6, 1)))

        if result_line:
            result_txt = SUBTEXT_FONT.render(result_line, True, ACCENT_COLOR)
            surface.blit(result_txt, result_txt.get_rect(center=Grid.pos(6, 2)))

        for col, header in enumerate(headers):
            txt = TEXT_FONT.render(header, True, ACCENT_COLOR)
            surface.blit(txt, txt.get_rect(center=(col_x[col], row_y[0])))

        visible_entries = entries[scroll_offset : scroll_offset + visible_rows]
        for row, entry in enumerate(visible_entries):
            y = row_y[row + 1]
            rank = scroll_offset + row + 1
            for col, val in enumerate(
                [
                    str(rank),
                    entry["name"],
                    str(entry["dino"]),
                    str(entry["pong"]),
                    str(entry["wheelchair"]),
                    str(entry["total"]),
                ]
            ):
                txt = SUBTEXT_FONT.render(val, True, TEXT_COLOR)
                surface.blit(txt, txt.get_rect(center=(col_x[col], y)))

        if len(entries) > visible_rows:
            indicator = SUBTEXT_FONT.render(
                f"↑↓ {scroll_offset + 1}-{scroll_offset + len(visible_entries)}/{len(entries)}",
                True,
                ACCENT_COLOR,
            )
            surface.blit(indicator, indicator.get_rect(center=Grid.pos(11, 11)))

        btn_watch.update(surface, mouse_pos)
        btn_disconnect.update(surface, mouse_pos)
        scale_to_screen(surface, screen)


def _run_pong_game(surface: pygame.Surface, screen: pygame.Surface) -> None:
    clock = pygame.time.Clock()
    renderer = PongViewerRenderer()

    while state.scene == Scene.PONG_GAME:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                state.go_to(Scene.QUIT)
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                spectator_client.stop_watching()
                state.reset_to(Scene.SESSION_PICKER)
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_k:
                spectator_client.toggle_keep_watching()

        if not spectator_client.connected:
            state.reset_to(Scene.LAUNCHER)
            return

        # The watched player switched to Dino while we were following them.
        if (
            spectator_client.spectating_game in (GameType.DINO, GameType.DINO_JUMP)
            and spectator_client.latest_dino_state
        ):
            state.go_to(Scene.DINO_GAME)
            return

        pong_state = spectator_client.latest_pong_state

        # When keeping watch, treat the finished match as 'wait for the next game' instead of leaving.
        if spectator_client.keep_watching and pong_state is not None and pong_state.game_over:
            spectator_client.await_next_game()
            pong_state = None

        if pong_state is None:
            fill_surface(surface)
            message = "Waiting for next game..." if spectator_client.keep_watching else "Waiting for match..."
            txt = TEXT_FONT.render(message, True, TEXT_COLOR)
            surface.blit(txt, txt.get_rect(center=Grid.pos(6, 5)))
            _draw_keep_watching_overlay(surface)
            scale_to_screen(surface, screen)
            continue

        if pong_state.game_over:
            state.username_one = pong_state.player1_name
            state.username_two = pong_state.player2_name
            state.score_one = pong_state.score_left
            state.score_two = pong_state.score_right
            state.winner = pong_state.winner
            spectator_client.stop_watching()
            state.go_to(Scene.LEADERBOARD)
            return

        renderer.render_frame(surface, screen, pong_state, overlay=_draw_keep_watching_overlay)


def _run_spectator_app(surface: pygame.Surface, screen: pygame.Surface) -> None:
    while state.scene != Scene.QUIT:
        match state.scene:
            case Scene.LAUNCHER:
                _run_spectator_launcher(surface, screen)
            case Scene.SPECTATOR_CONNECTION:
                run_connect_page(surface, screen)
            case Scene.SESSION_PICKER:
                _run_session_picker(surface, screen)
            case Scene.DINO_GAME:
                _run_dino_game(surface, screen)
            case Scene.PONG_GAME:
                _run_pong_game(surface, screen)
            case Scene.LEADERBOARD:
                _run_spectator_leaderboard(surface, screen)
            case _:
                state.reset_to(Scene.LAUNCHER)


def main_server() -> None:
    surface, screen = init_pygame("BCI ARCADE - Server")
    _ = get_server()  # eager init: server thread must be alive before the UI loop starts
    _run_server_app(surface, screen)
    pygame.quit()


def main_spectator() -> None:
    surface, screen = init_pygame("BCI ARCADE - Spectator")
    _run_spectator_app(surface, screen)
    pygame.quit()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="cpc", description="Cortical Peaks Challenge 2026 launcher")
    parser.add_argument(
        "--target",
        choices=["server", "spectator"],
        required=True,
        help="Which mode to launch: 'server' (game authority) or 'spectator' (display client)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument(
        "--audit", action="store_true", help="Write a JSON Lines audit log of server events to data/audit/"
    )
    return parser.parse_args()
