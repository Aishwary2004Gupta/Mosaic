import pygame
import sys
import math
import random
from PIL import Image
import urllib.request
import io

# --- Constants ---
WIDTH, HEIGHT = 700, 700
GRAVITY = pygame.math.Vector2(0, 0)          # no gravity → balls spread across canvas
BACKGROUND_COLOR = (0, 0, 0)
BOUNCE_LOSS = 0.9
COLLISION_DAMPING = 0.95
MIN_RADIUS = 10
MAX_RADIUS = 27
SPAWN_STEP_INTERVAL = 1
FIXED_DT = 1 / 60.0
TOTAL_STEPS = 400
SIMULATION_SUBSTEPS = 8
MAX_OBJECTS = 380

# Live image from Unsplash — fetched every run, never saved to disk
IMAGE_URL = "https://images.unsplash.com/photo-1564514476902-542f8c30121e?w=700&q=80"


class Ball:
    def __init__(self, position, radius, step_added, color=None):
        self.position = pygame.math.Vector2(position)
        self.old_position = pygame.math.Vector2(position)
        self.acceleration = pygame.math.Vector2(0, 0)
        self.radius = radius
        self.mass = math.pi * radius ** 2
        self.step_added = step_added
        self.color = color if color else (
            random.randint(100, 255),
            random.randint(100, 255),
            random.randint(100, 255),
        )

    def update(self, dt):
        velocity = self.position - self.old_position
        self.old_position = pygame.math.Vector2(self.position)
        self.position += velocity + self.acceleration * dt * dt
        self.acceleration = pygame.math.Vector2(0, 0)

    def apply_constraints(self):
        if self.position.x - self.radius < 0:
            self.position.x = self.radius
        elif self.position.x + self.radius > WIDTH:
            self.position.x = WIDTH - self.radius
        if self.position.y - self.radius < 0:
            self.position.y = self.radius
        elif self.position.y + self.radius > HEIGHT:
            self.position.y = HEIGHT - self.radius

    def draw(self, screen):
        draw_pos = (int(self.position.x), int(self.position.y))
        pygame.draw.circle(screen, self.color, draw_pos, int(self.radius))


