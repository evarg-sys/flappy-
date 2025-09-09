from pathlib import Path

code = r"""
# Mini Flappy++: A simple Flappy Bird-like game with bosses and power-ups
"""

path = Path(r"C:\Users\ericg\Documents\projects\project flappy\flappy_simple.py")
path.write_text(code, encoding="utf-8")

import math
import random
import sys
import time
import pygame

# ------------- Config -------------
WIDTH, HEIGHT = 480, 640
FPS = 60

# Core physics
GRAVITY = 1300.0        # px/s^2
FLAP_VELOCITY = -360.0  # px/s

# Pipes
PIPE_GAP_RANGE = (130, 190)   # min/max size of pipe gap
PIPE_GAP = 160
PIPE_WIDTH = 68
PIPE_SPEED = -170       # px/s (to the left)
SPAWN_EVERY_RANGE = (0.95, 1.55) # seconds — randomized spacing between pipe spawns
GROUND_H = 80
BIRD_X = 120

# Boss
BOSS_EVERY = 10         # spawn a boss every N points
BOSS_BULLET_COOLDOWN = (0.7, 1.1)  # random cooldown range (seconds)
BOSS_BULLET_SPEED = 220.0
BOSS_SURVIVE_TIME = 20.0  # seconds to survive each boss

# Power-ups
POWERUP_EVERY = (5.0, 9.0)  # seconds between spawns in normal mode
POWERUP_SPEED = PIPE_SPEED  # float along like pipes
POWERUP_R = 10
SHIELD_TIME = 4.5           # seconds of shield
SLOW_TIME = 3.0             # seconds of slow-mo
SPARK_SPEED = 360.0         # friendly projectile speed

# Colors
BG = (28, 31, 48)
FG = (230, 230, 230)
PIPE_COL = (90, 200, 120)
PIPE_ACC = (70, 150, 90)
BIRD_COL = (255, 190, 0)
BEAK = (255, 230, 150)
RED = (220, 70, 70)
CYAN = (140, 210, 240)
PURPLE = (180, 130, 230)
GREEN = (90, 230, 160)

# ------------- Helpers -------------
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def randf(a, b):
    return a + random.random() * (b - a)

def rect_circle_collide(rect, cx, cy, r):
    rx = clamp(cx, rect.left, rect.right)
    ry = clamp(cy, rect.top, rect.bottom)
    dx, dy = cx - rx, cy - ry
    return dx*dx + dy*dy <= r*r

# ------------- Entities -------------
class Particle:
    def __init__(self, x, y, vx, vy, r, col, life):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = vx, vy
        self.r = r
        self.col = col
        self.life = life
        self.age = 0.0

    def update(self, dt):
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 400.0 * dt

    def dead(self):
        return self.age >= self.life

    def draw(self, surf):
        if self.dead(): return
        alpha = 1.0 - self.age / self.life
        c = tuple(int(clamp(ch*alpha + 20*(1-alpha), 0, 255)) for ch in self.col)
        pygame.draw.circle(surf, c, (int(self.x), int(self.y)), max(1, int(self.r * alpha)))

class Bird:
    def __init__(self, x, y):
        self.x = float(x)
        self.base_y = float(y)
        self.y = float(y)
        self.vy = 0.0
        self.r = 14
        self.dead = False
        self.shield = 0.0
        self.invuln = 0.0
        self.flap_tick = 0.0

    def flap(self):
        if not self.dead:
            self.vy = FLAP_VELOCITY
            self.flap_tick = 0.12

    def update(self, dt):
        self.vy += GRAVITY * dt
        self.y += self.vy * dt
        if self.shield > 0: self.shield = max(0.0, self.shield - dt)
        if self.invuln > 0: self.invuln = max(0.0, self.invuln - dt)
        if self.flap_tick > 0: self.flap_tick -= dt

    def rect(self):
        return pygame.Rect(int(self.x - self.r), int(self.y - self.r), self.r*2, self.r*2)

    def hit(self):
        if self.shield > 0.0:
            self.shield = 0.0
            self.invuln = 0.7
            return False
        if self.invuln > 0.0:
            return False
        self.dead = True
        return True

    def draw(self, surf, time_scale=1.0):
        tilt = clamp(-self.vy / 500.0, -0.6, 0.6)
        cx, cy = int(self.x), int(self.y)
        scale = 1.0 + (0.12 if self.flap_tick > 0 else 0.0)
        pygame.draw.circle(surf, BIRD_COL, (cx, cy), int(self.r * scale))
        bx = cx + int(self.r * math.cos(tilt))
        by = cy + int(self.r * math.sin(tilt))
        pygame.draw.circle(surf, BEAK, (bx, by), 4)
        if self.shield > 0.0:
            t = time.perf_counter() * 6.0
            ring_r = self.r + 5 + int(2*math.sin(t))
            pygame.draw.circle(surf, CYAN, (cx, cy), ring_r, 2)

