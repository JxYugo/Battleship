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
            self.handle_network_messages()
            self.handle_events()
            self.draw()

        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass

        pygame.quit()

    def handle_network_messages(self):
        while not self.q.empty():
            m = self.q.get()

            if m.msg_type == GameMessage.INIT_PLAYER:
                self.id = m.data["id"]

                if self.id == 0:
                    self.status = "Waiting for opponent to connect..."
                    self.state = STATE_WAITING_START
                    pygame.display.set_caption("BATTLESHIP - WAITING")
                else:
                    self.status = f"Player {self.id}: place your 5 ships."
                    self.state = STATE_PLACING
                    pygame.display.set_caption(f"BATTLESHIP - PLAYER {self.id} PLACE SHIPS")

            elif m.msg_type == GameMessage.GAME_START:
                self.state = STATE_PLAYING
                self.turn = (m.data["turn"] == self.id)
                self.status = "Your turn: choose a target." if self.turn else "Opponent's turn: stand by."
                pygame.display.set_caption("BATTLESHIP - YOUR TURN" if self.turn else "BATTLESHIP - OPPONENT TURN")
                self.last_event_text = "Battle started!"
                self.last_event_time = time.perf_counter()

            elif m.msg_type == GameMessage.SHOT_RESULT:
                if m.data["p_id"] == self.id and self.shot_sent_time > 0:
                    self.last_latency = (time.perf_counter() - self.shot_sent_time) * 1000
                    print(f"[METRIC] Round-Trip Latency: {self.last_latency:.2f}ms")
                    self.shot_sent_time = 0

                x = m.data["x"]
                y = m.data["y"]
                res = m.data["res"]
                p_id = m.data["p_id"]

                val = -1 if res == "hit" else -2

                if p_id == self.id:
                    self.opp_grid[y][x] = val
                    self.last_event_text = f"Your shot at {chr(65 + x)}{y + 1}: {res.upper()}!"
                else:
                    self.my_grid[y][x] = val
                    self.last_event_text = f"Enemy fired at {chr(65 + x)}{y + 1}: {res.upper()}!"

                self.last_event_time = time.perf_counter()

                if res == "hit":
                    if self.snd_hit:
                        self.snd_hit.play()
                else:
                    if self.snd_miss:
                        self.snd_miss.play()

                self.turn = (self.id == m.data["next"])
                self.status = "Your turn: choose a target." if self.turn else "Opponent's turn: stand by."
                pygame.display.set_caption("BATTLESHIP - YOUR TURN" if self.turn else "BATTLESHIP - OPPONENT TURN")

            elif m.msg_type == GameMessage.GAME_OVER:
                winner_id = m.data["winner"]
                self.state = STATE_GAME_OVER
                self.turn = False

                if winner_id == self.id:
                    self.status = "Mission accomplished: you win!"
                    pygame.display.set_caption("BATTLESHIP - YOU WIN")
                    if self.snd_win:
                        self.snd_win.play()
                else:
                    self.status = "Fleet destroyed: you lose."
                    pygame.display.set_caption("BATTLESHIP - YOU LOSE")
                    if self.snd_lose:
                        self.snd_lose.play()

            elif m.msg_type == GameMessage.ERROR:
                self.status = m.data.get("msg", "Network error.")
                self.state = STATE_GAME_OVER
                self.turn = False
                pygame.display.set_caption("BATTLESHIP - ERROR")

    def handle_events(self):
        mouse = pygame.mouse.get_pos()
        self.hover_cell, self.hover_board = self.get_hover_cell(mouse)

        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False

            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.running = False
                if e.key == pygame.K_RETURN and self.state == STATE_HOME:
                    self.start_game()

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos

                if self.state == STATE_HOME:
                    if self.get_start_button_rect().collidepoint(mx, my):
                        self.start_game()
                    continue

                cell_data = self.get_hover_cell((mx, my))
                if not cell_data[0]:
                    continue

                (gx, gy), board = cell_data

                if board == "mine" and self.state == STATE_PLACING and self.ships < 5:
                    if self.my_grid[gy][gx] == 0:
                        self.my_grid[gy][gx] = 1
                        self.ships += 1
                        self.last_event_text = f"Ship placed at {chr(65 + gx)}{gy + 1}."
                        self.last_event_time = time.perf_counter()

                        if self.snd_place:
                            self.snd_place.play()

                        if self.ships == 5:
                            GameMessage.send_msg(
                                self.sock,
                                GameMessage(GameMessage.PLACE_SHIPS, {"grid": self.my_grid})
                            )
                            self.status = "Fleet ready. Waiting for opponent..."
                            self.state = STATE_WAITING_START
                            pygame.display.set_caption(f"BATTLESHIP - PLAYER {self.id} READY")

                elif board == "enemy" and self.state == STATE_PLAYING and self.turn:
                    if self.opp_grid[gy][gx] == 0:
                        self.shot_sent_time = time.perf_counter()
                        GameMessage.send_msg(
                            self.sock,
                            GameMessage(GameMessage.FIRE_SHOT, {"x": gx, "y": gy})
                        )
                        self.status = "Shot fired. Waiting for result..."

    def get_board_rects(self):
        y = TOP_BAR
        mine = pygame.Rect(MARGIN, y, DIM, DIM)
        enemy = pygame.Rect(MARGIN * 2 + DIM, y, DIM, DIM)
        return mine, enemy

    def get_hover_cell(self, mouse):
        mine, enemy = self.get_board_rects()
        mx, my = mouse

        if mine.collidepoint(mx, my):
            return ((mx - mine.x) // CELL, (my - mine.y) // CELL), "mine"

        if enemy.collidepoint(mx, my):
            return ((mx - enemy.x) // CELL, (my - enemy.y) // CELL), "enemy"

        return None, None

    def draw(self):
        draw_vertical_gradient(SCREEN, COLORS["bg_top"], COLORS["bg_bottom"])
        self.draw_water_lines()

        if self.state == STATE_HOME:
            self.draw_home_page()
            pygame.display.flip()
            return

        self.draw_header()

        mine, enemy = self.get_board_rects()
        self.draw_grid(mine.x, mine.y, self.my_grid, "YOUR FLEET", "mine")
        self.draw_grid(enemy.x, enemy.y, self.opp_grid, "ENEMY RADAR", "enemy")

        self.draw_center_radar()
        self.draw_turn_overlay()
        self.draw_footer()

        pygame.display.flip()

    def draw_water_lines(self):
        for i in range(18):
            y = int((i * 38 + self.water_offset) % HEIGHT)
            color = (0, 105 + i * 3 % 60, 150 + i * 2 % 70)
            points = []

            for x in range(0, WIDTH + 20, 20):
                wave = math.sin((x * 0.025) + i + self.water_offset * 0.025) * 5
                points.append((x, y + wave))

            if len(points) > 1:
                pygame.draw.lines(SCREEN, color, False, points, 1)

    def get_home_card_rect(self):
        return pygame.Rect(MARGIN + 35, 130, WIDTH - (MARGIN + 35) * 2, 335)

    def get_start_button_rect(self):
        card = self.get_home_card_rect()
        return pygame.Rect(WIDTH // 2 - 125, card.bottom + 32, 250, 58)

    def draw_home_page(self):
        title_y = 60
        self.draw_background_ship()

        draw_text(SCREEN, "BATTLESHIP", FONT_TITLE, COLORS["text"], (WIDTH // 2, title_y), center=True)
        draw_text(SCREEN, "LOCAL MULTIPLAYER CLIENT-SERVER GAME SYSTEM", FONT_BODY, COLORS["accent_2"], (WIDTH // 2, title_y + 42), center=True)

        card = self.get_home_card_rect()
        draw_round_rect(SCREEN, card, (8, 30, 52), 22, COLORS["panel_border"], 2)

        draw_text(SCREEN, "HOW TO PLAY", FONT_HEAD, COLORS["accent"], (card.centerx, card.y + 35), center=True)

        instructions = [
            "1. Click START GAME in both windows first. ",
            "2. Each player places 5 ships on the YOUR FLEET grid.",
            "3. After both players are ready, the server starts the match.",
            "4. On your turn, click a cell on ENEMY RADAR to fire a shot.",
            "5. Red marks mean HIT, white circles mean MISS.",
            "6. The first player to destroy all enemy ships wins.",
            "Important: Do not place ships after starting only Player 1."
    
        ]

        y = card.y + 82
        for line in instructions:
            draw_text(SCREEN, line, FONT_BODY, COLORS["text"], (card.x + 55, y))
            y += 34

        start_rect = self.get_start_button_rect()
        self.start_button_rect = start_rect
        hover = start_rect.collidepoint(pygame.mouse.get_pos())

        color = (0, 175, 220) if hover else (0, 130, 180)
        border = COLORS["accent_2"] if hover else COLORS["text"]

        draw_round_rect(SCREEN, start_rect, color, 18, border, 3)
        draw_text(SCREEN, "START GAME", FONT_HEAD, COLORS["text"], start_rect.center, center=True)

    def draw_background_ship(self):
        ship_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        base_y = HEIGHT - 115
        ship_color = (20, 90, 125, 95)
        edge_color = (0, 210, 255, 80)

        hull = [
            (90, base_y),
            (WIDTH - 110, base_y),
            (WIDTH - 170, base_y + 55),
            (150, base_y + 55),
        ]

        pygame.draw.polygon(ship_surface, ship_color, hull)
        pygame.draw.lines(ship_surface, edge_color, True, hull, 2)

        pygame.draw.rect(ship_surface, ship_color, (220, base_y - 35, 390, 35), border_radius=6)
        pygame.draw.rect(ship_surface, edge_color, (220, base_y - 35, 390, 35), 2, border_radius=6)

        pygame.draw.rect(ship_surface, ship_color, (395, base_y - 105, 80, 70), border_radius=6)
        pygame.draw.rect(ship_surface, edge_color, (395, base_y - 105, 80, 70), 2, border_radius=6)
        pygame.draw.rect(ship_surface, ship_color, (420, base_y - 145, 38, 40), border_radius=4)
        pygame.draw.rect(ship_surface, edge_color, (420, base_y - 145, 38, 40), 2, border_radius=4)

        pygame.draw.line(ship_surface, edge_color, (280, base_y - 28), (190, base_y - 65), 7)
        pygame.draw.line(ship_surface, edge_color, (570, base_y - 28), (660, base_y - 65), 7)
        pygame.draw.circle(ship_surface, ship_color, (280, base_y - 28), 16)
        pygame.draw.circle(ship_surface, ship_color, (570, base_y - 28), 16)

        pygame.draw.line(ship_surface, edge_color, (439, base_y - 145), (439, base_y - 185), 3)
        pygame.draw.circle(ship_surface, edge_color, (439, base_y - 190), 10, 2)

        SCREEN.blit(ship_surface, (0, 0))

    def draw_header(self):
        header = pygame.Rect(MARGIN, 15, WIDTH - MARGIN * 2, 62)
        draw_round_rect(SCREEN, header, (8, 27, 48), 18, COLORS["panel_border"], 2)

        draw_text(SCREEN, "BATTLESHIP", FONT_TITLE, COLORS["text"], (WIDTH // 2, 35), center=True)
        draw_text(SCREEN, "LOCAL MULTIPLAYER CLIENT-SERVER SYSTEM", FONT_SMALL, COLORS["accent_2"], (WIDTH // 2, 66), center=True)

    def draw_turn_overlay(self):
        if self.state == STATE_PLAYING and not self.turn:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 70))
            SCREEN.blit(overlay, (0, 0))

            box = pygame.Rect(WIDTH // 2 - 220, HEIGHT // 2 - 55, 440, 110)
            draw_round_rect(SCREEN, box, (10, 30, 50), 20, COLORS["accent"], 3)

            pulse = abs(pygame.time.get_ticks() % 1000 - 500) / 500.0
            color = (100, int(180 + 75 * pulse), 255)

            draw_text(SCREEN, "OPPONENT'S TURN", FONT_TITLE, color, box.center, center=True)
            draw_text(SCREEN, "Waiting for enemy action...", FONT_BODY, COLORS["muted"], (box.centerx, box.centery + 32), center=True)

    def draw_footer(self):
        footer = pygame.Rect(MARGIN, HEIGHT - BOTTOM_BAR + 18, WIDTH - MARGIN * 2, 62)
        draw_round_rect(SCREEN, footer, COLORS["panel"], 16, COLORS["panel_border"], 2)

        status_color = COLORS["success"] if self.turn else COLORS["text"]
        draw_text(SCREEN, self.status, FONT_HEAD, status_color, (MARGIN + 20, HEIGHT - BOTTOM_BAR + 35))

        draw_text(SCREEN, f"Ships placed: {self.ships}/5", FONT_BODY, COLORS["muted"], (WIDTH - MARGIN - 210, HEIGHT - BOTTOM_BAR + 28))

        if self.last_latency is not None:
            draw_text(SCREEN, f"Latency: {self.last_latency:.2f} ms", FONT_BODY, COLORS["accent"], (WIDTH - MARGIN - 210, HEIGHT - BOTTOM_BAR + 54))

        if self.last_event_text and time.perf_counter() - self.last_event_time < 3:
            draw_text(SCREEN, self.last_event_text, FONT_SMALL, COLORS["accent_2"], (WIDTH // 2, HEIGHT - 18), center=True)

    def draw_center_radar(self):
        cx = WIDTH // 2
        cy = TOP_BAR + DIM // 2

        pygame.draw.circle(SCREEN, (15, 52, 78), (cx, cy), 42, 2)
        pygame.draw.circle(SCREEN, (15, 52, 78), (cx, cy), 25, 1)

        angle = time.perf_counter() * 2.2
        end = (cx + math.cos(angle) * 42, cy + math.sin(angle) * 42)

        pygame.draw.line(SCREEN, COLORS["accent"], (cx, cy), end, 2)
        draw_text(SCREEN, "VS", FONT_HEAD, COLORS["accent_2"], (cx, cy), center=True)

    def draw_grid(self, x_off, y_off, data, label, board):
        outer = pygame.Rect(x_off - 8, y_off - 40, DIM + 16, DIM + 52)
        draw_round_rect(SCREEN, outer, COLORS["panel"], 16, COLORS["panel_border"], 2)

        draw_text(SCREEN, label, FONT_HEAD, COLORS["text"], (x_off + DIM // 2, y_off - 23), center=True)

        for i in range(GRID_SIZE):
            draw_text(SCREEN, chr(65 + i), FONT_TINY, COLORS["muted"], (x_off + i * CELL + CELL // 2, y_off - 7), center=True)
            draw_text(SCREEN, str(i + 1), FONT_TINY, COLORS["muted"], (x_off - 9, y_off + i * CELL + CELL // 2), center=True)

        pulse = abs(pygame.time.get_ticks() % 1000 - 500) / 500.0

        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                rect = pygame.Rect(x_off + x * CELL, y_off + y * CELL, CELL, CELL)
                base = COLORS["sea"] if (x + y) % 2 == 0 else COLORS["sea_alt"]

                pygame.draw.rect(SCREEN, base, rect)

                if self.hover_cell == (x, y) and self.hover_board == board:
                    can_highlight = False

                    if board == "mine" and self.state == STATE_PLACING and self.ships < 5:
                        can_highlight = data[y][x] == 0

                    if board == "enemy" and self.state == STATE_PLAYING and self.turn:
                        can_highlight = data[y][x] == 0

                    if can_highlight:
                        pygame.draw.rect(SCREEN, (0, 215, 255), rect, 4)

                cell_state = data[y][x]

                if cell_state == 1:
                    ship_color = (
                        clamp(COLORS["ship"][0] + int(45 * pulse), 0, 255),
                        clamp(COLORS["ship"][1] + int(45 * pulse), 0, 255),
                        clamp(COLORS["ship"][2] + int(45 * pulse), 0, 255),
                    )

                    ship_rect = rect.inflate(-10, -12)
                    pygame.draw.rect(SCREEN, ship_color, ship_rect, border_radius=10)
                    pygame.draw.circle(SCREEN, COLORS["ship_glow"], ship_rect.center, 5)
                    pygame.draw.rect(SCREEN, (45, 55, 65), ship_rect, 2, border_radius=10)

                elif cell_state == -1:
                    glow = int(80 * pulse)
                    color = (
                        clamp(COLORS["hit"][0], 0, 255),
                        clamp(COLORS["hit"][1] + glow, 0, 255),
                        clamp(COLORS["hit"][2] + glow, 0, 255),
                    )

                    pygame.draw.circle(SCREEN, COLORS["hit_glow"], rect.center, 14, 2)
                    pygame.draw.line(SCREEN, color, (rect.left + 9, rect.top + 9), (rect.right - 9, rect.bottom - 9), 5)
                    pygame.draw.line(SCREEN, color, (rect.right - 9, rect.top + 9), (rect.left + 9, rect.bottom - 9), 5)

                elif cell_state == -2:
                    pygame.draw.circle(SCREEN, COLORS["miss"], rect.center, 7)
                    pygame.draw.circle(SCREEN, (70, 110, 140), rect.center, 14, 1)

                pygame.draw.rect(SCREEN, COLORS["grid_line"], rect, 1)


if __name__ == "__main__":
    BattleClient().run()