class Simulation:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Circle Mosaic — Live Image")
        self.balls = []
        self.font = pygame.font.Font(None, 30)
        self.current_step = 0
        self.clock = pygame.time.Clock()
        self.input_image = None
        random.seed(42)
        self.load_image()

    # ---- fetch image from URL every run (real-time, no local file) ----
    def load_image(self):
        print("Fetching image from Unsplash...")
        try:
            req = urllib.request.Request(IMAGE_URL, headers={
                "User-Agent": "Mozilla/5.0",
                "Cache-Control": "no-cache",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
            self.input_image = Image.open(io.BytesIO(data)).convert("RGB")
            self.input_image = self.input_image.resize((WIDTH, HEIGHT))
            print("Image loaded successfully!")
        except Exception as e:
            print(f"Could not fetch image: {e}")
            print("Balls will keep random colours.")

    def add_ball(self, ball):
        if len(self.balls) < MAX_OBJECTS:
            self.balls.append(ball)
        elif self.balls:
            self.balls.pop(0)
            self.balls.append(ball)

    # ---- KEY FIX: actually set ball.color from the image ----
    def update_colors_from_image(self):
        """Every ball picks the image colour at its current pixel."""
        if not self.input_image:
            return
        for ball in self.balls:
            x = min(max(int(ball.position.x), 0), WIDTH - 1)
            y = min(max(int(ball.position.y), 0), HEIGHT - 1)
            r, g, b = self.input_image.getpixel((x, y))
            ball.color = (int(r), int(g), int(b))

    def solve_collisions(self):
        num_balls = len(self.balls)
        for i in range(num_balls):
            for j in range(i + 1, num_balls):
                a = self.balls[i]
                b = self.balls[j]
                dx = a.position.x - b.position.x
                dy = a.position.y - b.position.y
                dist_sq = dx * dx + dy * dy
                min_dist = a.radius + b.radius
                if dist_sq < min_dist * min_dist and dist_sq > 0:
                    dist = math.sqrt(dist_sq)
                    nx, ny = dx / dist, dy / dist
                    overlap = (min_dist - dist) * 0.5
                    total_mass = a.mass + b.mass
                    if total_mass == 0:
                        r1 = r2 = 0.5
                    else:
                        r1 = b.mass / total_mass
                        r2 = a.mass / total_mass
                    sep_x = nx * overlap * COLLISION_DAMPING
                    sep_y = ny * overlap * COLLISION_DAMPING
                    a.position.x += sep_x * r1
                    a.position.y += sep_y * r1
                    b.position.x -= sep_x * r2
                    b.position.y -= sep_y * r2

    def update(self, dt):
        sub_dt = dt / SIMULATION_SUBSTEPS
        for _ in range(SIMULATION_SUBSTEPS):
            for ball in self.balls:
                ball.acceleration += GRAVITY
            self.solve_collisions()
            for ball in self.balls:
                ball.apply_constraints()
            for ball in self.balls:
                ball.update(sub_dt)

    def avg_speed(self):
        if not self.balls:
            return 0
        total = 0.0
        for ball in self.balls:
            vx = ball.position.x - ball.old_position.x
            vy = ball.position.y - ball.old_position.y
            total += abs(vx) + abs(vy)
        return total / len(self.balls)

    def draw(self, label=""):
        self.screen.fill(BACKGROUND_COLOR)
        for ball in self.balls:
            ball.draw(self.screen)
        info = f"Step {self.current_step}/{TOTAL_STEPS}  |  {len(self.balls)}/{MAX_OBJECTS} circles"
        if label:
            info += f"  |  {label}"
        text = self.font.render(info, True, (200, 200, 200))
        self.screen.blit(text, (10, 10))
        pygame.display.flip()

    # ------------------------------------------------------------------ #
    def run(self):
        running = True
        balls_spawned = 0
        phase = "SPAWN"          # SPAWN → SETTLE → MAP → DONE
        settle_wait = 0

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            self.clock.tick(60)

            # ---- SPAWN: blast balls outward from centre ----
            if phase == "SPAWN":
                if (self.current_step % SPAWN_STEP_INTERVAL == 0
                        and balls_spawned < MAX_OBJECTS):
                    cx, cy = WIDTH / 2, HEIGHT / 2
                    radius = random.uniform(MIN_RADIUS, MAX_RADIUS)
                    new_ball = Ball((cx, cy), radius, self.current_step)
                    angle = random.uniform(0, 2 * math.pi)
                    blast = 280
                    new_ball.old_position.x = cx - math.cos(angle) * blast * FIXED_DT
                    new_ball.old_position.y = cy - math.sin(angle) * blast * FIXED_DT
                    self.add_ball(new_ball)
                    balls_spawned += 1

                if balls_spawned >= MAX_OBJECTS:
                    phase = "SETTLE"

            # ---- SETTLE: wait for balls to slow down ----
            elif phase == "SETTLE":
                settle_wait += 1
                if (self.avg_speed() < 0.5 and settle_wait > 60) or settle_wait > 300:
                    phase = "MAP"

            # ---- MAP: paint image colours onto every ball ----
            elif phase == "MAP":
                self.update_colors_from_image()
                phase = "DONE"

            # ---- physics step ----
            if phase in ("SPAWN", "SETTLE"):
                self.update(FIXED_DT)

            # ---- continuous colour update while settling ----
            if self.input_image and phase in ("SPAWN", "SETTLE"):
                if self.current_step % 2 == 0:
                    self.update_colors_from_image()

            # ---- draw ----
            self.draw(label=phase.capitalize())
            self.current_step += 1

            # ---- once DONE, keep showing result until user closes ----
            if phase == "DONE":
                while running:
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            running = False
                    self.clock.tick(30)

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    simulation = Simulation()
    simulation.run()