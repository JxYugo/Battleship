import json
import struct

class GameMessage:
    INIT_PLAYER = "INIT_PLAYER"
    PLACE_SHIPS = "PLACE_SHIPS"
    GAME_START  = "GAME_START"
    FIRE_SHOT   = "FIRE_SHOT"
    SHOT_RESULT = "SHOT_RESULT"
    GAME_OVER   = "GAME_OVER"
    ERROR       = "ERROR"

    def __init__(self, msg_type, data=None):
        self.msg_type = msg_type
        self.data = data if data is not None else {}

    def to_json(self):
        return json.dumps({"type": self.msg_type, "data": self.data}).encode('utf-8')

    @classmethod
    def from_json(cls, json_bytes):
        msg_dict = json.loads(json_bytes.decode('utf-8'))
        return cls(msg_dict["type"], msg_dict["data"])

    @staticmethod
    def send_msg(sock, message_obj):
        msg_bytes = message_obj.to_json()
        sock.sendall(struct.pack('>I', len(msg_bytes)) + msg_bytes)

    @staticmethod
    def recv_msg(sock):
        try:
            raw_len = sock.recv(4)
            if not raw_len: return None
            msg_len = struct.unpack('>I', raw_len)[0]
            chunks = []
            bytes_recvd = 0
            while bytes_recvd < msg_len:
                chunk = sock.recv(min(msg_len - bytes_recvd, 2048))
                if not chunk: return None
                chunks.append(chunk)
                bytes_recvd += len(chunk)
            return GameMessage.from_json(b''.join(chunks))
        except: return None