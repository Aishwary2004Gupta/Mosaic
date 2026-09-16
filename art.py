import pygame
import sys
import math
import random
import io
import urllib.request
from PIL import Image
from collections import defaultdict

# --- Constants ---
WIDTH, HEIGHT = 700, 700
BACKGROUND_COLOR = (0, 0, 0)
DAMPING = 0.93
MIN_RADIUS = 3
MAX_RADIUS = 7
MAX_OBJECTS = 4500
POPS_PER_FRAME = 40
STIFFNESS = 0.07
POP_SPEED = 0.09
IMAGE_URL = "https://images.unsplash.com/photo-1564514476902-542f8c30121e?auto=format&fit=crop&w=700&h=700&q=80"


class Ball:
    __slots__ = ['x', 'y', 'tx', 'ty', 'r', 'cr', 'cg', 'cb',
                 'vx', 'vy', 'pop', 'pop_t', 'settled']

    def __init__(self, tx, ty, r, cr, cg, cb):
        side = random.randint(0, 3)
        if side == 0:   self.x, self.y = random.uniform(0, WIDTH), -40.0
        elif side == 1: self.x, self.y = random.uniform(0, WIDTH), HEIGHT + 40.0
        elif side == 2: self.x, self.y = -40.0, random.uniform(0, HEIGHT)
        else:           self.x, self.y = WIDTH + 40.0, random.uniform(0, HEIGHT)

        self.tx, self.ty = float(tx), float(ty)
        self.r = float(r)
        self.cr, self.cg, self.cb = cr, cg, cb
        self.vx = random.uniform(-2, 2)
        self.vy = random.uniform(-2, 2)
        self.pop = False
        self.pop_t = 0.0
        self.settled = False

    def update(self):
        if not self.pop:
            return

        if self.pop_t < 1.0:
            self.pop_t = min(1.0, self.pop_t + POP_SPEED)

        if self.settled:
            return

        dx = self.tx - self.x
        dy = self.ty - self.y
        dist_sq = dx * dx + dy * dy

        if dist_sq < 0.64:
            self.x, self.y = self.tx, self.ty
            self.vx, self.vy = 0.0, 0.0
            self.settled = True
            return

        self.vx = (self.vx + dx * STIFFNESS) * DAMPING
        self.vy = (self.vy + dy * STIFFNESS) * DAMPING
        self.x += self.vx
        self.y += self.vy


