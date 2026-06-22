import pygame

from shared.connection.spectator_client import spectator_client
from shared.constants import TEXT_COLOR, TEXT_FONT, TITLE_FONT
from shared.state import Scene, state
from shared.ui import Button, Grid, TextInput, fill_surface, mouse_pos_to_surface, scale_to_screen


def run_connect_page(surface: pygame.Surface, screen: pygame.Surface) -> None:
    text_input_ip = TextInput(Grid.pos(6, 4), TEXT_FONT, "SERVER IP", "127.0.0.1", max_length=15)
    text_input_port = TextInput(Grid.pos(6, 6), TEXT_FONT, "PORT", "5000", max_length=5)
    text_input_ip.active = True  # IP focused first; clicking a field switches focus

    def connect() -> None:
        ip = text_input_ip.get_text()
        try:
            port = int(text_input_port.get_text())
        except ValueError:
            return
        spectator_client.update_server_address(ip, port)
        spectator_client.connect()

    buttons = [
        Button(Grid.pos(2, 11), "BACK", TEXT_FONT, on_click=state.go_back),
        Button(Grid.pos(6, 8), "CONNECT", TEXT_FONT, on_click=connect),
        Button(Grid.pos(10, 11), "QUIT", TEXT_FONT, on_click=lambda: state.go_to(Scene.QUIT)),
    ]

    while state.scene == Scene.SPECTATOR_CONNECTION:
        # Auto-advance to session picker once connected
        if spectator_client.connected:
            state.go_to(Scene.SESSION_PICKER)
            return

        mouse_pos = mouse_pos_to_surface(screen)

        for event in pygame.event.get():
            text_input_ip.handle_event(event)
            text_input_port.handle_event(event)

            match event.type:
                case pygame.QUIT:
                    state.go_to(Scene.QUIT)
                    return
                case pygame.MOUSEBUTTONDOWN:
                    text_input_ip.handle_click(mouse_pos)
                    text_input_port.handle_click(mouse_pos)
                    for btn in buttons:
                        btn.handle_click(mouse_pos)

        fill_surface(surface)

        title = TITLE_FONT.render("CONNECT TO SERVER", True, TEXT_COLOR)
        surface.blit(title, title.get_rect(center=Grid.pos(6, 1)))

        color = (0, 255, 0) if spectator_client.connected else (255, 0, 0)
        pygame.draw.circle(surface, color, Grid.pos(6, 9), 10)

        text_input_ip.update(surface, mouse_pos)
        text_input_port.update(surface, mouse_pos)
        for btn in buttons:
            btn.update(surface, mouse_pos)

        scale_to_screen(surface, screen)