class PipePair:
    def __init__(self, x, last_center=None):
        self.x = float(x)
        self.passed = False
        margin = 50
        gap = random.randint(*PIPE_GAP_RANGE)
        if last_center is not None:
            shift = random.randint(-80, 80)
            center = clamp(last_center + shift, 120, HEIGHT - GROUND_H - 120)
        else:
            center = random.randint(150, HEIGHT - GROUND_H - 150)
        top_height = center - gap // 2
        self.top_rect = pygame.Rect(int(self.x), 0, PIPE_WIDTH, top_height)
        self.bot_rect = pygame.Rect(int(self.x), top_height + gap, PIPE_WIDTH,
                                    HEIGHT - GROUND_H - (top_height + gap))
        self.gap_center = center

    def update(self, dt):
        self.x += PIPE_SPEED * dt
        self.top_rect.x = int(self.x)
        self.bot_rect.x = int(self.x)

    def offscreen(self):
        return self.x + PIPE_WIDTH < 0

    def collide(self, rect):
        return rect.colliderect(self.top_rect) or rect.colliderect(self.bot_rect)

    def draw(self, surf):
        pygame.draw.rect(surf, PIPE_COL, self.top_rect, border_radius=6)
        pygame.draw.rect(surf, PIPE_COL, self.bot_rect, border_radius=6)

class EnemyBullet:
    def __init__(self, x, y, vx, vy, r=6, col=RED):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = float(vx), float(vy)
        self.r = r
        self.col = col
        self.dead = False

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.x < -20 or self.x > WIDTH + 20 or self.y < -20 or self.y > HEIGHT + 20:
            self.dead = True

    def rect(self):
        return pygame.Rect(int(self.x - self.r), int(self.y - self.r), self.r*2, self.r*2)

    def draw(self, surf):
        pygame.draw.circle(surf, self.col, (int(self.x), int(self.y)), self.r)

class PowerUp:
    TYPES = ("shield", "slow")  # removed charge
    COLS = {"shield": CYAN, "slow": GREEN}

    def __init__(self, x, y, kind=None):
        self.x, self.y = float(x), float(y)
        self.kind = kind if kind in PowerUp.TYPES else random.choice(PowerUp.TYPES)
        self.r = POWERUP_R
        self.dead = False

    def update(self, dt):
        self.x += POWERUP_SPEED * dt
        if self.x + self.r < -5:
            self.dead = True

    def rect(self):
        return pygame.Rect(int(self.x - self.r), int(self.y - self.r), self.r*2, self.r*2)

    def draw(self, surf):
        col = PowerUp.COLS[self.kind]
        pygame.draw.circle(surf, col, (int(self.x), int(self.y)), self.r)
        pygame.draw.circle(surf, (255,255,255), (int(self.x), int(self.y)), self.r, 2)

class Boss:
    def __init__(self, level):
        self.level = level
        self.w, self.h = 120, 70
        self.x = WIDTH + 40.0
        self.y = 120.0
        self.vx = -120.0
        self.dead = False
        self.time = 0.0
        self.fire_cd = randf(*BOSS_BULLET_COOLDOWN) / (1.0 + 0.05*(level-1))
        self.intro = True
        self.outro = False

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), int(self.w), int(self.h))

    def update(self, dt, bird):
        self.time += dt
        if self.intro:
            self.x += self.vx * dt
            if self.x <= WIDTH - self.w - 40:
                self.intro = False
        elif self.outro:
            self.x += 240 * dt
            if self.x > WIDTH + 50:
                self.dead = True
        else:
            self.y = 80 + 60 * math.sin(self.time * (1.2 + 0.1*self.level))
            self.x = clamp(self.x, 60, WIDTH - self.w - 20)

    def try_fire(self, bird):
        if self.intro or self.outro: return None
        self.fire_cd -= 1/FPS
        if self.fire_cd <= 0:
            self.fire_cd = randf(*BOSS_BULLET_COOLDOWN) / (1.0 + 0.06*(self.level-1))
            bx, by = self.x + 10, self.y + self.h*0.5 + randf(-10, 10)
            dx, dy = (bird.x - bx), (bird.y - by)
            dist = math.hypot(dx, dy) + 1e-5
            vx, vy = dx / dist * (BOSS_BULLET_SPEED + 20*self.level), dy / dist * (BOSS_BULLET_SPEED + 20*self.level)
            return EnemyBullet(bx, by, vx, vy, r=6, col=RED)
        return None

    def draw(self, surf):
        body = pygame.Rect(int(self.x), int(self.y), int(self.w), int(self.h))
        pygame.draw.rect(surf, (200, 90, 120), body, border_radius=14)
        eye_l = pygame.Rect(int(self.x + 24), int(self.y + 20), 16, 16)
        eye_r = pygame.Rect(int(self.x + self.w - 40), int(self.y + 20), 16, 16)
        pygame.draw.rect(surf, (20, 20, 30), eye_l, border_radius=8)
        pygame.draw.rect(surf, (20, 20, 30), eye_r, border_radius=8)
        mouth = pygame.Rect(int(self.x + 20), int(self.y + self.h - 22), int(self.w - 40), 10)
        pygame.draw.rect(surf, (30, 18, 30), mouth, border_radius=6)

