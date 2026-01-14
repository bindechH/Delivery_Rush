import pygame
import sys
from modules import (
    MainMenu, Player, GameMap, GameUI, NetworkClient
)

# Server Configuration
SERVER_IP = '25.51.179.140'  # Use '127.0.0.1' for local testing, '25.51.179.140' for remote
SERVER_PORT = 12345
USERNAME = 'marwane'
CAR = ('SEDAN TOPDOWN', 'Black')

# Game States
MENU = 0
GAME = 1

# Screen Constants
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

def _init_networking():
    """Initialize network client and perform handshake."""
    print(f"[NET] Connecting to {SERVER_IP}:{SERVER_PORT} as {USERNAME}")
    client = NetworkClient(SERVER_IP, SERVER_PORT)
    ok, reason = client.connect(USERNAME, CAR)
    if not ok:
        print(f"[NET] Connect failed: {reason}")
        return None, reason
    print("[NET] Handshake complete, multiplayer ready")
    return client, 'ok'


def _send_player_position(network_client, player, username):
    """Send player position and username to server."""
    network_client.send_state(player)


def _receive_player_positions(network_client, other_players_dict, username):
    """Receive and update positions and usernames from server."""
    success, positions = network_client.receive_states()
    if success is False:
        return False
    if success is True:
        other_players_dict.clear()
        other_players_dict.update(positions)
    return True


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Delivery Rush")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 48)
    small_font = pygame.font.SysFont(None, 36)

    # Initialize components
    menu = MainMenu(screen, font, small_font, SCREEN_WIDTH, SCREEN_HEIGHT, SERVER_IP)
    game_map = GameMap()
    game_ui = None

    # Game state variables
    state = MENU
    multiplayer = False
    running = True

    # Networking variables
    network_client = None
    other_players = {}
    connection_errors = 0
    MAX_CONNECTION_ERRORS = 3  # Disconnect after 3 consecutive errors

    while running:
        events = pygame.event.get()

        for event in events:
            if event.type == pygame.QUIT:
                running = False

        if state == MENU:
            solo_rect, multi_rect = menu.display_menu()

            for event in events:
                new_state, new_multiplayer = menu.handle_menu_input(event, solo_rect, multi_rect)
                if new_state is not None:
                    if new_multiplayer is not None:
                        multiplayer = new_multiplayer
                        if multiplayer:
                            if network_client is None:
                                network_client, reason = _init_networking()
                            if network_client:
                                state = new_state
                            else:
                                menu.show_error = True
                                menu.error_message = f"Connect failed: {reason}"
                                multiplayer = False
                                network_client = None
                        else:
                            state = new_state
                            print("[GAME] Starting solo game")
                    else:
                        state = new_state
                        print("[GAME] Starting solo game")

        elif state == GAME:
            if game_ui is None:
                print(f"[GAME] Entering GAME state, multiplayer={multiplayer}")
                game_ui = GameUI(screen, font, small_font, Player(CAR), game_map, other_players, SCREEN_WIDTH, SCREEN_HEIGHT, USERNAME)
            
            if game_ui:
                game_ui.handle_events(events)
                # Check for ESC key to return to menu
                for event in events:
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        print("[GAME] ESC pressed, returning to menu")
                        state = MENU
                        game_ui = None
                        multiplayer = False
                        other_players.clear()
                        if network_client:
                            network_client.close()
                            network_client = None
                        break
                
                if state == GAME:  # Only update if still in game
                    game_ui.update(pygame.key.get_pressed())
                    # Handle multiplayer networking
                    if multiplayer and network_client:
                        _send_player_position(network_client, game_ui.player, USERNAME)
                        if _receive_player_positions(network_client, other_players, USERNAME):
                            connection_errors = 0
                        else:
                            connection_errors += 1
                            if connection_errors >= MAX_CONNECTION_ERRORS:
                                # Server disconnected, return to menu
                                print("[NET] Too many receive errors, dropping to menu")
                                state = MENU
                                game_ui = None
                                multiplayer = False
                                other_players.clear()
                                if network_client:
                                    network_client.close()
                                    network_client = None
                                menu.show_error = True
                                menu.error_message = "Disconnected from server!"
                    if game_ui:
                        game_ui.render()

        pygame.display.flip()
        clock.tick(FPS)

    # Cleanup
    if network_client:
        network_client.close()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()