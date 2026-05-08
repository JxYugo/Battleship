import pygame, socket, threading, queue
from battleship_network import GameMessage

CELL, MARGIN = 40, 20
DIM = CELL * 10
SCREEN = pygame.display.set_mode((DIM * 2 + MARGIN * 3, DIM + 150))
COLORS = {"sea": (30, 60, 100), "ship": (100, 100, 100), "hit": (255, 50, 50), "miss": (200, 200, 200),
          "bg": (10, 20, 30)}

STATE_CONNECTING = 0
STATE_PLACING = 1
STATE_WAITING_START = 2
STATE_PLAYING = 3
STATE_GAME_OVER = 4

class BattleClient:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()

        self.my_grid = [[0] * 10 for _ in range(10)]
        self.opp_grid = [[0] * 10 for _ in range(10)]
        self.q = queue.Queue()
        self.id, self.turn, self.ships, self.running = None, False, 0, True
        self.status = "Connecting..."

        try:
            self.snd_place = pygame.mixer.Sound("PowerUp.wav")
            self.snd_hit = pygame.mixer.Sound("Boom.wav")
            self.snd_miss = pygame.mixer.Sound("Hit.wav")

            self.snd_win = pygame.mixer.Sound("win.wav")
            self.snd_lose = pygame.mixer.Sound("lose.wav")
        except:
            print("Sound files not found in folder. Running in silent mode.")
            self.snd_place = self.snd_hit = self.snd_miss = None

    def network_thread(self, sock):
        while self.running:
            msg = GameMessage.recv_msg(sock)
            if msg:
                self.q.put(msg)
            else:
                break

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect(('127.0.0.1', 65432))
        except:
            return
        threading.Thread(target=self.network_thread, args=(sock,), daemon=True).start()

        while self.running:
            # --- 1. Process Network Messages (PLACE THE UPDATE HERE) ---
            while not self.q.empty():
                m = self.q.get()

                if m.msg_type == GameMessage.INIT_PLAYER:
                    self.id = m.data['id']
                    if self.id == 0:
                        self.status = "WAITING FOR OPPONENT..."
                    else:
                        self.status = f"PLAYER {self.id}: PLACE YOUR SHIPS"
                        self.state = STATE_PLACING

                elif m.msg_type == GameMessage.GAME_START:
                    self.state = STATE_PLAYING
                    self.turn = (m.data['turn'] == self.id)
                    self.status = "YOUR TURN!" if self.turn else "OPPONENT'S TURN..."

                elif m.msg_type == GameMessage.SHOT_RESULT:
                    # Keep your original SHOT_RESULT logic here to update grids/sounds
                    x, y, res, p_id = m.data['x'], m.data['y'], m.data['res'], m.data['p_id']
                    val = -1 if res == "hit" else -2
                    if p_id == self.id:
                        self.opp_grid[y][x] = val
                    else:
                        self.my_grid[y][x] = val

                    if res == "hit":
                        if self.snd_hit: self.snd_hit.play()
                    else:
                        if self.snd_miss: self.snd_miss.play()
                    self.turn = (self.id == m.data['next'])

                elif m.msg_type == GameMessage.GAME_OVER:
                    winner_id = m.data['winner']
                    self.state = STATE_GAME_OVER
                    self.turn = False
                    if winner_id == self.id:
                        self.status = "MISSION ACCOMPLISHED: YOU WIN!"
                        if self.snd_win: self.snd_win.play()
                    else:
                        self.status = "FLEET DESTROYED: YOU LOSE!"
                        if self.snd_lose: self.snd_lose.play()

                elif m.msg_type == GameMessage.ERROR:
                    self.status = m.data['msg']
                    self.state = STATE_GAME_OVER
                    self.turn = False
                    if self.snd_lose: self.snd_lose.play()

            for e in pygame.event.get():
                if e.type == pygame.QUIT: self.running = False
                if e.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = e.pos

                    if self.ships < 5 and MARGIN < mx < MARGIN + DIM and MARGIN < my < MARGIN + DIM:
                        gx, gy = (mx - MARGIN) // CELL, (my - MARGIN) // CELL
                        if self.my_grid[gy][gx] == 0:
                            self.my_grid[gy][gx] = 1
                            self.ships += 1

                            if self.snd_place: self.snd_place.play()

                            if self.ships == 5:
                                GameMessage.send_msg(sock, GameMessage(GameMessage.PLACE_SHIPS, {"grid": self.my_grid}))
                                self.status = "Waiting for opponent..."

                    elif self.turn and (MARGIN * 2 + DIM) < mx < (MARGIN * 2 + DIM * 2) and MARGIN < my < MARGIN + DIM:
                        gx, gy = (mx - (MARGIN * 2 + DIM)) // CELL, (my - MARGIN) // CELL
                        if self.opp_grid[gy][gx] == 0:
                            GameMessage.send_msg(sock, GameMessage(GameMessage.FIRE_SHOT, {"x": gx, "y": gy}))

            SCREEN.fill(COLORS["bg"])
            self.draw_grid(MARGIN, MARGIN, self.my_grid, "YOUR FLEET")
            self.draw_grid(MARGIN * 2 + DIM, MARGIN, self.opp_grid, "ENEMY RADAR")

            txt = pygame.font.Font(None, 40).render(self.status, True, (255, 255, 255))
            SCREEN.blit(txt, (MARGIN, DIM + 50))
            if self.turn: pygame.draw.circle(SCREEN, (0, 255, 0), (DIM * 2 + MARGIN * 2, DIM + 65), 10)

            pygame.display.flip()
        pygame.quit()


    def draw_grid(self, x_off, y_off, data, label):

        lbl = pygame.font.Font(None, 30).render(label, True, (200, 200, 200))
        SCREEN.blit(lbl, (x_off, y_off - 25))

        pulse = (abs(pygame.time.get_ticks() % 1000 - 500) / 500.0)

        for y in range(10):
            for x in range(10):

                rect = pygame.Rect(x_off + x * CELL, y_off + y * CELL, CELL, CELL)
                pygame.draw.rect(SCREEN, COLORS["sea"], rect)

                cell_state = data[y][x]

                if cell_state == 1:

                    ship_color = COLORS["ship"]

                    animated_gray = (
                        min(255, ship_color[0] + int(40 * pulse)),
                        min(255, ship_color[1] + int(40 * pulse)),
                        min(255, ship_color[2] + int(40 * pulse))
                    )

                    ship_points = [
                        (rect.centerx, rect.top + 5),
                        (rect.right - 5, rect.bottom - 5),
                        (rect.left + 5, rect.bottom - 5)
                    ]

                    pygame.draw.polygon(SCREEN, animated_gray, ship_points)
                    pygame.draw.polygon(SCREEN, (50, 50, 50), ship_points, 2)

                elif cell_state == -1:
                    pulse_color = (
                        min(255, COLORS["hit"][0] + int(100 * pulse)),
                        min(255, COLORS["hit"][1] + int(100 * pulse)),
                        min(255, COLORS["hit"][2] + int(100 * pulse))
                    )

                    pygame.draw.line(SCREEN, pulse_color, (rect.left + 8, rect.top + 8),
                                     (rect.right - 8, rect.bottom - 8), 5)
                    pygame.draw.line(SCREEN, pulse_color, (rect.right - 8, rect.top + 8),
                                     (rect.left + 8, rect.bottom - 8), 5)

                elif cell_state == -2:
                    pygame.draw.circle(SCREEN, COLORS["miss"], rect.center, 6)

                pygame.draw.rect(SCREEN, (0, 0, 0), rect, 1)

if __name__ == "__main__": BattleClient().run()