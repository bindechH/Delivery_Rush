# Delivery Rush

A multiplayer delivery game built with Python and Pygame.

## Project Structure

- `main.py`: Main client application
- `server.py`: UDP server for multiplayer
- `modules/`: Game modules
  - `config.py`: Game constants and utility functions
  - `ui.py`: User interface (menu, IP input, game UI)
  - `player.py`: Player class and network management
  - `map.py`: Game map rendering
  - `missions.py`: Mission system (placeholder)
  - `sounds.py`: Sound manager (placeholder)
- `assets/`: Game assets (images, sounds)

## Getting Started

1. Install dependencies: `pip install -r requirements.txt`
2. Run the server: `python server.py`
3. Run the client: `python main.py`

## Features

- Top-down delivery gameplay
- Multiplayer support (UDP)
- Dynamic mission generation (planned)
- Vehicle upgrades (planned)
- Enemy AI (planned)