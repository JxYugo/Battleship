# 2-Player Local Multiplayer Battleship Game

## Dependencies
1. Install pygame (in bash, type `pip install pygame`).
2. Two or more devices for multi-device multiplayer: one server device and two client/player devices.
3. Make sure these files are in the same folder:
   - `battleship_server.py`
   - `battleship_client.py`
   - `battleship_network.py`
   - `run_battleship.py`

## How to run
1. Open PowerShell/CMD and type `ipconfig`. Look for the IPv4 Address.
2. In the server device, open `battleship_server.py`.
3. Make sure the `HOST` is set to `0.0.0.0`.
4. In both player devices, open `battleship_client.py`.
5. Change the client IP from `127.0.0.1` to the server IPv4 Address found in Step 1.
6. Start `battleship_server.py` on the server device.
7. Start `battleship_client.py` on both player devices.
8. Click **START GAME** on both client windows.

## How to Play

1. Each player clicks the **START GAME** button.
2. Each player places 5 ships on the **YOUR FLEET** board.
3. After both players finish placing ships, the server starts the match.
4. During battle, only the player whose status says **YOUR TURN** can click a cell on the **ENEMY RADAR** board to fire a shot.
5. After a shot is fired, the server sends the result to both players.
6. A red X means hit.
7. A white circle means miss.
8. The first player to hit all 5 enemy ships wins.

## How to evaluate performance metrics:

On the terminals where you started the server and the clients:

the server sends a health report every 10 seconds, showing throughput, active players/nodes, and active matches.
the client sends latency/ping information in the terminal every time a shot is fired.

## For Collaborators:

### How to run for testing

This can be run on the same device for testing. This is the easiest testing method because it opens the server and two client windows automatically.

Use the terminal in your IDE to run:

```bash
python run_battleship.py
