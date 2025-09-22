import math
import sys
import pygame

# -----------------------------
# Simulation parameters (tweak)
# -----------------------------
ROAD_LEN_M      = 10_000.0       # 10 km vertical road
LANE_WIDTH_M    = 3.5            # per requirement
LANES           = 1             # adjustable; total width = LANES * 3.5 m
BASE_SCALE      = 10.0           # base pixels per meter before zoom
TARGET_KMH      = 120.0          # speed cap
AUTO_MODE       = True           # auto accelerate/cruise/stop at road end
FOLLOW_TRUCK    = False          # toggle with 'C'

# Truck physical parameters
MASS_KG         = 20_000.0
CD              = 0.8
FRONTAL_AREA    = 8.0
CRR             = 0.006
AIR_DENS        = 1.225
MU_TIRE         = 0.8

P_MAX_W         = 300_000.0
A_BRAKE_COMF    = 3.0
A_BRAKE_MAX     = 4.5

# Truck drawing parameters
TRUCK_LEN_M     = 8.0
TRUCK_WID_M     = 2.5

# Window and drawing
WIN_W           = 1000
WIN_H           = 800
FPS             = 60

def kmh_to_ms(kmh): return kmh / 3.6
def ms_to_kmh(ms):  return ms * 3.6
TARGET_MS = kmh_to_ms(TARGET_KMH)

pygame.init()
screen = pygame.display.set_mode((WIN_W, WIN_H))
clock  = pygame.time.Clock()
font   = pygame.font.SysFont("consolas", 18)

GREY    = (85, 85, 85)
DARK    = (30, 30, 30)
WHITE   = (240, 240, 240)
YELLOW  = (240, 220, 0)
RED     = (220, 40, 40)
GREEN   = (60, 200, 80)
LINE    = (210, 210, 210)

s = 0.0
v = 0.0
a = 0.0

int_err = 0.0
Kp = 0.8
Ki = 0.2

cam_cx = (LANES * LANE_WIDTH_M) * 0.5
cam_cy = ROAD_LEN_M * 0.15
zoom   = 1.0

PAN_SPEED_MPS = 80.0
PAN_SPEED_FAST = 200.0
ZOOM_STEP = 1.1

def resist_forces(v_ms):
    F_rr = CRR * MASS_KG * 9.81
    F_d  = 0.5 * AIR_DENS * CD * FRONTAL_AREA * v_ms * v_ms
    return F_rr + F_d

def traction_force_from_power(v_ms, throttle):
    v_eff = max(v_ms, 0.5)
    F_power = (P_MAX_W * max(0.0, min(1.0, throttle))) / v_eff
    F_mu = MU_TIRE * MASS_KG * 9.81
    return min(F_power, F_mu)

def brake_force_from_command(brake_cmd):
    brake_cmd = max(0.0, min(1.0, brake_cmd))
    return brake_cmd * MASS_KG * A_BRAKE_MAX

def stopping_distance(v_ms, a_dec):
    if a_dec <= 0.0:
        return float('inf')
    return v_ms * v_ms / (2.0 * a_dec)

def controller(dt, s, v, remaining_m):
    global int_err
    margin = 20.0
    need_brake_for_end = remaining_m < (stopping_distance(v, A_BRAKE_COMF) + margin)
    v_ref = TARGET_MS if not need_brake_for_end else 0.0
    err = v_ref - v
    int_err += err * dt
    a_des = Kp * err + Ki * int_err
    a_des = max(-A_BRAKE_MAX, min(1.5, a_des))
    F_res = resist_forces(v)
    throttle = 0.0
    brake    = 0.0
    if a_des >= 0.0:
        F_need = MASS_KG * a_des + F_res
        lo, hi = 0.0, 1.0
        for _ in range(12):
            mid = 0.5 * (lo + hi)
            if traction_force_from_power(v, mid) >= F_need:
                hi = mid
            else:
                lo = mid
        throttle = hi
    else:
        F_need_brake = max(0.0, MASS_KG * (-a_des) - F_res)
        brake = min(1.0, F_need_brake / (MASS_KG * A_BRAKE_MAX))
    return throttle, brake

def scale_px_per_m():
    return BASE_SCALE * zoom