class SpatialGrid:
    __slots__ = ['cell_size', 'cells']

    def __init__(self, cell_size=20):
        self.cell_size = cell_size
        self.cells = defaultdict(list)

    def clear(self):
        self.cells.clear()

    def insert(self, idx, x, y):
        gx = int(x // self.cell_size)
        gy = int(y // self.cell_size)
        self.cells[(gx, gy)].append(idx)

    def get_nearby(self, x, y):
        gx = int(x // self.cell_size)
        gy = int(y // self.cell_size)
        result = []
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                key = (gx + dx, gy + dy)
                if key in self.cells:
                    result.extend(self.cells[key])
        return result


class Simulation:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Circle Mosaic")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 20)
        self.balls = []
        self.image = None
        self.image_data = None
        self.grid = SpatialGrid(cell_size=18)
        self.targets = []
        self.pop_index = 0
        self.all_popped = False
        self.frame = 0

        # Pre-create surfaces for fast blitting
        self.ball_surfs = {}
        self.bg_surface = pygame.Surface((WIDTH, HEIGHT))

        self.fetch_image()

    def fetch_image(self):
        print("Fetching image...")
        try:
            req = urllib.request.Request(IMAGE_URL, headers={
                "User-Agent": "Mozilla/5.0",
                "Cache-Control": "no-cache",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
            img = Image.open(io.BytesIO(data)).convert("RGB")
            self.image = img.resize((WIDTH, HEIGHT))
            self.image_data = self.image.load()
            print(f"Image loaded: {self.image.size}")
        except Exception as e:
            print(f"Failed: {e}")
            self.create_fallback()

    def create_fallback(self):
        self.image = Image.new("RGB", (WIDTH, HEIGHT))
        pixels = self.image.load()
        for y in range(HEIGHT):
            for x in range(WIDTH):
                r = int(128 + 127 * math.sin(x / 80))
                g = int(128 + 127 * math.sin(y / 80))
                b = int(128 + 127 * math.sin((x + y) / 80))
                pixels[x, y] = (r, g, b)
        self.image_data = pixels

    def build_targets(self):
        self.targets = []
        grid_size = max(5, int(math.sqrt((WIDTH * HEIGHT) / MAX_OBJECTS)))

        for y in range(grid_size // 2, HEIGHT, grid_size):
            for x in range(grid_size // 2, WIDTH, grid_size):
                ix = min(x, WIDTH - 1)
                iy = min(y, HEIGHT - 1)
                cr, cg, cb = self.image_data[ix, iy]
                r = random.uniform(MIN_RADIUS, MAX_RADIUS)
                jx = x + random.uniform(-1, 1)
                jy = y + random.uniform(-1, 1)
                self.targets.append((jx, jy, r, cr, cg, cb))

        random.shuffle(self.targets)
        print(f"Targets: {len(self.targets)}")

    def solve_collisions(self):
        self.grid.clear()
        for i, b in enumerate(self.balls):
            if b.pop_t >= 1.0:
                self.grid.insert(i, b.x, b.y)

        for i, a in enumerate(self.balls):
            if a.pop_t < 1.0:
                continue

            nearby = self.grid.get_nearby(a.x, a.y)
            ar = a.r * (0.5 + 0.5 * min(a.pop_t, 1.0))

            for j in nearby:
                if j <= i:
                    continue
                b = self.balls[j]
                dx = a.x - b.x
                dy = a.y - b.y
                d2 = dx * dx + dy * dy
                br = b.r * (0.5 + 0.5 * min(b.pop_t, 1.0))
                md = ar + br

                if d2 < md * md and d2 > 0.001:
                    d = math.sqrt(d2)
                    nx, ny = dx / d, dy / d
                    overlap = (md - d) * 0.5
                    sep_x = nx * overlap * 0.85
                    sep_y = ny * overlap * 0.85
                    a.x += sep_x
                    a.y += sep_y
                    b.x -= sep_x
                    b.y -= sep_y

    def pop_batch(self):
        for _ in range(POPS_PER_FRAME):
            if self.pop_index >= len(self.targets):
                self.all_popped = True
                return

            tx, ty, r, cr, cg, cb = self.targets[self.pop_index]
            ball = Ball(tx, ty, r, cr, cg, cb)
            ball.pop = True
            self.balls.append(ball)
            self.pop_index += 1

    def get_ball_surface(self, radius, color, pop_t):
        key = (int(radius), color, int(pop_t * 10))
        if key in self.ball_surfs:
            return self.ball_surfs[key]

        r = max(1, int(radius * (0.5 + 0.5 * min(pop_t, 1.0))))
        size = r * 2 + 4
        if size > 60:
            return None

        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        cx, cy = size // 2, size // 2
        pygame.draw.circle(surf, (*color, 255), (cx, cy), r)
        if r > 2:
            highlight = (
                min(255, color[0] + 40),
                min(255, color[1] + 40),
                min(255, color[2] + 40),
                180,
            )
            pygame.draw.circle(surf, highlight, (cx, cy), max(1, r // 3))

        if len(self.ball_surfs) < 5000:
            self.ball_surfs[key] = surf
        return surf

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    if event.key == pygame.K_SPACE:
                        global POPS_PER_FRAME
                        POPS_PER_FRAME = min(200, POPS_PER_FRAME + 20)

            if not self.all_popped:
                if self.frame == 0:
                    self.build_targets()
                self.pop_batch()

            for ball in self.balls:
                ball.update()

            if self.frame % 3 == 0:
                self.solve_collisions()

            self.draw()
            self.clock.tick(60)
            self.frame += 1

        pygame.quit()
        sys.exit()

    def draw(self):
        self.bg_surface.fill(BACKGROUND_COLOR)
        self.screen.blit(self.bg_surface, (0, 0))

        for ball in self.balls:
            if ball.pop_t <= 0:
                continue
            surf = self.get_ball_surface(ball.r, (ball.cr, ball.cg, ball.cb), ball.pop_t)
            r = max(1, int(ball.r * (0.5 + 0.5 * min(ball.pop_t, 1.0))))

            if surf:
                x = int(ball.x) - surf.get_width() // 2
                y = int(ball.y) - surf.get_height() // 2
                self.screen.blit(surf, (x, y))
            else:
                pygame.draw.circle(
                    self.screen,
                    (ball.cr, ball.cg, ball.cb),
                    (int(ball.x), int(ball.y)),
                    r
                )

        settled = sum(1 for b in self.balls if b.settled)
        pct = int(self.pop_index / max(1, len(self.targets)) * 100)

        hud_lines = [
            f"Circles: {len(self.balls)}/{len(self.targets)}  ({pct}%)",
            f"Settled: {settled}  |  Speed: {POPS_PER_FRAME}/frame",
            "SPACE = faster  |  ESC = quit",
        ]
        for i, line in enumerate(hud_lines):
            text = self.small_font.render(line, True, (180, 180, 180))
            self.screen.blit(text, (10, 10 + i * 18))

        fps_text = self.small_font.render(f"FPS: {int(self.clock.get_fps())}", True, (120, 120, 120))
        self.screen.blit(fps_text, (WIDTH - 90, 10))

        pygame.display.flip()


if __name__ == "__main__":
    sim = Simulation()
    sim.run()