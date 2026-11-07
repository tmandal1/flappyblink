import random

W, H, FLOOR = 288, 512, 410
BIRD_X, RADIUS = 74, 12
GRAVITY, FLAP_SPEED, PIPE_SPEED = 110, -110, 65
GAP, PIPE_WIDTH, SPACING = 170, 52, 180
INK = (29, 49, 64)


class Game:
    def __init__(self):
        self.best = 0
        self.practice = False
        self.reset()

    def reset(self):
        self.y, self.velocity = 220.0, 0.0
        self.pipes = []
        self.score = 0
        self.state = "ready"
        self.last_input = "SPACE to begin"
        self.spawn(W + 40)

    def spawn(self, x):
        self.pipes.append([float(x), random.randint(175, 265), False])

    def flap(self, source):
        if self.state in ("ready", "playing"):
            self.state = "playing"
            self.velocity = FLAP_SPEED
            self.last_input = source

    def update(self, dt):
        if self.state != "playing":
            return
        self.velocity += GRAVITY * dt
        self.y += self.velocity * dt
        for pipe in self.pipes:
            pipe[0] -= PIPE_SPEED * dt
        if self.pipes[-1][0] < W - SPACING:
            self.spawn(self.pipes[-1][0] + SPACING)
        self.pipes = [p for p in self.pipes if p[0] + PIPE_WIDTH > -5]
        hit = self.y - RADIUS <= 0 or self.y + RADIUS >= FLOOR
        for p in self.pipes:
            x, middle, passed = p
            for top, bottom in ((0, middle-GAP/2), (middle+GAP/2, FLOOR)):
                nx = max(x, min(BIRD_X, x+PIPE_WIDTH))
                ny = max(top, min(self.y, bottom))
                if (BIRD_X-nx)**2 + (self.y-ny)**2 < RADIUS**2:
                    hit = True
            if not passed and x + PIPE_WIDTH < BIRD_X-RADIUS:
                p[2] = True
                self.score += 1
                self.best = max(self.best, self.score)
        if self.practice:
            self.y = max(RADIUS+1, min(FLOOR-RADIUS-1, self.y))
            if self.y >= FLOOR-RADIUS-1 or self.y <= RADIUS+1:
                self.velocity = 0
        elif hit:
            self.state = "over"

