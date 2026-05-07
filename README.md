# 2-Player Local Multiplayer Battleship Game

## Dependencies
1. Install pygame (in bash, type 'pip install pygame').
2. TTwo devices for multi-device multiplayer (1 clients, 1 client and server).

## How to run
1. Open PowerShell/CMD and type ipconfig. Look for the IPv4 Address.
2. In server device, open battleship_server.py.
3. Change the HOST to 0.0.0.0.
4. In both the server device and the second player device, change battleship_client.py IP (127.0.0.1) to point to the Server's IP address found in Step 1.
5. Start battleship_server.py on server device.
6. Start battleship_client.py on both devices.

## How to Play
1. Players take turns placing ships on the board.
2. After players are done placing ships, they take turns firing on the board.
3. The first player to hit all the opposing player's ships wins.
