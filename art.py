import pygame
import sys
import math
import random
import io
import urllib.request
from PIL import Image

# --- Constants ---
WIDTH, HEIGHT = 700, 700
BACKGROUND_COLOR = (0, 0, 0)
SPAWN_RATE = 15          # Balls to "pop" into existence per frame
GRID_SIZE = 30           # Spatial grid size for fast collision detection
MAX_OBJECTS = 2500       # Higher density
IMAGE_URL = "https://images.unsplash.com/photo-1564514476902-542f8c30121e?w=700&h=700&q=80"

class Ball:
    def __init__(self, target_x, target_y, radius, color):
        # Start random position (pop in)
        self.position = pygame.math.Vector2(random.randint(0, WIDTH), random.randint(0, HEIGHT))
        self.velocity = pygame.math.Vector2(random.uniform(-10, 10), random.uniform(-10, 10))
        self.target = pygame.math.Vector2(target_x, target_y)
        self.radius = radius
        self.color = color
        self.settled = False

    def update(self):
        if not self.settled:
            # Spring force to target
            force = (self.target - self.position) * 0.1
            self.velocity += force
            self.velocity *= 0.9  # Damping
            self.position += self.velocity
            
            # Lock if close and slow
            if self.position.distance_to(self.target) < 1.0 and self.velocity.length() < 0.5:
                self.position = self.target
                self.velocity = pygame.math.Vector2(0,0)
                self.settled = True

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.position.x), int(self.position.y)), int(self.radius))

class Simulation:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.balls = []
        self.targets = [] # Queue of future balls
        self.image = self.fetch_image(IMAGE_URL)
        self.prepare_mosaic()

    def fetch_image(self, url):
        try:
            with urllib.request.urlopen(url) as response:
                img = Image.open(io.BytesIO(response.read())).convert('RGB').resize((WIDTH, HEIGHT))
                return img
        except: return None

    def prepare_mosaic(self):
        """Pre-calculate target grid to ensure full coverage without gaps."""
        # Hexagonal packing calculation
        radius = 8 
        x_spacing = radius * 1.7
        y_spacing = radius * 1.5
        
        for y in range(0, HEIGHT, int(y_spacing)):
            offset = (y // int(y_spacing)) % 2 * (x_spacing / 2)
            for x in range(int(-x_spacing), WIDTH + int(x_spacing), int(x_spacing)):
                tx, ty = x + offset, y
                if 0 <= tx < WIDTH and 0 <= ty < HEIGHT:
                    color = self.image.getpixel((int(tx), int(ty)))
                    self.targets.append({'x': tx, 'y': ty, 'r': radius, 'c': color})
        random.shuffle(self.targets)

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: running = False
            
            # Pop out new balls
            for _ in range(SPAWN_RATE):
                if self.targets and len(self.balls) < MAX_OBJECTS:
                    t = self.targets.pop()
                    self.balls.append(Ball(t['x'], t['y'], t['r'], t['c']))

            # Update & Draw
            self.screen.fill(BACKGROUND_COLOR)
            
            # Simple grid-based collision optimization
            grid = {}
            for i, b in enumerate(self.balls):
                b.update()
                
                # Spatial Hash check: Only check neighbors in same grid cell
                gx, gy = int(b.position.x // GRID_SIZE), int(b.position.y // GRID_SIZE)
                key = (gx, gy)
                if key not in grid: grid[key] = []
                grid[key].append(i)
                
                b.draw(self.screen)

            # Resolve collisions using the grid
            for key, cell_indices in grid.items():
                for i in cell_indices:
                    for j in cell_indices:
                        if i < j:
                            self.resolve(self.balls[i], self.balls[j])

            pygame.display.flip()
            self.clock.tick(60)

    def resolve(self, b1, b2):
        dist = b1.position.distance_to(b2.position)
        min_dist = b1.radius + b2.radius
        if dist < min_dist and dist > 0:
            overlap = min_dist - dist
            direction = (b1.position - b2.position).normalize()
            b1.position += direction * (overlap * 0.5)
            b2.position -= direction * (overlap * 0.5)

if __name__ == "__main__":
    Simulation().run()