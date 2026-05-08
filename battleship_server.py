import socket
import selectors
import time
from collections import deque
from battleship_network import GameMessage

HOST = '0.0.0.0'
PORT = 65432
sel = selectors.DefaultSelector()

active_matches = {}
addr_map = {}
lobby_queue = deque()
loop_count = 0
last_report_time = time.time()

class GameMatch:
    def __init__(self, p1_conn, p2_conn):
        self.players = {1: p1_conn, 2: p2_conn}
        self.boards = {}
        self.hits = {1: 0, 2: 0}
        self.win_score = 5
        self.started = False

    def get_opponent_id(self, p_id):
        return 2 if p_id == 1 else 1

    def broadcast(self, msg_obj):
        for conn in self.players.values():
            try:
                GameMessage.send_msg(conn, msg_obj)
            except:
                pass

def cleanup_connection(conn):
    addr = addr_map.get(conn, "Unknown Node")
    print(f"[DISCONNECT] Cleaning up {addr}")

    if conn in lobby_queue:
        lobby_queue.remove(conn)

    if conn in active_matches:
        match = active_matches[conn]
        opp_id = 1 if match.players[2] == conn else 2
        opp_conn = match.players[opp_id]

        try:
            GameMessage.send_msg(opp_conn, GameMessage(GameMessage.ERROR, {"msg": "Opponent Disconnected."}))
        except:
            pass

        active_matches.pop(match.players[1], None)
        active_matches.pop(match.players[2], None)

    try:
        sel.unregister(conn)
    except:
        pass
    conn.close()
    addr_map.pop(conn, None)


def handle_player_data(conn, mask):
    msg = GameMessage.recv_msg(conn)

    if not msg:
        cleanup_connection(conn)
        return

    match = active_matches.get(conn)
    if not match: return

    p_id = 1 if match.players[1] == conn else 2
    opp_id = match.get_opponent_id(p_id)

    if msg.msg_type == GameMessage.PLACE_SHIPS:
        match.boards[p_id] = msg.data['grid']
        if len(match.boards) == 2:
            match.started = True
            match.broadcast(GameMessage(GameMessage.GAME_START, {"turn": 1}))

    elif msg.msg_type == GameMessage.FIRE_SHOT and match.started:
        x, y = msg.data['x'], msg.data['y']
        res = "hit" if match.boards[opp_id][y][x] == 1 else "miss"
        if res == "hit": match.hits[p_id] += 1

        match.broadcast(GameMessage(GameMessage.SHOT_RESULT, {
            "p_id": p_id, "x": x, "y": y, "res": res, "next": opp_id
        }))

        if match.hits[p_id] >= match.win_score:
            match.broadcast(GameMessage(GameMessage.GAME_OVER, {"winner": p_id}))

def accept_connection(sock, mask):
    conn, addr = sock.accept()
    conn.setblocking(False)
    addr_str = f"{addr[0]}:{addr[1]}"
    addr_map[conn] = addr_str

    print(f"[CONNECT] {addr_str} joined the lobby.")
    sel.register(conn, selectors.EVENT_READ, handle_player_data)
    lobby_queue.append(conn)

    if len(lobby_queue) >= 2:
        p1 = lobby_queue.popleft()
        p2 = lobby_queue.popleft()
        new_match = GameMatch(p1, p2)
        active_matches[p1] = new_match
        active_matches[p2] = new_match

        GameMessage.send_msg(p1, GameMessage(GameMessage.INIT_PLAYER, {"id": 1}))
        GameMessage.send_msg(p2, GameMessage(GameMessage.INIT_PLAYER, {"id": 2}))
        print(f"[MATCH] Created Game for {addr_map[p1]} and {addr_map[p2]}")
    else:
        GameMessage.send_msg(conn, GameMessage(GameMessage.INIT_PLAYER, {"id": 0}))

server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_sock.bind((HOST, PORT))
server_sock.listen()
server_sock.setblocking(False)
sel.register(server_sock, selectors.EVENT_READ, accept_connection)

print(f"Battleship Server active on {PORT}...")
try:
    while True:
        loop_count += 1
        current_time = time.time()

        if current_time - last_report_time >= 10:
            avg_ticks = loop_count / (current_time - last_report_time)
            active_p = len(addr_map)
            active_m = len(active_matches) // 2

            print(f"\n--- SERVER HEALTH REPORT ---")
            print(f"Throughput: {avg_ticks:.2f} ticks/sec")
            print(f"Load: {active_p} Players | {active_m} Active Matches")
            print(f"----------------------------\n")

            loop_count = 0
            last_report_time = current_time

        for key, mask in sel.select(timeout=1.0):
            key.data(key.fileobj, mask)
except KeyboardInterrupt:
    pass
finally:
    sel.close()