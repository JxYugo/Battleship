import socket
import selectors
from battleship_network import GameMessage

HOST = '127.0.0.1'  # 0.0.0.0 for multi-computer play
PORT = 65432


sel = selectors.DefaultSelector()
player_slots = {1: None, 2: None}
player_boards = {}
hits = {1: 0, 2: 0}
WIN_SCORE = 5


def broadcast(msg_obj):
    """Sends a message to all connected players."""
    for conn in list(player_slots.values()):
        if conn:
            try:
                GameMessage.send_msg(conn, msg_obj)
            except:
                pass


def handle_player_data(conn, mask):
    """Parallel event handler for incoming player moves."""

    p_id = None
    for pid, c in player_slots.items():
        if c == conn:
            p_id = pid
            break

    msg = GameMessage.recv_msg(conn)

    if not msg:
        print(f"[DISCONNECT] Player {p_id} left.")
        if p_id:
            player_slots[p_id] = None
            if p_id in player_boards:
                del player_boards[p_id]
        sel.unregister(conn)
        conn.close()
        return

    if msg.msg_type == GameMessage.PLACE_SHIPS:
        player_boards[p_id] = msg.data['grid']
        print(f"[READY] Player {p_id} has placed ships.")

        # Check if both players are ready to start the game
        if len(player_boards) == 2 and None not in player_slots.values():
            print("[START] Both players ready. Starting battle.")
            broadcast(GameMessage(GameMessage.GAME_START, {"turn": 1}))

    elif msg.msg_type == GameMessage.FIRE_SHOT:
        opp_id = 2 if p_id == 1 else 1
        x, y = msg.data['x'], msg.data['y']

        res = "miss"
        if player_boards[opp_id][y][x] == 1:
            res = "hit"
            hits[p_id] += 1

        print(f"[SHOT] Player {p_id} fired at {x},{y}: {res}")

        broadcast(GameMessage(GameMessage.SHOT_RESULT, {
            "p_id": p_id,
            "x": x,
            "y": y,
            "res": res,
            "next": opp_id
        }))

        if hits[p_id] >= WIN_SCORE:
            print(f"[WIN] Player {p_id} has won the game!")
            broadcast(GameMessage(GameMessage.GAME_OVER, {"winner": p_id}))


def accept_connection(sock, mask):
    """Handles new incoming connections and assigns Player IDs."""
    conn, addr = sock.accept()

    p_id = None
    if player_slots[1] is None:
        p_id = 1
    elif player_slots[2] is None:
        p_id = 2

    if p_id is None:
        print(f"[REJECT] Connection from {addr} - Server Full.")
        conn.close()
        return

    print(f"[CONNECT] Assigned Player {p_id} to {addr}")
    conn.setblocking(False)
    player_slots[p_id] = conn
    sel.register(conn, selectors.EVENT_READ, handle_player_data)

    GameMessage.send_msg(conn, GameMessage(GameMessage.INIT_PLAYER, {"id": p_id}))


server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_sock.bind((HOST, PORT))
server_sock.listen()
server_sock.setblocking(False)
sel.register(server_sock, selectors.EVENT_READ, accept_connection)

print(f"Battleship Server active on {HOST}:{PORT}")
try:
    while True:
        events = sel.select(timeout=None)
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)
except KeyboardInterrupt:
    print("\nShutting down server.")
finally:
    sel.close()
    server_sock.close()