def world_to_screen(xm, ym):
    S = scale_px_per_m()
    xs = WIN_W * 0.5 + (xm - cam_cx) * S
    ys = WIN_H * 0.5 + (cam_cy - ym) * S
    return int(xs), int(ys)

def screen_to_world(xs, ys):
    S = scale_px_per_m()
    xm = cam_cx + (xs - WIN_W * 0.5) / S
    ym = cam_cy - (ys - WIN_H * 0.5) / S
    return xm, ym

def zoom_at_cursor(factor, mouse_pos):
    global zoom, cam_cx, cam_cy
    if factor <= 0.0:
        return
    mx, my = mouse_pos
    wx_before, wy_before = screen_to_world(mx, my)
    zoom *= factor
    zoom = max(0.05, min(20.0, zoom))
    wx_after, wy_after = screen_to_world(mx, my)
    cam_cx += (wx_before - wx_after)
    cam_cy += (wy_before - wy_after)

def draw_lane_markings():
    S = scale_px_per_m()
    total_w_m = LANES * LANE_WIDTH_M
    left_x = 0.0
    right_x = total_w_m
    top_y = ROAD_LEN_M
    bot_y = 0.0

    x0s, y0s = world_to_screen(left_x, bot_y)
    x1s, y1s = world_to_screen(right_x, top_y)
    rect = pygame.Rect(min(x0s, x1s), min(y0s, y1s), abs(x1s - x0s), abs(y1s - y0s))
    pygame.draw.rect(screen, GREY, rect)

    xls, _ = world_to_screen(left_x, 0.0)
    xrs, _ = world_to_screen(right_x, 0.0)
    _, yts = world_to_screen(0.0, top_y)
    _, ybs = world_to_screen(0.0, bot_y)
    pygame.draw.line(screen, WHITE, (xls, yts), (xls, ybs), max(1, int(2 * zoom)))
    pygame.draw.line(screen, WHITE, (xrs, yts), (xrs, ybs), max(1, int(2 * zoom)))

    dash_m = 10.0
    gap_m  = 10.0
    for li in range(1, LANES):
        x_m = li * LANE_WIDTH_M
        xs, _ = world_to_screen(x_m, 0.0)
        _, y_world_top = screen_to_world(0, 0)
        _, y_world_bot = screen_to_world(0, WIN_H)
        y_min = max(0.0, min(y_world_top, y_world_bot))
        y_max = min(ROAD_LEN_M, max(y_world_top, y_world_bot))
        start = y_min - ((y_min) % (dash_m + gap_m))
        y = start
        while y < y_max:
            y2 = min(y + dash_m, y_max)
            _, ys1 = world_to_screen(0.0, y)
            _, ys2 = world_to_screen(0.0, y2)
            pygame.draw.line(screen, LINE, (xs, ys1), (xs, ys2), max(1, int(2 * zoom)))
            y += dash_m + gap_m  # FIXED: removed stray parenthesis