# ------------- Game -------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Mini Flappy++")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 36)
        self.big = pygame.font.SysFont(None, 64)
        self.small = pygame.font.SysFont(None, 24)
        self.reset()

    def reset(self):
        self.state = "ready"
        self.level = 1
        self.bird = Bird(BIRD_X, HEIGHT//2)
        self.pipes = []
        self.spawn_timer = 0.0
        self.next_spawn_delay = randf(*SPAWN_EVERY_RANGE)
        self.score = 0
        self.best = getattr(self, "best", 0)
        self.power_timer = randf(*POWERUP_EVERY)
        self.powerups = []
        self.particles = []
        self.bullets = []
        self.boss = None
        self.boss_time = 0.0
        self.next_boss_at = BOSS_EVERY
        self.slowmo = 0.0
        self.screenshake = 0.0
        self.last_gap_center = HEIGHT // 2

    def spawn_pipe(self):
        x = WIDTH + 40
        new_pipe = PipePair(x, self.last_gap_center)
        self.last_gap_center = new_pipe.gap_center
        self.pipes.append(new_pipe)

    def spawn_powerup(self, kind=None):
        x = WIDTH + 40 + PIPE_WIDTH + 30
        y = random.randint(60, HEIGHT - GROUND_H - 60)
        self.powerups.append(PowerUp(x, y, kind=kind))

    def spawn_boss(self):
        self.boss = Boss(self.level)
        self.boss_time = BOSS_SURVIVE_TIME
        self.spawn_timer = -999.0

    def handle_input(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
                if self.state == "ready":
                    self.state = "playing"
                    self.bird.flap()
                elif self.state == "playing":
                    self.bird.flap()
                elif self.state == "dead":
                    self.reset()
            elif e.key == pygame.K_r:
                self.reset()
            elif e.key == pygame.K_p and self.state == "playing":
                self.state = "paused"
            elif e.key == pygame.K_p and self.state == "paused":
                self.state = "playing"
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.state in ("ready", "dead"):
                self.reset()
                self.state = "playing"
                self.bird.flap()
            elif self.state == "playing":
                self.bird.flap()

    def update(self, dt):
        if self.state != "playing":
            return
        tscale = 0.6 if self.slowmo > 0 else 1.0
        edt = dt * tscale
        if self.slowmo > 0.0: self.slowmo = max(0.0, self.slowmo - dt)
        if self.screenshake > 0.0: self.screenshake = max(0.0, self.screenshake - dt)

        self.bird.update(edt)

        if self.boss is None:
            self.spawn_timer += edt
            if self.spawn_timer >= self.next_spawn_delay:
                self.spawn_timer = 0.0
                self.next_spawn_delay = randf(*SPAWN_EVERY_RANGE)
                self.spawn_pipe()

        for p in list(self.pipes):
            p.update(edt)
            if p.offscreen():
                self.pipes.remove(p)

        brect = self.bird.rect()
        if self.boss is None:
            for p in self.pipes:
                if not p.passed and p.x + PIPE_WIDTH < self.bird.x:
                    p.passed = True
                    self.score += 1
                if p.collide(brect):
                    if self.bird.hit(): self.dead()
                    else: self.hit_fx(self.bird.x, self.bird.y)
        else:
            for p in self.pipes:
                if p.collide(brect):
                    if self.bird.hit(): self.dead()
                    else: self.hit_fx(self.bird.x, self.bird.y)

        if self.bird.y - self.bird.r <= 0 or self.bird.y + self.bird.r >= HEIGHT - GROUND_H:
            if self.bird.hit(): self.dead()
            else: self.hit_fx(self.bird.x, self.bird.y)

        self.power_timer -= dt
        if self.boss is None and self.power_timer <= 0.0:
            self.power_timer = randf(*POWERUP_EVERY)
            self.spawn_powerup()
        for pu in list(self.powerups):
            pu.update(edt)
            if pu.dead:
                self.powerups.remove(pu)
                continue
            if rect_circle_collide(brect, pu.x, pu.y, pu.r):
                if pu.kind == "shield":
                    self.bird.shield = SHIELD_TIME
                elif pu.kind == "slow":
                    self.slowmo = SLOW_TIME
                self.powerups.remove(pu)

        if self.boss is None and self.score >= self.next_boss_at:
            self.spawn_boss()

        if self.boss is not None:
            self.boss.update(edt, self.bird)
            b = self.boss.try_fire(self.bird)
            if b: self.bullets.append(b)
            for blt in list(self.bullets):
                blt.update(edt)
                if blt.dead:
                    self.bullets.remove(blt); continue
                if rect_circle_collide(brect, blt.x, blt.y, blt.r):
                    if self.bird.hit(): self.dead()
                    else:
                        self.hit_fx(blt.x, self.bird.y)
                        blt.dead = True
                        if blt in self.bullets: self.bullets.remove(blt)

            self.boss_time -= dt
            if self.boss_time <= 0.0 and not self.boss.outro:
                self.level += 1
                self.score += 3
                self.boss.outro = True
                self.screenshake = 0.5

            if self.boss.dead:
                self.boss = None
                self.next_boss_at += BOSS_EVERY
                self.spawn_timer = 0.0
                self.next_spawn_delay = randf(*SPAWN_EVERY_RANGE)
                self.bullets.clear()

    def hit_fx(self, x, y):
        for _ in range(12):
            ang = randf(0, 2*math.pi)
            spd = randf(80, 160)
            self.particles.append(Particle(x, y, math.cos(ang)*spd, math.sin(ang)*spd, 2, CYAN, 0.4))
        self.screenshake = max(self.screenshake, 0.2)

    def dead(self):
        self.state = "dead"
        self.bird.dead = True
        self.best = max(self.best, self.score)

    def draw_bg(self):
        self.screen.fill(BG)

    def draw_ground(self):
        pygame.draw.rect(self.screen, (44, 44, 58), (0, HEIGHT-GROUND_H, WIDTH, GROUND_H))

    def draw(self):
        self.draw_bg()
        for p in self.pipes: p.draw(self.screen)
        for pu in self.powerups: pu.draw(self.screen)
        if self.boss is not None:
            self.boss.draw(self.screen)
            for blt in self.bullets: blt.draw(self.screen)
        for pr in self.particles: pr.draw(self.screen)
        self.draw_ground()
        self.bird.draw(self.screen, time_scale=(0.6 if self.slowmo>0 else 1.0))

        score_surf = self.big.render(str(self.score), True, FG)
        self.screen.blit(score_surf, (WIDTH//2 - score_surf.get_width()//2, 20))
        best_text = self.font.render(f"best: {self.best}", True, CYAN)
        self.screen.blit(best_text, (10, 10))

        if self.state == "ready":
            self.draw_center_text("Click/Space to start", "W/↑/Space to flap — Boss every 10!")
        elif self.state == "paused":
            self.draw_center_text("Paused", "Press P to resume")
        elif self.state == "dead":
            self.draw_center_text(f"Game Over — score {self.score}", "Press R or click to restart")

        if self.boss is not None and not self.boss.intro:
            timer_text = self.small.render(f"Survive {int(self.boss_time)}s", True, CYAN)
            self.screen.blit(timer_text, (WIDTH//2 - timer_text.get_width()//2, 40))
            label = self.small.render(f"Boss L{self.level}", True, FG)
            self.screen.blit(label, (60, 30))

        if self.slowmo > 0.0:
            t = self.small.render("SLOW-MO", True, GREEN)
            self.screen.blit(t, (WIDTH - t.get_width() - 12, 10))
        if self.bird.shield > 0.0:
            s = self.small.render("SHIELD", True, CYAN)
            self.screen.blit(s, (WIDTH - s.get_width() - 12, 28))

        pygame.display.flip()

    def draw_center_text(self, title, subtitle):
        t = self.big.render(title, True, FG)
        s = self.font.render(subtitle, True, FG)
        x = WIDTH//2
        self.screen.blit(t, (x - t.get_width()//2, HEIGHT//2 - 70))
        self.screen.blit(s, (x - s.get_width()//2, HEIGHT//2 - 20))

    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                self.handle_input(e)
            if self.state != "paused": self.update(dt)
            self.draw()

if __name__ == "__main__":
    Game().run()
