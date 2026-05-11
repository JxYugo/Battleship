import pygame, socket, threading, queue, time, math, sys, os
from battleship_network import GameMessage

pygame.init()
pygame.mixer.init()

CELL = 40
GRID_SIZE = 10
DIM = CELL * GRID_SIZE
MARGIN = 28
TOP_BAR = 92
BOTTOM_BAR = 95
WIDTH = DIM * 2 + MARGIN * 3
HEIGHT = DIM + TOP_BAR + BOTTOM_BAR
FPS = 60

if "BATTLESHIP_WINDOW_POS" in os.environ:
    os.environ["SDL_VIDEO_WINDOW_POS"] = os.environ["BATTLESHIP_WINDOW_POS"]

SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Battleship: Local Multiplayer")
CLOCK = pygame.time.Clock()

STATE_HOME = -1
STATE_CONNECTING = 0
STATE_PLACING = 1
STATE_WAITING_START = 2
STATE_PLAYING = 3
STATE_GAME_OVER = 4

COLORS = {
    "bg_top": (6, 18, 34),
    "bg_bottom": (5, 35, 58),
    "panel": (12, 36, 60),
    "panel_border": (64, 190, 220),
    "sea": (22, 83, 126),
    "sea_alt": (28, 98, 145),
    "grid_line": (7, 25, 42),
    "ship": (135, 145, 155),
    "ship_glow": (190, 205, 215),
    "hit": (255, 70, 55),
    "hit_glow": (255, 170, 70),
    "miss": (220, 235, 245),
    "text": (235, 245, 255),
    "muted": (150, 178, 198),
    "accent": (0, 210, 255),
    "accent_2": (255, 190, 45),
    "success": (70, 255, 145),
}

FONT_TITLE = pygame.font.Font(None, 58)
FONT_HEAD = pygame.font.Font(None, 34)
FONT_BODY = pygame.font.Font(None, 25)
FONT_SMALL = pygame.font.Font(None, 20)
FONT_TINY = pygame.font.Font(None, 17)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def draw_text(surface, text, font, color, pos, center=False):
    img = font.render(str(text), True, color)
    rect = img.get_rect()
    rect.center = pos if center else rect.center
    if not center:
        rect.topleft = pos
    surface.blit(img, rect)
    return rect


def draw_round_rect(surface, rect, color, radius=14, border_color=None, border_width=2):
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border_color:
        pygame.draw.rect(surface, border_color, rect, border_width, border_radius=radius)


def draw_vertical_gradient(surface, top_color, bottom_color):
    for y in range(HEIGHT):
        t = y / HEIGHT
        r = int(top_color[0] * (1 - t) + bottom_color[0] * t)
        g = int(top_color[1] * (1 - t) + bottom_color[1] * t)
        b = int(top_color[2] * (1 - t) + bottom_color[2] * t)
        pygame.draw.line(surface, (r, g, b), (0, y), (WIDTH, y))


class BattleClient:
    def __init__(self):
        self.my_grid = [[0] * GRID_SIZE for _ in range(GRID_SIZE)]
        self.opp_grid = [[0] * GRID_SIZE for _ in range(GRID_SIZE)]
        self.q = queue.Queue()

        self.id = None
        self.turn = False
        self.ships = 0
        self.running = True
        self.status = "Welcome, Captain. Review the instructions, then start the game."
        self.state = STATE_HOME
        self.started = False
        self.shot_sent_time = 0
        self.last_latency = None
        self.last_event_time = 0
        self.last_event_text = ""
        self.sock = None

        self.hover_cell = None
        self.hover_board = None
        self.water_offset = 0
        self.start_button_rect = None
        self.auto_start = "--auto-start" in sys.argv

        try:
            self.snd_place = pygame.mixer.Sound("PowerUp.wav")
            self.snd_hit = pygame.mixer.Sound("Boom.wav")
            self.snd_miss = pygame.mixer.Sound("Hit.wav")
            self.snd_win = pygame.mixer.Sound("win.wav")
            self.snd_lose = pygame.mixer.Sound("lose.wav")
        except Exception:
            print("Sound files not found. Running in silent mode.")
            self.snd_place = self.snd_hit = self.snd_miss = self.snd_win = self.snd_lose = None

    def network_thread(self, sock):
        while self.running:
            try:
                msg = GameMessage.recv_msg(sock)
                if msg:
                    self.q.put(msg)
                else:
                    break
            except Exception:
                break

        self.q.put(GameMessage(GameMessage.ERROR, {"msg": "Disconnected from server."}))

    def start_game(self):
        if self.started:
            return

        self.started = True
        self.state = STATE_CONNECTING
        self.status = "Connecting to local server..."
        pygame.display.set_caption("BATTLESHIP - CONNECTING")
        self.connect()

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self.sock.connect(("127.0.0.1", 65432))
            threading.Thread(target=self.network_thread, args=(self.sock,), daemon=True).start()
        except Exception:
            self.status = "Unable to connect. Start battleship_server.py first."
            self.state = STATE_HOME
            self.started = False
            pygame.display.set_caption("BATTLESHIP - HOME")

    def run(self):
        if self.auto_start:
            self.start_game()

        while self.running:
            CLOCK.tick(FPS)
            self.water_offset += 0.8
            