def draw_truck(s):
    x_center = (LANES * LANE_WIDTH_M) * 0.5
    y_center = s
    S = scale_px_per_m()
    truck_w_px = int(TRUCK_WID_M * S)
    truck_h_px = int(TRUCK_LEN_M * S)
    xs, ys = world_to_screen(x_center, y_center)
    rect = pygame.Rect(xs - truck_w_px // 2, ys - truck_h_px // 2, truck_w_px, truck_h_px)
    pygame.draw.rect(screen, RED, rect, border_radius=3)

def draw_scale_bar():
    S = scale_px_per_m()
    nice = [1,2,5]
    target_px = 220
    candidates = []
    for n in range(-3, 6):
        for k in nice:
            candidates.append(k * (10 ** n))
    best = candidates[0]
    best_err = abs(best * S - target_px)
    for c in candidates:
        err = abs(c * S - target_px)
        if err < best_err:
            best = c
            best_err = err
    length_m = max(1e-6, best)
    bar_px = length_m * S
    x0 = 20
    y0 = WIN_H - 40
    pygame.draw.line(screen, WHITE, (x0, y0), (x0 + int(bar_px), y0), 3)
    pygame.draw.line(screen, WHITE, (x0, y0 - 8), (x0, y0 + 8), 2)
    pygame.draw.line(screen, WHITE, (x0 + int(bar_px), y0 - 8), (x0 + int(bar_px), y0 + 8), 2)
    sub_m = 1.0
    if S < 15:
        sub_m = 5.0 if S >= 3.0 else 10.0
    n_sub = int(length_m // sub_m)
    for i in range(1, n_sub):
        xi = x0 + int(i * sub_m * S)
        pygame.draw.line(screen, WHITE, (xi, y0 - 5), (xi, y0 + 5), 1)
    label = f"{length_m:g} m   |   zoom {zoom:.2f}x   |   {S:.1f} px/m"
    text = font.render(label, True, WHITE)
    screen.blit(text, (x0, y0 + 10))

def draw_hud():
    kmh = ms_to_kmh(v)
    text1 = font.render(f"Speed: {kmh:6.1f} km/h   Accel: {a:5.2f} m/s^2", True, WHITE)
    text2 = font.render(f"Distance: {s:7.1f} m / {ROAD_LEN_M:.0f} m", True, WHITE)
    text3 = font.render("Controls: Wheel zoom, Right-drag pan, Arrows/WASD pan, +/- zoom, C follow, R reset", True, GREEN)
    screen.blit(text1, (16, 12))
    screen.blit(text2, (16, 36))
    screen.blit(text3, (16, 60))

def main():
    global s, v, a, int_err, cam_cx, cam_cy, zoom, FOLLOW_TRUCK
    running = True
    dragging = False
    last_mouse = (0, 0)
    while running:
        dt = clock.tick(FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEWHEEL:
                factor = ZOOM_STEP if event.y > 0 else (1.0 / ZOOM_STEP)
                zoom_at_cursor(factor, pygame.mouse.get_pos())
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 3:  # right mouse drag to pan
                    dragging = True
                    last_mouse = event.pos
                # Optional wheel fallback (older backends may emit 4/5 instead of MOUSEWHEEL)
                elif event.button == 4:
                    zoom_at_cursor(ZOOM_STEP, event.pos)
                elif event.button == 5:
                    zoom_at_cursor(1.0/ZOOM_STEP, event.pos)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 3:
                    dragging = False
            elif event.type == pygame.MOUSEMOTION and dragging:
                mx, my = event.pos
                dx = mx - last_mouse[0]
                dy = my - last_mouse[1]
                last_mouse = (mx, my)
                S = scale_px_per_m()
                cam_cx -= dx / S
                cam_cy += dy / S
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_c:
                    FOLLOW_TRUCK = not FOLLOW_TRUCK
                elif event.key == pygame.K_r:
                    zoom   = 1.0
                    cam_cx = (LANES * LANE_WIDTH_M) * 0.5
                    cam_cy = ROAD_LEN_M * 0.15
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                    zoom_at_cursor(ZOOM_STEP, (WIN_W//2, WIN_H//2))
                elif event.key == pygame.K_MINUS:
                    zoom_at_cursor(1.0/ZOOM_STEP, (WIN_W//2, WIN_H//2))

        keys = pygame.key.get_pressed()
        pan = PAN_SPEED_MPS * dt
        if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
            pan = PAN_SPEED_FAST * dt
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            cam_cx -= pan
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            cam_cx += pan
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            cam_cy += pan
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            cam_cy -= pan

        if FOLLOW_TRUCK:
            cam_cx = (LANES * LANE_WIDTH_M) * 0.5
            cam_cy = s - (WIN_H * 0.3) / scale_px_per_m()

        remaining = max(0.0, ROAD_LEN_M - s)
        if AUTO_MODE:
            throttle, brake = controller(dt, s, v, remaining)
        else:
            throttle = 0.0
            brake    = 0.0

        F_res   = resist_forces(v)
        F_trac  = traction_force_from_power(v, throttle)
        F_brake = brake_force_from_command(brake)

        F_net = F_trac - F_res - F_brake
        a = F_net / MASS_KG

        v = max(0.0, v + a * dt)
        v = min(v, TARGET_MS)
        s = s + v * dt
        if s >= ROAD_LEN_M:
            s = ROAD_LEN_M
            v = 0.0
            a = 0.0

        screen.fill(DARK)
        draw_lane_markings()
        draw_truck(s)
        draw_scale_bar()
        draw_hud()
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
