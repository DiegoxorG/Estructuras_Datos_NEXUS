import json
import os
import sys
import pygame
import math
import copy

PANEL_W = 230   # right sidebar width
STATUS_H = 36   # bottom status bar height

# Las coordenadas del editor son las del JUEGO (la imagen original por
# mundo.ESCALA_MAPA), y los rectángulos se guardan pegados a los píxeles de la
# imagen original (múltiplos de PIXEL_MUNDO): así el juego los pone
# exactamente donde se ven aquí (int(rx * ancho) da un entero exacto).
PIXEL_MUNDO = 1
# Niveles de zoom: cuántos píxeles de pantalla mide un píxel de la imagen
# original. Desde 1 son enteros: cada píxel del dibujo es un cuadro exacto
# y los bordes de las hitboxes coinciden con los del dibujo.
ZOOMS_PIXEL = [0.25, 0.33, 0.5, 0.75, 1, 2, 3, 4, 6, 8, 12]

# ── Helper functions ──────────────────────────────────────────────────────────

def load_image(path):
    return pygame.image.load(path)


def clamp_rect_to_image(rect, img_rect):
    x1 = max(img_rect.left, min(rect.left, img_rect.right))
    y1 = max(img_rect.top, min(rect.top, img_rect.bottom))
    x2 = max(img_rect.left, min(rect.right, img_rect.right))
    y2 = max(img_rect.top, min(rect.bottom, img_rect.bottom))
    return pygame.Rect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))


def _al_pixel(v):
    """Redondea al borde de píxel de la imagen original más cercano."""
    return int(round(v / PIXEL_MUNDO)) * PIXEL_MUNDO


def normalize_rect(rect, img_rect):
    x0, y0 = _al_pixel(rect.x - img_rect.x), _al_pixel(rect.y - img_rect.y)
    x1, y1 = _al_pixel(rect.right - img_rect.x), _al_pixel(rect.bottom - img_rect.y)
    x1, y1 = max(x1, x0 + PIXEL_MUNDO), max(y1, y0 + PIXEL_MUNDO)
    return {
        "rx": x0 / img_rect.width,
        "ry": y0 / img_rect.height,
        "rw": (x1 - x0) / img_rect.width,
        "rh": (y1 - y0) / img_rect.height,
    }


def denormalize_rect(data, img_rect):
    # Igual que el juego (Mundo._cargar_hitboxes): int() de cada valor.
    return pygame.Rect(
        img_rect.x + int(data["rx"] * img_rect.width),
        img_rect.y + int(data["ry"] * img_rect.height),
        max(1, int(data["rw"] * img_rect.width)),
        max(1, int(data["rh"] * img_rect.height)),
    )


def point_to_line_distance(point, line_start, line_end):
    px, py = point
    x1, y1 = line_start
    x2, y2 = line_end
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def line_thickness_px(hitbox, img_rect, default_px=8):
    return max(1, int(hitbox.get("thickness", default_px / img_rect.width) * img_rect.width))


def collides_rect_with_hitbox(rect, h, img_rect):
    if h["type"] == "rect":
        return rect.colliderect(denormalize_rect(h, img_rect))
    if h["type"] == "circle":
        cx = img_rect.x + int(h["cx"] * img_rect.width)
        cy = img_rect.y + int(h["cy"] * img_rect.height)
        r = max(4, int(h["r"] * img_rect.width))
        nx = max(rect.left, min(cx, rect.right))
        ny = max(rect.top, min(cy, rect.bottom))
        return (cx - nx) ** 2 + (cy - ny) ** 2 <= r * r
    if h["type"] == "line":
        x1 = img_rect.x + h["x1"] * img_rect.width
        y1 = img_rect.y + h["y1"] * img_rect.height
        x2 = img_rect.x + h["x2"] * img_rect.width
        y2 = img_rect.y + h["y2"] * img_rect.height
        thickness = line_thickness_px(h, img_rect)
        steps = max(1, int(max(abs(x2 - x1), abs(y2 - y1)) / 3))
        radius = max(2, thickness // 2)
        for i in range(steps + 1):
            t = i / steps
            px = int(x1 + (x2 - x1) * t)
            py = int(y1 + (y2 - y1) * t)
            if rect.colliderect(pygame.Rect(px - radius, py - radius, radius * 2, radius * 2)):
                return True
    return False


def save_hitboxes(out_path, hitboxes, img_rect, image_path,
                  spawn_data=None, npc_positions=None, decoracion=None):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    abs_image_path = os.path.abspath(image_path)
    abs_images_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Imagenes"))
    if abs_image_path.startswith(abs_images_root):
        image_rel = os.path.relpath(
            abs_image_path,
            os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        )
    else:
        image_rel = os.path.join("Imagenes", os.path.basename(image_path))
    payload = {
        "image": image_rel,
        "image_size": [img_rect.width, img_rect.height],
        "hitboxes": hitboxes,
        "spawn": spawn_data or {},
        "npc_positions": npc_positions or {},
        "decoracion": decoracion or [],
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def load_hitboxes(in_path):
    with open(in_path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    hitboxes = payload.get("hitboxes", [])
    for h in hitboxes:
        if "type" not in h:
            h["type"] = "rect"
        if "role" not in h:
            h["role"] = "wall"
        if h["role"] == "interactable" and "action" not in h:
            h["action"] = "puerta"
        if h["role"] == "interactable" and "target_image" not in h:
            h["target_image"] = ""
        if h["role"] == "interactable" and h.get("action") == "npc":
            h.setdefault("npc_character", "Sara")
            h.setdefault("npc_animation", "Sara_dibujando.png")
    return (hitboxes,
            payload.get("spawn", {}),
            payload.get("npc_positions", {}),
            payload.get("decoracion", None))   # None = key absent (migration needed)


def build_dummy_from_game_logic(project_root, img_rect, tamano_nativo=None):
    """Rect del modo de prueba, con el MISMO hitbox que usan los personajes.

    Toma el hitbox real de un personaje de Imagenes/Personajes/ (el primero
    que tenga sprites) y lo convierte a las coordenadas de este editor: el
    juego dibuja el mapa a mundo.ESCALA_MAPA del archivo original y el editor
    lo dibuja a otro tamaño, así que se ajusta por proporción para que el
    cuadrito de prueba ocupe lo mismo respecto al mapa que el personaje real.

    `tamano_nativo` es el (ancho, alto) del archivo de imagen sin escalar.
    """
    default = pygame.Rect(img_rect.centerx - 14, img_rect.centery - 14, 28, 28)
    try:
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from Movimiento.Personaje import Personaje, detectar_hojas
        from juego import mundo as mundo_juego
        personajes_dir = os.path.join(project_root, "Imagenes", "Personajes")
        carpeta = None
        for nombre in sorted(os.listdir(personajes_dir)):
            ruta = os.path.join(personajes_dir, nombre)
            if os.path.isdir(ruta) and detectar_hojas(ruta):
                carpeta = ruta
                break
        if carpeta is None:
            return default

        personaje = Personaje(0, 0, carpeta, velocidad=4, fps_animacion=8)

        if tamano_nativo:
            ancho_juego = tamano_nativo[0] * mundo_juego.ESCALA_MAPA
            alto_juego = tamano_nativo[1] * mundo_juego.ESCALA_MAPA
        else:
            ancho_juego, alto_juego = img_rect.width, img_rect.height

        hb = pygame.Rect(
            0, 0,
            max(4, round(personaje.hitbox.width * img_rect.width / max(1, ancho_juego))),
            max(4, round(personaje.hitbox.height * img_rect.height / max(1, alto_juego))),
        )
        hb.center = img_rect.center
        hb.clamp_ip(img_rect)
        print(f"[modo prueba] hitbox del personaje {os.path.basename(carpeta)}: "
              f"{personaje.hitbox.width}x{personaje.hitbox.height} en el juego "
              f"-> {hb.width}x{hb.height} en este editor")
        return hb
    except Exception as e:
        print(f"[modo prueba] no se pudo leer el hitbox del personaje ({e}); "
              f"se usa un cuadro de {default.width}x{default.height}")
        return default


# ── Image picker GUI ─────────────────────────────────────────────────────────

def choose_image_gui(scan_dir, title="Elegir imagen"):
    """
    Muestra un selector visual de imágenes con thumbnails.
    Devuelve la ruta absoluta elegida, o None si el usuario cancela.
    Asume que pygame.init() ya fue llamado.
    """
    valid_ext = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

    # Recopilar imágenes
    entries = []
    if os.path.isdir(scan_dir):
        for root, _, files in os.walk(scan_dir):
            for f in sorted(files):
                if os.path.splitext(f)[1].lower() in valid_ext:
                    fp = os.path.join(root, f)
                    rel = os.path.relpath(fp, scan_dir)
                    entries.append((rel, fp))
    entries.sort(key=lambda x: x[0].lower())

    if not entries:
        return None

    THUMB_W, THUMB_H = 200, 130
    LABEL_H = 34
    GAP = 10
    CELL_W = THUMB_W + GAP
    CELL_H = THUMB_H + LABEL_H + GAP
    SEARCH_H = 48
    PADDING = 14

    di = pygame.display.Info()
    WIN_W = min(1400, di.current_w)
    WIN_H = min(900, di.current_h)
    cols = max(1, (WIN_W - PADDING * 2) // CELL_W)

    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption(title)
    picker_clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 15)
    big_font = pygame.font.SysFont("consolas", 20, bold=True)

    thumb_cache = {}

    def get_thumb(fp):
        if fp in thumb_cache:
            return thumb_cache[fp]
        try:
            img = pygame.image.load(fp)
            iw, ih = img.get_size()
            s = min(THUMB_W / iw, THUMB_H / ih, 1.0)
            t = pygame.transform.smoothscale(img, (max(1, int(iw * s)), max(1, int(ih * s))))
            thumb_cache[fp] = t
        except Exception:
            thumb_cache[fp] = None
        return thumb_cache[fp]

    filter_text = ""
    scroll_y = 0
    selected_idx = 0
    grid_top = SEARCH_H + 4

    def filtered():
        ft = filter_text.lower()
        return [(r, fp) for r, fp in entries if not ft or ft in r.lower()]

    running = True
    result = None

    while running:
        images = filtered()
        rows = math.ceil(len(images) / cols) if images else 0
        grid_area_h = WIN_H - grid_top
        total_h = rows * CELL_H + PADDING
        max_scroll = max(0, total_h - grid_area_h)
        scroll_y = min(scroll_y, max_scroll)

        # Mantener selected visible
        if images and 0 <= selected_idx < len(images):
            sel_row = selected_idx // cols
            sel_top = sel_row * CELL_H
            sel_bot = sel_top + CELL_H
            if sel_top < scroll_y:
                scroll_y = sel_top
            elif sel_bot > scroll_y + grid_area_h:
                scroll_y = sel_bot - grid_area_h

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEWHEEL:
                scroll_y = max(0, min(scroll_y - event.y * 40, max_scroll))
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                if my >= grid_top and images:
                    col_i = (mx - PADDING) // CELL_W
                    row_i = (my - grid_top + scroll_y) // CELL_H
                    if 0 <= col_i < cols:
                        idx = row_i * cols + col_i
                        if 0 <= idx < len(images):
                            if idx == selected_idx:
                                result = images[idx][1]
                                running = False
                            else:
                                selected_idx = idx
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if images and 0 <= selected_idx < len(images):
                        result = images[selected_idx][1]
                        running = False
                elif event.key == pygame.K_BACKSPACE:
                    filter_text = filter_text[:-1]
                    selected_idx = 0
                    scroll_y = 0
                elif event.key == pygame.K_RIGHT:
                    selected_idx = min(len(images) - 1, selected_idx + 1)
                elif event.key == pygame.K_LEFT:
                    selected_idx = max(0, selected_idx - 1)
                elif event.key == pygame.K_DOWN:
                    selected_idx = min(len(images) - 1, selected_idx + cols)
                elif event.key == pygame.K_UP:
                    selected_idx = max(0, selected_idx - cols)
                elif event.unicode and event.unicode.isprintable():
                    filter_text += event.unicode
                    selected_idx = 0
                    scroll_y = 0

        # ── Render picker ─────────────────────────────────────────────────────
        screen.fill((22, 22, 32))

        # Barra superior
        pygame.draw.rect(screen, (35, 36, 52), pygame.Rect(0, 0, WIN_W, SEARCH_H))
        screen.blit(big_font.render(title, True, (210, 215, 240)), (PADDING, 8))
        filter_lbl = font.render(
            f"  Filtro: {filter_text}_    {len(images)} imagen{'es' if len(images) != 1 else ''} "
            f"   Flechas=navegar  Enter=abrir  Escribe=filtrar  ESC=salir",
            True, (140, 200, 160))
        screen.blit(filter_lbl, (PADDING + big_font.size(title)[0] + 16, 14))
        pygame.draw.line(screen, (55, 58, 78), (0, SEARCH_H), (WIN_W, SEARCH_H), 1)

        # Grid de thumbnails
        screen.set_clip(pygame.Rect(0, grid_top, WIN_W, grid_area_h))
        for i, (rel, fp) in enumerate(images):
            col_i = i % cols
            row_i = i // cols
            cx = PADDING + col_i * CELL_W
            cy = grid_top + row_i * CELL_H - scroll_y + GAP // 2
            if cy + CELL_H < grid_top or cy > WIN_H:
                continue

            is_sel = (i == selected_idx)
            bg_col = (52, 58, 82) if is_sel else (34, 36, 50)
            border_col = (100, 150, 255) if is_sel else (50, 54, 72)
            cell_r = pygame.Rect(cx, cy, CELL_W - GAP, CELL_H - GAP)
            pygame.draw.rect(screen, bg_col, cell_r, border_radius=6)
            pygame.draw.rect(screen, border_col, cell_r, 2 if is_sel else 1, border_radius=6)

            # Thumbnail
            thumb = get_thumb(fp)
            thumb_area = pygame.Rect(cx + 2, cy + 2, THUMB_W - 4, THUMB_H - 4)
            if thumb:
                tw, th = thumb.get_size()
                tx = cx + 2 + (THUMB_W - 4 - tw) // 2
                ty = cy + 2 + (THUMB_H - 4 - th) // 2
                screen.blit(thumb, (tx, ty))
            else:
                pygame.draw.rect(screen, (44, 46, 64), thumb_area, border_radius=4)
                q = font.render("sin preview", True, (80, 80, 100))
                screen.blit(q, q.get_rect(center=thumb_area.center))

            # Nombre
            name = os.path.basename(rel)
            if font.size(name)[0] > CELL_W - GAP - 8:
                while font.size(name + "…")[0] > CELL_W - GAP - 8 and name:
                    name = name[:-1]
                name += "…"
            col_txt = (230, 235, 255) if is_sel else (150, 155, 180)
            lbl = font.render(name, True, col_txt)
            screen.blit(lbl, (cx + (CELL_W - GAP - lbl.get_width()) // 2,
                               cy + THUMB_H + 6))

        screen.set_clip(None)

        # Scrollbar
        if max_scroll > 0:
            sb_track = pygame.Rect(WIN_W - 8, grid_top, 6, grid_area_h)
            pygame.draw.rect(screen, (40, 42, 58), sb_track)
            sb_h = max(20, int(grid_area_h * grid_area_h / max(total_h, 1)))
            sb_y = grid_top + int(scroll_y / max_scroll * (grid_area_h - sb_h))
            pygame.draw.rect(screen, (90, 100, 140),
                             pygame.Rect(WIN_W - 8, sb_y, 6, sb_h), border_radius=3)

        pygame.display.flip()
        picker_clock.tick(60)

    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    clock = pygame.time.Clock()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)


    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        if not os.path.isabs(image_path):
            image_path = os.path.join(project_root, image_path)
    else:
        backgrounds_dir = os.path.join(project_root, "Imagenes", "Fondos")
        image_path = choose_image_gui(backgrounds_dir,
                                      "Elegir fondo — Editor de Hitboxes  (doble clic o Enter)")
        if image_path is None:
            pygame.quit()
            return

    if not os.path.isabs(image_path):
        image_path = os.path.join(project_root, image_path)
    if not os.path.exists(image_path):
        print(f"No existe la imagen: {image_path}")
        return

    raw_image = load_image(image_path)
    iw, ih = raw_image.get_size()
    max_w, max_h = 1600, 950
    fit_scale = min(max_w / iw, max_h / ih, 1.0)
    view_w = int(iw * fit_scale)
    # Antes el mundo del editor era la imagen reescalada a ~1300 px (con
    # bordes que no caían en los píxeles del dibujo). Ahora es el mundo del
    # juego; U pasa los tamaños fijos de antes (sitios de NPC, decoración,
    # tolerancias) a la escala nueva para que se sientan igual.
    global PIXEL_MUNDO
    try:
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from juego.mundo import ESCALA_MAPA
    except Exception:
        ESCALA_MAPA = 3
    PIXEL_MUNDO = ESCALA_MAPA
    world_w, world_h = iw * ESCALA_MAPA, ih * ESCALA_MAPA
    U = world_w / max(1, int(view_w * 1.35))

    padding = 20
    ui_h = 180
    display_info = pygame.display.Info()
    win_w = display_info.current_w
    win_h = display_info.current_h

    screen = pygame.display.set_mode((win_w, win_h), pygame.NOFRAME)
    pygame.display.set_caption("Editor de Hitboxes")
    raw_image = raw_image.convert()

    font = pygame.font.SysFont("consolas", 20)
    small = pygame.font.SysFont("consolas", 16)
    tiny = pygame.font.SysFont("consolas", 13)

    def draw_wrapped_text(surface, text, font_obj, color, x, y, max_width, line_gap=4):
        words = text.split(" ")
        line = ""
        yy = y
        for word in words:
            test = f"{line} {word}".strip()
            if font_obj.size(test)[0] <= max_width:
                line = test
            else:
                surface.blit(font_obj.render(line, True, color), (x, yy))
                yy += font_obj.get_height() + line_gap
                line = word
        if line:
            surface.blit(font_obj.render(line, True, color), (x, yy))
            yy += font_obj.get_height() + line_gap
        return yy

    # ── Layout ────────────────────────────────────────────────────────────────
    viewport_w = max(100, win_w - padding * 2 - PANEL_W)
    viewport_h = max(100, win_h - padding * 2 - ui_h - STATUS_H)
    viewport_rect = pygame.Rect(padding, padding, viewport_w, viewport_h)
    panel_x = win_w - PANEL_W
    panel_rect = pygame.Rect(panel_x, 0, PANEL_W, win_h - STATUS_H)
    status_rect_layout = pygame.Rect(0, win_h - STATUS_H, win_w, STATUS_H)
    world_rect = pygame.Rect(0, 0, world_w, world_h)
    camera_x = 0.0
    camera_y = 0.0

    # ── Zoom ──────────────────────────────────────────────────────────────────
    # zoom = píxeles de pantalla por unidad del mundo (del juego). Los niveles
    # salen de ZOOMS_PIXEL (pantalla por píxel de la imagen original), más uno
    # que deja ver el mapa entero.
    cabe = min(viewport_w / world_w, viewport_h / world_h)
    niveles_zoom = sorted({cabe} | {k / ESCALA_MAPA for k in ZOOMS_PIXEL if k / ESCALA_MAPA > cabe})
    # Al abrir: como antes (el mapa un poco más grande que la ventana).
    zoom_i = min(range(len(niveles_zoom)), key=lambda i: abs(niveles_zoom[i] - cabe * 1.35))
    zoom = niveles_zoom[zoom_i]
    mapa_cache = {}       # zoom -> mapa entero escalado (solo para zooms chicos)

    def clamp_camera():
        """La cámara (esquina del viewport, en el mundo) siempre en un píxel
        entero de pantalla: así el dibujo y las hitboxes no se corren."""
        nonlocal camera_x, camera_y
        vista_w, vista_h = viewport_rect.width / zoom, viewport_rect.height / zoom
        if world_rect.width <= vista_w:
            camera_x = (world_rect.width - vista_w) / 2
        else:
            camera_x = max(0, min(camera_x, world_rect.width - vista_w))
        if world_rect.height <= vista_h:
            camera_y = (world_rect.height - vista_h) / 2
        else:
            camera_y = max(0, min(camera_y, world_rect.height - vista_h))
        camera_x = round(camera_x * zoom) / zoom
        camera_y = round(camera_y * zoom) / zoom

    def center_camera_on_rect(rect):
        nonlocal camera_x, camera_y
        camera_x = rect.centerx - viewport_rect.width / zoom / 2
        camera_y = rect.centery - viewport_rect.height / zoom / 2
        clamp_camera()

    def screen_to_world(pos):
        sx, sy = pos
        if not viewport_rect.collidepoint(sx, sy):
            return None
        return (int(math.floor((sx - viewport_rect.x) / zoom + camera_x)),
                int(math.floor((sy - viewport_rect.y) / zoom + camera_y)))

    def world_to_screen(pos):
        wx, wy = pos
        return ((wx - camera_x) * zoom + viewport_rect.x, (wy - camera_y) * zoom + viewport_rect.y)

    def rect_to_screen(rect):
        """Un Rect del mundo en la pantalla, redondeando las dos esquinas (no
        el ancho): así dos rects pegados en el mundo quedan pegados aquí."""
        x0, y0 = world_to_screen(rect.topleft)
        x1, y1 = world_to_screen(rect.bottomright)
        x0, y0, x1, y1 = round(x0), round(y0), round(x1), round(y1)
        return pygame.Rect(x0, y0, max(1, x1 - x0), max(1, y1 - y0))

    def set_zoom(nuevo_i, ancla=None):
        """Cambia el zoom dejando quieto el punto del mundo bajo `ancla`
        (posición en pantalla; por defecto el centro del viewport)."""
        nonlocal zoom_i, zoom, camera_x, camera_y
        nuevo_i = max(0, min(len(niveles_zoom) - 1, nuevo_i))
        if nuevo_i == zoom_i:
            return
        if ancla is None or not viewport_rect.collidepoint(ancla):
            ancla = viewport_rect.center
        wx = (ancla[0] - viewport_rect.x) / zoom + camera_x
        wy = (ancla[1] - viewport_rect.y) / zoom + camera_y
        zoom_i, zoom = nuevo_i, niveles_zoom[nuevo_i]
        camera_x = wx - (ancla[0] - viewport_rect.x) / zoom
        camera_y = wy - (ancla[1] - viewport_rect.y) / zoom
        clamp_camera()

    def draw_map():
        """El dibujo del mapa en el viewport. Con zoom chico se escala el mapa
        entero una vez (suave); con zoom grande, solo el pedazo que se ve y
        con vecino más cercano (cada píxel del dibujo, un cuadro exacto)."""
        k = zoom * ESCALA_MAPA            # píxeles de pantalla por píxel de la imagen
        prev_clip = screen.get_clip()
        screen.set_clip(viewport_rect)
        if k < 1 or abs(k - round(k)) > 1e-6:      # zoom chico o no entero: el mapa entero, una vez
            if zoom not in mapa_cache:
                mapa_cache.clear()
                mapa_cache[zoom] = pygame.transform.smoothscale(
                    raw_image, (max(1, round(iw * k)), max(1, round(ih * k))))
            ox, oy = world_to_screen((0, 0))
            screen.blit(mapa_cache[zoom], (round(ox), round(oy)))
        else:
            x0 = max(0, int(math.floor(camera_x / ESCALA_MAPA)))
            y0 = max(0, int(math.floor(camera_y / ESCALA_MAPA)))
            x1 = min(iw, int(math.ceil((camera_x + viewport_rect.width / zoom) / ESCALA_MAPA)) + 1)
            y1 = min(ih, int(math.ceil((camera_y + viewport_rect.height / zoom) / ESCALA_MAPA)) + 1)
            if x1 > x0 and y1 > y0:
                kk = int(round(k))
                pedazo = raw_image.subsurface(pygame.Rect(x0, y0, x1 - x0, y1 - y0))
                img = pygame.transform.scale(pedazo, ((x1 - x0) * kk, (y1 - y0) * kk))
                ox, oy = world_to_screen((x0 * ESCALA_MAPA, y0 * ESCALA_MAPA))
                screen.blit(img, (round(ox), round(oy)))
        screen.set_clip(prev_clip)

    clamp_camera()

    # ── Available backgrounds ─────────────────────────────────────────────────
    images_dir = os.path.join(project_root, "Imagenes", "Fondos")
    valid_ext = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    available_backgrounds = []
    if os.path.isdir(images_dir):
        for root, _, files in os.walk(images_dir):
            for f in files:
                if os.path.splitext(f)[1].lower() in valid_ext:
                    available_backgrounds.append(
                        os.path.relpath(os.path.join(root, f), images_dir))
    available_backgrounds.sort()
    if not available_backgrounds:
        available_backgrounds = [os.path.basename(image_path)]

    # ── Core hitbox state ─────────────────────────────────────────────────────
    hitboxes = []
    history = [copy.deepcopy(hitboxes)]
    history_index = 0
    dragging = False
    moving_hitbox = None
    selected_hitbox_idx = None
    selected_set = set()          # multi-select (Ctrl+A)
    move_offset = (0, 0)
    move_mode = False
    start_pos = (0, 0)
    current_rect = None
    current_shape = "rect"
    current_role = "wall"
    interactable_actions = ["puerta", "npc"]
    current_interactable_action = "puerta"
    current_target_bg_idx = 0
    current_file_name = os.path.basename(image_path)
    if current_file_name in available_backgrounds:
        current_target_bg_idx = available_backgrounds.index(current_file_name)
    current_line_thickness_px = max(1, round(8 * U))
    test_mode = False
    test_speed = 4
    test_player = pygame.Rect(0, 0, 28, 28)  # su tamaño real lo fija hb_template
    test_speed = 4   # como Personaje(velocidad=4) en el juego: el mundo es el del juego

    # ── Display options ───────────────────────────────────────────────────────
    show_walls = True
    show_interactables = True
    show_objects = True
    show_labels = True
    grid_snap = False
    GRID_SIZE = 0.01    # 1% of world per axis

    def snap_val(val, world_dim):
        if not grid_snap:
            return val
        step = max(1, int(GRID_SIZE * world_dim))
        return round(val / step) * step

    # ── Editor mode ───────────────────────────────────────────────────────────
    editor_mode = "hitbox"   # "hitbox" | "object"

    # ── Panel state ───────────────────────────────────────────────────────────
    panel_scroll = 0
    PANEL_ROW_H = 22

    # ── Spawn system ──────────────────────────────────────────────────────────
    hb_template = build_dummy_from_game_logic(project_root, world_rect, raw_image.get_size())
    spawn_rect = hb_template.copy()
    spawn_rules = {"default": None, "by_origin": {}}
    spawn_modal_active = False
    spawn_modal_options = ["Cualquier fondo"] + available_backgrounds
    spawn_modal_selected = 0
    spawn_status_message = ""
    spawn_status_timer = 0
    pending_spawn_rect = None
    npc_positions = {}
    selected_npc_name = "sara"
    npc_default_site_w = round(96 * U)
    npc_default_site_h = round(96 * U)

    def clamp_spawn_rect():
        nonlocal spawn_rect
        spawn_rect.width = hb_template.width
        spawn_rect.height = hb_template.height
        spawn_rect.clamp_ip(world_rect)

    def reset_test_player_to_spawn():
        s = spawn_rect.copy()
        s.clamp_ip(world_rect)
        test_player.topleft = s.topleft
        test_player.size = spawn_rect.size

    def set_spawn_to_mouse(mouse_pos):
        nonlocal pending_spawn_rect
        world_pos = screen_to_world(mouse_pos)
        if world_pos is None:
            return
        base = spawn_rect.copy()
        base.center = world_pos
        base.clamp_ip(world_rect)
        pending_spawn_rect = base

    def _serialize_spawn_rect(rect):
        return {"rx": rect.x / world_rect.width, "ry": rect.y / world_rect.height,
                "rw": rect.width / world_rect.width, "rh": rect.height / world_rect.height}

    def _spawn_rect_from_data(sdata):
        return pygame.Rect(
            int(float(sdata.get("rx", 0.5)) * world_rect.width),
            int(float(sdata.get("ry", 0.5)) * world_rect.height),
            spawn_rect.width, spawn_rect.height,
        )

    def _apply_loaded_spawn(spawn_payload):
        nonlocal spawn_rules, spawn_rect
        spawn_rules = {"default": None, "by_origin": {}}
        if not isinstance(spawn_payload, dict):
            return
        if "default" in spawn_payload or "by_origin" in spawn_payload:
            default_spawn = spawn_payload.get("default")
            if isinstance(default_spawn, dict):
                spawn_rules["default"] = default_spawn
                spawn_rect.x = int(default_spawn.get("rx", 0.5) * world_rect.width)
                spawn_rect.y = int(default_spawn.get("ry", 0.5) * world_rect.height)
            by_origin = spawn_payload.get("by_origin", {})
            if isinstance(by_origin, dict):
                spawn_rules["by_origin"] = {
                    str(k): v for k, v in by_origin.items()
                    if isinstance(v, dict) and "rx" in v and "ry" in v
                }
        elif "rx" in spawn_payload and "ry" in spawn_payload:
            spawn_rules["default"] = spawn_payload
            spawn_rect.x = int(spawn_payload.get("rx", 0.5) * world_rect.width)
            spawn_rect.y = int(spawn_payload.get("ry", 0.5) * world_rect.height)
        clamp_spawn_rect()
        reset_test_player_to_spawn()

    def _delete_spawn_at_world_pos(world_pos):
        nonlocal spawn_status_message, spawn_status_timer
        for origin_name in list(spawn_rules.get("by_origin", {}).keys()):
            sdata = spawn_rules["by_origin"].get(origin_name)
            if isinstance(sdata, dict) and _spawn_rect_from_data(sdata).collidepoint(world_pos):
                del spawn_rules["by_origin"][origin_name]
                spawn_status_message = f"Spawn eliminado: '{origin_name}'."
                spawn_status_timer = 180
                return True
        default_data = spawn_rules.get("default")
        if isinstance(default_data, dict) and _spawn_rect_from_data(default_data).collidepoint(world_pos):
            spawn_rules["default"] = None
            spawn_status_message = "Spawn por defecto eliminado."
            spawn_status_timer = 180
            return True
        return False

    def _serialize_world_point(world_pos):
        return {"rx": (world_pos[0] - world_rect.x) / world_rect.width,
                "ry": (world_pos[1] - world_rect.y) / world_rect.height}

    def _denormalize_world_point(data):
        return (int(world_rect.x + float(data.get("rx", 0.5)) * world_rect.width),
                int(world_rect.y + float(data.get("ry", 0.5)) * world_rect.height))

    def _set_npc_at_mouse(npc_name, mouse_pos):
        nonlocal spawn_status_message, spawn_status_timer
        world_pos = screen_to_world(mouse_pos)
        if world_pos is None:
            return
        point = _serialize_world_point(world_pos)
        point["rw"] = npc_default_site_w / world_rect.width
        point["rh"] = npc_default_site_h / world_rect.height
        npc_positions[npc_name] = point
        spawn_status_message = f"{npc_name.capitalize()} ubicado."
        spawn_status_timer = 180

    def _change_npc_site_size(npc_name, delta):
        nonlocal spawn_status_message, spawn_status_timer
        data = npc_positions.get(npc_name)
        if not isinstance(data, dict):
            spawn_status_message = f"Primero ubica {npc_name} (Shift+1/Shift+2)."
            spawn_status_timer = 180
            return
        cur_w = max(24, int(float(data.get("rw", npc_default_site_w / world_rect.width)) * world_rect.width))
        cur_h = max(24, int(float(data.get("rh", npc_default_site_h / world_rect.height)) * world_rect.height))
        new_w = max(24, min(320, cur_w + delta))
        new_h = max(24, min(320, cur_h + delta))
        data["rw"] = new_w / world_rect.width
        data["rh"] = new_h / world_rect.height
        spawn_status_message = f"Tamano de {npc_name}: {new_w}x{new_h}px."
        spawn_status_timer = 180

    def _delete_npc_at_world_pos(world_pos):
        nonlocal spawn_status_message, spawn_status_timer
        for npc_name, data in list(npc_positions.items()):
            if not isinstance(data, dict):
                continue
            nx, ny = _denormalize_world_point(data)
            if math.hypot(world_pos[0] - nx, world_pos[1] - ny) <= 24 * U:
                del npc_positions[npc_name]
                spawn_status_message = f"{npc_name.capitalize()} eliminado."
                spawn_status_timer = 180
                return True
        return False

    # ── NPC character / animation system ─────────────────────────────────────
    personajes_dir = os.path.join(project_root, "Imagenes", "Personajes")
    npc_character_options = []
    if os.path.isdir(personajes_dir):
        npc_character_options = sorted([e for e in os.listdir(personajes_dir)
                                        if os.path.isdir(os.path.join(personajes_dir, e))])
    if not npc_character_options:
        npc_character_options = ["Sara", "Diego"]
    current_npc_character_idx = 0

    def _animations_for_character(char_name):
        char_dir = os.path.join(personajes_dir, char_name)
        if not os.path.isdir(char_dir):
            return ["idle_down.png"]
        opts = sorted([fn for fn in os.listdir(char_dir) if fn.lower().endswith(".png")])
        return opts or ["idle_down.png"]

    current_npc_animation_options = _animations_for_character(npc_character_options[0])
    current_npc_animation_idx = 0
    npc_preview_cache = {}

    def _load_npc_preview_frames(character_name, animation_file):
        key = (str(character_name), str(animation_file))
        if key in npc_preview_cache:
            return npc_preview_cache[key]
        anim_path = os.path.join(personajes_dir, str(character_name), str(animation_file))
        frames = []
        try:
            sheet = pygame.image.load(anim_path).convert_alpha()
            sw, sh = sheet.get_size()
            fn_lower = str(animation_file).lower()
            is_static = any(t in fn_lower for t in ("sentado", "parado", "idle", "stand"))
            frame_count = 1 if is_static else max(1, round(sw / max(1, sh)))
            frame_w = max(1, sw // frame_count)
            for i in range(frame_count):
                frames.append(sheet.subsurface(pygame.Rect(i * frame_w, 0, frame_w, sh)).copy())
        except (OSError, pygame.error):
            pass
        npc_preview_cache[key] = frames
        return frames

    # ── Visual NPC/animation selector modals ──────────────────────────────────
    npc_char_modal = False
    npc_anim_modal = False
    npc_modal_selected = 0
    npc_anim_modal_selected = 0
    npc_modal_source = "hitbox"   # "hitbox" | "deco"
    thumbnail_cache = {}
    THUMB = 72
    THUMB_COLS = 3
    THUMB_GAP = 8

    def _load_thumbnail(char_name, anim_file=None):
        key = (char_name, anim_file)
        if key in thumbnail_cache:
            return thumbnail_cache[key]
        img = None
        try:
            if anim_file is not None:
                frames = _load_npc_preview_frames(char_name, anim_file)
                if frames:
                    f = frames[0]
                    fw, fh = f.get_size()
                    s = min(THUMB / fw, THUMB / fh, 1.0)
                    img = pygame.transform.smoothscale(f, (max(1, int(fw * s)), max(1, int(fh * s))))
            else:
                char_dir = os.path.join(personajes_dir, char_name)
                for fn in sorted(os.listdir(char_dir)):
                    if fn.lower().endswith(".png"):
                        frames = _load_npc_preview_frames(char_name, fn)
                        if frames:
                            f = frames[0]
                            fw, fh = f.get_size()
                            s = min(THUMB / fw, THUMB / fh, 1.0)
                            img = pygame.transform.smoothscale(f, (max(1, int(fw * s)), max(1, int(fh * s))))
                            break
        except Exception:
            pass
        thumbnail_cache[key] = img
        return img

    # ── Object / decoracion system ────────────────────────────────────────────
    imagenes_dir     = os.path.join(project_root, "Imagenes")
    interactables_dir = os.path.join(project_root, "Imagenes", "Interactuables")
    personajes_img_dir = os.path.join(project_root, "Imagenes", "Personajes")
    valid_obj_ext = {".png", ".jpg", ".jpeg"}
    available_objects = []
    # Objetos del directorio Interactuables (sin prefijo, como siempre)
    if os.path.isdir(interactables_dir):
        available_objects = sorted([f for f in os.listdir(interactables_dir)
                                    if os.path.splitext(f)[1].lower() in valid_obj_ext
                                    and os.path.isfile(os.path.join(interactables_dir, f))])
    # Sprites de personajes: guardados con prefijo "Personajes/<Carpeta>/<archivo>"
    # para distinguirlos de los interactuables en el JSON.
    if os.path.isdir(personajes_img_dir):
        for char_folder in sorted(os.listdir(personajes_img_dir)):
            char_path = os.path.join(personajes_img_dir, char_folder)
            if not os.path.isdir(char_path):
                continue
            for fn in sorted(os.listdir(char_path)):
                if os.path.splitext(fn)[1].lower() in valid_obj_ext:
                    # clave relativa a Imagenes/ → "Personajes/Profesor1/Profesor1_idle_down.png"
                    available_objects.append(
                        os.path.join("Personajes", char_folder, fn).replace("\\", "/"))
    current_object_idx = 0
    pending_placement_frames = 1   # frames que se asignarán al próximo objeto colocado
    object_cache = {}
    placement_sizes = {}
    decoracion = []
    deco_history = [copy.deepcopy(decoracion)]
    deco_history_index = 0
    selected_deco_idx = None
    moving_deco_idx = None
    deco_move_offset = (0, 0)
    DECO_SCALE_STEP = 1.18
    MIN_DECO = 4
    deco_crop_mode = False
    deco_crop_dragging = False
    deco_crop_start = None
    deco_crop_current = None

    def load_object_image(obj_name):
        """Carga imagen de objeto/decoración.
        Busca primero en Interactuables/, luego en Imagenes/<obj_name>
        (para sprites de personajes guardados como 'Personajes/Xxx/archivo.png')."""
        if obj_name in object_cache:
            return object_cache[obj_name]
        # Ruta 1: Interactuables/<nombre> (objetos clásicos)
        path = os.path.join(interactables_dir, obj_name)
        if not os.path.isfile(path):
            # Ruta 2: Imagenes/<nombre> (sprites de personajes con prefijo)
            path = os.path.join(imagenes_dir, obj_name.replace("/", os.sep))
        try:
            img = pygame.image.load(path).convert_alpha()
            object_cache[obj_name] = img
            return img
        except (OSError, pygame.error):
            object_cache[obj_name] = None
            return None

    def get_deco_world_rect(obj):
        return pygame.Rect(
            int(obj["x"] * world_rect.width),
            int(obj["y"] * world_rect.height),
            max(MIN_DECO, int(obj["w"] * world_rect.width)),
            max(MIN_DECO, int(obj["h"] * world_rect.height)),
        )

    def normalize_deco(x, y, w, h):
        return {"x": x / world_rect.width, "y": y / world_rect.height,
                "w": w / world_rect.width, "h": h / world_rect.height}

    def clamp_deco_pos(x, y, w, h):
        return (max(0, min(x, world_rect.width - w)),
                max(0, min(y, world_rect.height - h)))

    def detect_sprite_frames(obj_img):
        """Detecta cuántos frames tiene un spritesheet horizontal por ratio de aspecto."""
        iw, ih = obj_img.get_size()
        if ih == 0:
            return 1
        ratio   = iw / ih
        rounded = round(ratio)
        if rounded >= 2 and abs(ratio - rounded) < 0.15:
            return rounded
        return 1

    def get_initial_deco_size(obj_img):
        frames = detect_sprite_frames(obj_img)
        iw, ih = obj_img.get_size()
        fw = iw // frames          # ancho de un solo frame
        s  = min(96 * U / max(fw, ih), U)
        return max(MIN_DECO, int(fw * s)), max(MIN_DECO, int(ih * s))

    def get_placement_size(obj_name, obj_img):
        if obj_name not in placement_sizes:
            placement_sizes[obj_name] = get_initial_deco_size(obj_img)
        return placement_sizes[obj_name]

    def get_deco_crop_rect(obj, obj_img):
        crop = obj.get("crop")
        iw, ih = obj_img.get_size()
        if not isinstance(crop, dict):
            return pygame.Rect(0, 0, iw, ih)
        try:
            cx = float(crop.get("x", 0.0))
            cy = float(crop.get("y", 0.0))
            cw = float(crop.get("w", 1.0))
            ch = float(crop.get("h", 1.0))
        except (TypeError, ValueError):
            return pygame.Rect(0, 0, iw, ih)
        x = max(0, min(iw - 1, int(cx * iw)))
        y = max(0, min(ih - 1, int(cy * ih)))
        w = max(1, min(iw - x, int(cw * iw)))
        h = max(1, min(ih - y, int(ch * ih)))
        return pygame.Rect(x, y, w, h)

    def get_cropped_deco_image(obj, obj_img):
        crop_rect = get_deco_crop_rect(obj, obj_img)
        if crop_rect.size == obj_img.get_size() and crop_rect.topleft == (0, 0):
            return obj_img
        return obj_img.subsurface(crop_rect)

    def make_deco_crop_rect_from_points(start, end):
        return pygame.Rect(min(start[0], end[0]), min(start[1], end[1]),
                           abs(end[0] - start[0]), abs(end[1] - start[1]))

    def apply_crop_to_selected_deco(crop_world_rect):
        if selected_deco_idx is None or not (0 <= selected_deco_idx < len(decoracion)):
            return
        obj = decoracion[selected_deco_idx]
        obj_img = load_object_image(obj["name"])
        if obj_img is None:
            return
        obj_rect = get_deco_world_rect(obj)
        crop_rect = crop_world_rect.clip(obj_rect)
        if crop_rect.width < 2 or crop_rect.height < 2:
            return
        old_crop = get_deco_crop_rect(obj, obj_img)
        rel_x = (crop_rect.x - obj_rect.x) / max(1, obj_rect.width)
        rel_y = (crop_rect.y - obj_rect.y) / max(1, obj_rect.height)
        rel_w = crop_rect.width / max(1, obj_rect.width)
        rel_h = crop_rect.height / max(1, obj_rect.height)
        iw, ih = obj_img.get_size()
        new_x = max(0, min(old_crop.x + int(old_crop.width * rel_x), iw - 1))
        new_y = max(0, min(old_crop.y + int(old_crop.height * rel_y), ih - 1))
        new_w = max(1, min(int(old_crop.width * rel_w), iw - new_x))
        new_h = max(1, min(int(old_crop.height * rel_h), ih - new_y))
        obj["crop"] = {"x": new_x / iw, "y": new_y / ih, "w": new_w / iw, "h": new_h / ih}
        obj.update(normalize_deco(crop_rect.x, crop_rect.y, crop_rect.width, crop_rect.height))
        push_deco_history()

    def reset_selected_deco_crop():
        if selected_deco_idx is None or not (0 <= selected_deco_idx < len(decoracion)):
            return
        decoracion[selected_deco_idx].pop("crop", None)
        push_deco_history()

    def copy_all_deco():
        try:
            with open(deco_clipboard_path, "w", encoding="utf-8") as fh:
                json.dump(copy.deepcopy(decoracion), fh, indent=2)
            print(f"{len(decoracion)} objetos copiados.")
        except Exception as e:
            print(f"Error copiando objetos: {e}")

    def paste_all_deco():
        nonlocal selected_deco_idx
        if not os.path.exists(deco_clipboard_path):
            return
        try:
            with open(deco_clipboard_path, "r", encoding="utf-8") as fh:
                pasted = json.load(fh)
            if not isinstance(pasted, list):
                return
            start_idx = len(decoracion)
            for obj in pasted:
                if isinstance(obj, dict) and "name" in obj:
                    decoracion.append(copy.deepcopy(obj))
            if len(decoracion) > start_idx:
                selected_deco_idx = len(decoracion) - 1
                push_deco_history()
            print(f"{len(decoracion) - start_idx} objetos pegados.")
        except Exception as e:
            print(f"Error pegando objetos: {e}")

    def copy_selected_deco():
        if selected_deco_idx is None or not (0 <= selected_deco_idx < len(decoracion)):
            return
        try:
            with open(deco_selected_clipboard_path, "w", encoding="utf-8") as fh:
                json.dump(copy.deepcopy(decoracion[selected_deco_idx]), fh, indent=2)
            print(f"Objeto seleccionado copiado: {decoracion[selected_deco_idx]['name']}")
        except Exception as e:
            print(f"Error copiando objeto seleccionado: {e}")

    def paste_selected_deco():
        nonlocal selected_deco_idx
        if not os.path.exists(deco_selected_clipboard_path):
            return
        try:
            with open(deco_selected_clipboard_path, "r", encoding="utf-8") as fh:
                pasted = json.load(fh)
            if not isinstance(pasted, dict) or "name" not in pasted:
                return
            copied = copy.deepcopy(pasted)
            r = get_deco_world_rect(copied)
            nx = min(world_rect.width - r.width, r.x + 18)
            ny = min(world_rect.height - r.height, r.y + 18)
            copied.update(normalize_deco(nx, ny, r.width, r.height))
            decoracion.append(copied)
            selected_deco_idx = len(decoracion) - 1
            push_deco_history()
            print(f"Objeto seleccionado pegado: {copied['name']}")
        except Exception as e:
            print(f"Error pegando objeto seleccionado: {e}")

    def find_deco_at(world_pos):
        for idx in range(len(decoracion) - 1, -1, -1):
            if get_deco_world_rect(decoracion[idx]).collidepoint(world_pos):
                return idx
        return None

    def push_deco_history():
        nonlocal deco_history, deco_history_index
        deco_history = deco_history[:deco_history_index + 1]
        deco_history.append(copy.deepcopy(decoracion))
        deco_history_index += 1

    def scale_selected_deco(factor):
        if selected_deco_idx is None or not (0 <= selected_deco_idx < len(decoracion)):
            return
        obj = decoracion[selected_deco_idx]
        r = get_deco_world_rect(obj)
        nw = max(MIN_DECO, int(r.width * factor))
        nh = max(MIN_DECO, int(r.height * factor))
        nx, ny = clamp_deco_pos(r.centerx - nw // 2, r.centery - nh // 2, nw, nh)
        obj.update(normalize_deco(nx, ny, nw, nh))
        push_deco_history()

    def scale_placement_deco(factor):
        if not available_objects:
            return
        obj_name = available_objects[current_object_idx]
        obj_img = load_object_image(obj_name)
        if obj_img is None:
            return
        cw, ch = get_placement_size(obj_name, obj_img)
        placement_sizes[obj_name] = (
            max(MIN_DECO, int(cw * factor)),
            max(MIN_DECO, int(ch * factor)),
        )

    def scale_selected_deco_w(factor):
        """Scale only the width of the selected decoration."""
        if selected_deco_idx is None or not (0 <= selected_deco_idx < len(decoracion)):
            return
        obj = decoracion[selected_deco_idx]
        r = get_deco_world_rect(obj)
        nw = max(MIN_DECO, int(r.width * factor))
        nx, ny = clamp_deco_pos(r.x, r.y, nw, r.height)
        obj.update(normalize_deco(nx, ny, nw, r.height))
        push_deco_history()

    def scale_selected_deco_h(factor):
        """Scale only the height of the selected decoration."""
        if selected_deco_idx is None or not (0 <= selected_deco_idx < len(decoracion)):
            return
        obj = decoracion[selected_deco_idx]
        r = get_deco_world_rect(obj)
        nh = max(MIN_DECO, int(r.height * factor))
        nx, ny = clamp_deco_pos(r.x, r.y, r.width, nh)
        obj.update(normalize_deco(nx, ny, r.width, nh))
        push_deco_history()

    def scale_placement_deco_w(factor):
        """Scale only the width of the placement ghost."""
        if not available_objects:
            return
        obj_name = available_objects[current_object_idx]
        obj_img = load_object_image(obj_name)
        if obj_img is None:
            return
        cw, ch = get_placement_size(obj_name, obj_img)
        placement_sizes[obj_name] = (max(MIN_DECO, int(cw * factor)), ch)

    def scale_placement_deco_h(factor):
        """Scale only the height of the placement ghost."""
        if not available_objects:
            return
        obj_name = available_objects[current_object_idx]
        obj_img = load_object_image(obj_name)
        if obj_img is None:
            return
        cw, ch = get_placement_size(obj_name, obj_img)
        placement_sizes[obj_name] = (cw, max(MIN_DECO, int(ch * factor)))

    # ── File paths ────────────────────────────────────────────────────────────
    image_name = os.path.splitext(os.path.basename(image_path))[0]
    out_path = os.path.join(project_root, "Hitboxes", f"{image_name}_hitboxes.json")
    clipboard_path = os.path.join(project_root, "Hitboxes", "_clipboard.json")
    selected_clipboard_path = os.path.join(project_root, "Hitboxes", "_clipboard_selected.json")
    deco_clipboard_path = os.path.join(project_root, "Hitboxes", "_deco_clipboard.json")
    deco_selected_clipboard_path = os.path.join(project_root, "Hitboxes", "_deco_selected_clipboard.json")
    legacy_objects_path = os.path.join(project_root, "Objetos", f"{image_name}_objetos.json")

    # ── Auto-load ─────────────────────────────────────────────────────────────
    try:
        if os.path.exists(out_path):
            hitboxes, loaded_spawn, loaded_npcs, loaded_deco = load_hitboxes(out_path)
            _apply_loaded_spawn(loaded_spawn)
            if isinstance(loaded_npcs, dict):
                npc_positions = {k: v for k, v in loaded_npcs.items() if isinstance(v, dict)}
            if loaded_deco is not None:
                decoracion = [obj for obj in loaded_deco
                              if isinstance(obj, dict) and "name" in obj]
                if not decoracion and os.path.exists(legacy_objects_path):
                    with open(legacy_objects_path, "r", encoding="utf-8") as fh:
                        legacy = json.load(fh)
                    decoracion = [obj for obj in legacy.get("objects", [])
                                  if isinstance(obj, dict) and "name" in obj]
                    if decoracion:
                        print(f"Migrados {len(decoracion)} objetos desde {legacy_objects_path}")
            elif os.path.exists(legacy_objects_path):
                # Migrate from old Objetos/ JSON (one-time, saved on next Enter)
                with open(legacy_objects_path, "r", encoding="utf-8") as fh:
                    legacy = json.load(fh)
                decoracion = [obj for obj in legacy.get("objects", [])
                              if isinstance(obj, dict) and "name" in obj]
                print(f"Migrados {len(decoracion)} objetos desde {legacy_objects_path}")
            history = [copy.deepcopy(hitboxes)]
            history_index = 0
            deco_history = [copy.deepcopy(decoracion)]
            deco_history_index = 0
            print(f"Cargado desde: {out_path}")
    except Exception as e:
        print(f"Error cargando: {e}")
        hitboxes = []
        history = [copy.deepcopy(hitboxes)]
        history_index = 0

    reset_test_player_to_spawn()

    # ── History helpers ───────────────────────────────────────────────────────
    def push_history():
        nonlocal history, history_index
        history = history[:history_index + 1]
        history.append(copy.deepcopy(hitboxes))
        history_index += 1

    def copy_walls_to_clipboard():
        copied = [copy.deepcopy(h) for h in hitboxes if h.get("role") == "wall"]
        try:
            with open(clipboard_path, "w", encoding="utf-8") as fh:
                json.dump(copied, fh, indent=2)
            print(f"{len(copied)} hitboxes pared copiadas.")
        except Exception as e:
            print(f"Error copiando: {e}")

    def paste_walls_from_clipboard():
        if not os.path.exists(clipboard_path):
            return
        try:
            with open(clipboard_path, "r", encoding="utf-8") as fh:
                pasted = json.load(fh)
            if isinstance(pasted, list):
                hitboxes.extend(copy.deepcopy(pasted))
                push_history()
                print(f"{len(pasted)} hitboxes pegadas.")
        except Exception as e:
            print(f"Error pegando: {e}")

    def copy_selected_hitbox():
        if selected_hitbox_idx is None or not (0 <= selected_hitbox_idx < len(hitboxes)):
            return
        try:
            with open(selected_clipboard_path, "w", encoding="utf-8") as fh:
                json.dump(copy.deepcopy(hitboxes[selected_hitbox_idx]), fh, indent=2)
            print("Hitbox seleccionada copiada.")
        except Exception as e:
            print(f"Error: {e}")

    def paste_selected_hitbox():
        nonlocal selected_hitbox_idx
        if not os.path.exists(selected_clipboard_path):
            return
        try:
            with open(selected_clipboard_path, "r", encoding="utf-8") as fh:
                pasted = json.load(fh)
            if isinstance(pasted, dict) and "type" in pasted:
                hitboxes.append(copy.deepcopy(pasted))
                selected_hitbox_idx = len(hitboxes) - 1
                push_history()
                print("Hitbox seleccionada pegada.")
        except Exception as e:
            print(f"Error: {e}")

    def duplicate_selected_hitbox():
        nonlocal selected_hitbox_idx
        if selected_hitbox_idx is None or not (0 <= selected_hitbox_idx < len(hitboxes)):
            return
        dup = copy.deepcopy(hitboxes[selected_hitbox_idx])
        offset = 0.02
        if dup["type"] == "rect":
            dup["rx"] = min(1.0 - dup.get("rw", 0), dup.get("rx", 0) + offset)
            dup["ry"] = min(1.0 - dup.get("rh", 0), dup.get("ry", 0) + offset)
        elif dup["type"] == "circle":
            dup["cx"] = min(1.0, dup.get("cx", 0.5) + offset)
            dup["cy"] = min(1.0, dup.get("cy", 0.5) + offset)
        elif dup["type"] == "line":
            for k in ("x1", "x2", "y1", "y2"):
                dup[k] = min(1.0, dup.get(k, 0.5) + offset)
        hitboxes.append(dup)
        selected_hitbox_idx = len(hitboxes) - 1
        push_history()

    def select_all_of_role():
        nonlocal selected_set, selected_hitbox_idx
        selected_set = {i for i, h in enumerate(hitboxes) if h.get("role") == current_role}
        if selected_set:
            selected_hitbox_idx = min(selected_set)
            center_camera_on_rect(denormalize_rect(hitboxes[selected_hitbox_idx], world_rect))
        print(f"Seleccionadas {len(selected_set)} hitboxes de tipo '{current_role}'.")

    def _build_hitbox_payload(shape_data):
        payload = {"role": current_role, **shape_data}
        if current_role == "interactable":
            payload["action"] = current_interactable_action
            if current_interactable_action == "puerta":
                payload["target_image"] = available_backgrounds[current_target_bg_idx]
            elif current_interactable_action == "npc":
                payload["npc_character"] = npc_character_options[current_npc_character_idx]
                payload["npc_animation"] = current_npc_animation_options[current_npc_animation_idx]
        return payload

    def _interactable_label(action):
        return {"npc": "NPC"}.get(str(action).lower(), "Puerta")

    # ── Panel helpers ─────────────────────────────────────────────────────────
    def _panel_items():
        """Returns list of (label, color, index_type, real_idx) for the panel list."""
        items = []
        for i, h in enumerate(hitboxes):
            role = h.get("role", "wall")
            if role == "wall" and not show_walls:
                continue
            if role == "interactable" and not show_interactables:
                continue
            act = h.get("action", "")
            char = h.get("npc_character", "")
            shape = h["type"]
            if role == "wall":
                label = f"W{i+1} {shape[:3]}"
                color = (100, 160, 255)
            elif act == "npc":
                label = f"N{i+1} {char[:10]}"
                color = (255, 200, 80)
            else:
                label = f"P{i+1} puerta"
                color = (255, 200, 80)
            items.append((label, color, "hitbox", i))
        if show_objects:
            for j, obj in enumerate(decoracion):
                name = obj.get("name", "?")[:14]
                items.append((f"D{j+1} {name}", (120, 220, 120), "deco", j))
        return items

    def _panel_click(mouse_y):
        nonlocal selected_hitbox_idx, selected_deco_idx, panel_scroll, editor_mode
        items = _panel_items()
        list_top = panel_rect.y + 80   # after the toggle buttons
        row = (mouse_y - list_top + panel_scroll) // PANEL_ROW_H
        if 0 <= row < len(items):
            label, color, kind, real_idx = items[row]
            if kind == "hitbox":
                selected_hitbox_idx = real_idx
                selected_set.clear()
                selected_set.add(real_idx)
                editor_mode = "hitbox"
                center_camera_on_rect(denormalize_rect(hitboxes[real_idx], world_rect))
            else:
                selected_deco_idx = real_idx
                editor_mode = "object"
                center_camera_on_rect(get_deco_world_rect(decoracion[real_idx]))

    # ── Save ─────────────────────────────────────────────────────────────────
    def do_save():
        spawn_data = {
            "default": spawn_rules.get("default"),
            "by_origin": spawn_rules.get("by_origin", {}),
        }
        save_hitboxes(out_path, hitboxes, world_rect, image_path,
                      spawn_data=spawn_data, npc_positions=npc_positions,
                      decoracion=decoracion)
        print(f"Guardado: {out_path}")

    def do_load():
        nonlocal hitboxes, history, history_index, decoracion, deco_history, deco_history_index
        nonlocal selected_hitbox_idx, selected_deco_idx
        if not os.path.exists(out_path):
            return
        try:
            hitboxes, loaded_spawn, loaded_npcs, loaded_deco = load_hitboxes(out_path)
            _apply_loaded_spawn(loaded_spawn)
            if isinstance(loaded_npcs, dict):
                npc_positions.clear()
                npc_positions.update({k: v for k, v in loaded_npcs.items() if isinstance(v, dict)})
            if loaded_deco is not None:
                decoracion = [o for o in loaded_deco if isinstance(o, dict) and "name" in o]
            selected_hitbox_idx = None
            selected_deco_idx = None
            selected_set.clear()
            history = [copy.deepcopy(hitboxes)]
            history_index = 0
            deco_history = [copy.deepcopy(decoracion)]
            deco_history_index = 0
            print(f"Recargado desde: {out_path}")
        except Exception as e:
            print(f"Error recargando: {e}")

    # ── Main loop ─────────────────────────────────────────────────────────────
    running = True
    arrastre_camara = None     # (x, y del mouse, cámara) mientras se arrastra con el botón del medio
    while running:
        clock.tick(60)
        fps = clock.get_fps()
        mouse_pos_screen = pygame.mouse.get_pos()
        mouse_world = screen_to_world(mouse_pos_screen)
        norm_cursor = (
            f"{mouse_world[0] / world_rect.width:.3f}, {mouse_world[1] / world_rect.height:.3f}"
            if mouse_world else "---, ---"
        )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # ── Spawn modal ───────────────────────────────────────────────────
            if spawn_modal_active:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        spawn_modal_selected = (spawn_modal_selected - 1) % len(spawn_modal_options)
                    elif event.key == pygame.K_DOWN:
                        spawn_modal_selected = (spawn_modal_selected + 1) % len(spawn_modal_options)
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if pending_spawn_rect is None:
                            spawn_status_message = "Primero marca una posicion con Shift+P."
                            spawn_status_timer = 180
                            continue
                        selected = spawn_modal_options[spawn_modal_selected]
                        spawn_data = _serialize_spawn_rect(pending_spawn_rect)
                        if selected == "Cualquier fondo":
                            if spawn_rules.get("default") is not None:
                                spawn_status_message = "Ya existe spawn para 'Cualquier fondo'."
                                spawn_status_timer = 240
                                continue
                            spawn_rules["default"] = spawn_data
                            spawn_rect.topleft = pending_spawn_rect.topleft
                            clamp_spawn_rect()
                            reset_test_player_to_spawn()
                            spawn_status_message = "Spawn por defecto creado."
                        else:
                            if selected in spawn_rules["by_origin"]:
                                spawn_status_message = f"Ya existe spawn para '{selected}'."
                                spawn_status_timer = 240
                                continue
                            spawn_rules["by_origin"][selected] = spawn_data
                            spawn_rect.topleft = pending_spawn_rect.topleft
                            clamp_spawn_rect()
                            reset_test_player_to_spawn()
                            spawn_status_message = f"Spawn creado para '{selected}'."
                        spawn_status_timer = 180
                        pending_spawn_rect = None
                        spawn_modal_active = False
                    elif event.key == pygame.K_ESCAPE:
                        pending_spawn_rect = None
                        spawn_modal_active = False
                continue

            # ── NPC character selector modal ──────────────────────────────────
            if npc_char_modal:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        npc_char_modal = False
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        current_npc_character_idx = npc_modal_selected
                        current_npc_animation_options = _animations_for_character(
                            npc_character_options[current_npc_character_idx])
                        current_npc_animation_idx = 0
                        if npc_modal_source == "deco" and selected_deco_idx is not None:
                            decoracion[selected_deco_idx]["npc_owner"] = npc_character_options[npc_modal_selected]
                            push_deco_history()
                        npc_char_modal = False
                    elif event.key == pygame.K_RIGHT:
                        npc_modal_selected = (npc_modal_selected + 1) % len(npc_character_options)
                    elif event.key == pygame.K_LEFT:
                        npc_modal_selected = (npc_modal_selected - 1) % len(npc_character_options)
                    elif event.key == pygame.K_DOWN:
                        npc_modal_selected = min(len(npc_character_options) - 1,
                                                 npc_modal_selected + THUMB_COLS)
                    elif event.key == pygame.K_UP:
                        npc_modal_selected = max(0, npc_modal_selected - THUMB_COLS)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # hit detection on modal cells is done in rendering pass (done below)
                    pass
                continue

            # ── NPC animation selector modal ──────────────────────────────────
            if npc_anim_modal:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        npc_anim_modal = False
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        current_npc_animation_idx = npc_anim_modal_selected
                        if npc_modal_source == "deco" and selected_deco_idx is not None:
                            decoracion[selected_deco_idx]["npc_animation"] = current_npc_animation_options[npc_anim_modal_selected]
                            push_deco_history()
                        npc_anim_modal = False
                    elif event.key == pygame.K_RIGHT:
                        npc_anim_modal_selected = (npc_anim_modal_selected + 1) % len(current_npc_animation_options)
                    elif event.key == pygame.K_LEFT:
                        npc_anim_modal_selected = (npc_anim_modal_selected - 1) % len(current_npc_animation_options)
                    elif event.key == pygame.K_DOWN:
                        npc_anim_modal_selected = min(len(current_npc_animation_options) - 1,
                                                      npc_anim_modal_selected + THUMB_COLS)
                    elif event.key == pygame.K_UP:
                        npc_anim_modal_selected = max(0, npc_anim_modal_selected - THUMB_COLS)
                continue

            # ── Panel scroll ──────────────────────────────────────────────────
            if event.type == pygame.MOUSEWHEEL:
                if panel_rect.collidepoint(mouse_pos_screen):
                    panel_scroll = max(0, panel_scroll - event.y * PANEL_ROW_H)
                    continue
                # ── Zoom con la rueda, alrededor del mouse ────────────────────
                if viewport_rect.collidepoint(mouse_pos_screen) and event.y:
                    set_zoom(zoom_i + (1 if event.y > 0 else -1), mouse_pos_screen)
                    continue
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2 and viewport_rect.collidepoint(event.pos):
                arrastre_camara = (event.pos[0], event.pos[1], camera_x, camera_y)
                continue
            if event.type == pygame.MOUSEBUTTONUP and event.button == 2:
                arrastre_camara = None
                continue
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_0, pygame.K_KP0) and not test_mode:
                set_zoom(0)           # el mapa entero
                continue

            # ── Panel click ───────────────────────────────────────────────────
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                # Toggle buttons at top of panel
                if panel_rect.collidepoint(mx, my):
                    btn_y = panel_rect.y + 30
                    btn_h = 20
                    # W toggle
                    if pygame.Rect(panel_rect.x + 4, btn_y, 60, btn_h).collidepoint(mx, my):
                        show_walls = not show_walls
                        continue
                    # I toggle
                    if pygame.Rect(panel_rect.x + 70, btn_y, 60, btn_h).collidepoint(mx, my):
                        show_interactables = not show_interactables
                        continue
                    # O toggle
                    if pygame.Rect(panel_rect.x + 140, btn_y, 60, btn_h).collidepoint(mx, my):
                        show_objects = not show_objects
                        continue
                    # List area
                    if my > panel_rect.y + 80:
                        _panel_click(my)
                        continue

            # ── Test mode movement ────────────────────────────────────────────
            if test_mode and event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                test_mode = False
                continue

            # ── Mouse events (viewport only) ──────────────────────────────────
            if event.type == pygame.MOUSEBUTTONDOWN and not test_mode:
                world_pos = screen_to_world(event.pos)
                if event.button == 1 and world_pos is not None:

                    # ── OBJECT MODE ──────────────────────────────────────────
                    if editor_mode == "object":
                        # Crop mode: start drag on selected deco
                        if deco_crop_mode and selected_deco_idx is not None and 0 <= selected_deco_idx < len(decoracion):
                            sel_rect = get_deco_world_rect(decoracion[selected_deco_idx])
                            if sel_rect.collidepoint(world_pos):
                                deco_crop_dragging = True
                                deco_crop_start = world_pos
                                deco_crop_current = world_pos
                                continue
                        clicked_idx = find_deco_at(world_pos)
                        if clicked_idx is not None:
                            selected_deco_idx = clicked_idx
                            r = get_deco_world_rect(decoracion[clicked_idx])
                            moving_deco_idx = clicked_idx
                            deco_move_offset = (world_pos[0] - r.x, world_pos[1] - r.y)
                        else:
                            selected_deco_idx = None
                            if available_objects and not deco_crop_mode:
                                obj_name = available_objects[current_object_idx]
                                obj_img = load_object_image(obj_name)
                                if obj_img:
                                    ow, oh = get_placement_size(obj_name, obj_img)
                                    ox = snap_val(int(world_pos[0] - ow / 2), world_rect.width)
                                    oy = snap_val(int(world_pos[1] - oh / 2), world_rect.height)
                                    ox = max(0, min(ox, world_rect.width - ow))
                                    oy = max(0, min(oy, world_rect.height - oh))
                                    new_obj = {"name": obj_name,
                                               **normalize_deco(ox, oy, ow, oh)}
                                    if pending_placement_frames > 1:
                                        new_obj["frames"] = pending_placement_frames
                                    decoracion.append(new_obj)
                                    selected_deco_idx = len(decoracion) - 1
                                    push_deco_history()

                    # ── HITBOX MODE ──────────────────────────────────────────
                    else:
                        if move_mode:
                            for idx in range(len(hitboxes) - 1, -1, -1):
                                h = hitboxes[idx]
                                hit = False
                                if h["type"] == "rect":
                                    r = denormalize_rect(h, world_rect)
                                    if r.collidepoint(world_pos):
                                        move_offset = (world_pos[0] - r.x, world_pos[1] - r.y)
                                        hit = True
                                elif h["type"] == "circle":
                                    cx = world_rect.x + h["cx"] * world_rect.width
                                    cy = world_rect.y + h["cy"] * world_rect.height
                                    if math.hypot(world_pos[0] - cx, world_pos[1] - cy) <= h["r"] * world_rect.width:
                                        move_offset = (world_pos[0] - cx, world_pos[1] - cy)
                                        hit = True
                                elif h["type"] == "line":
                                    x1 = world_rect.x + h["x1"] * world_rect.width
                                    y1 = world_rect.y + h["y1"] * world_rect.height
                                    x2 = world_rect.x + h["x2"] * world_rect.width
                                    y2 = world_rect.y + h["y2"] * world_rect.height
                                    if point_to_line_distance(world_pos, (x1, y1), (x2, y2)) <= line_thickness_px(h, world_rect):
                                        move_offset = (world_pos[0] - x1, world_pos[1] - y1)
                                        hit = True
                                if hit:
                                    moving_hitbox = idx
                                    selected_hitbox_idx = idx
                                    selected_set = {idx}
                                    break
                        else:
                            dragging = True
                            sx = snap_val(int(world_pos[0]), world_rect.width)
                            sy = snap_val(int(world_pos[1]), world_rect.height)
                            start_pos = (sx, sy)
                            current_rect = pygame.Rect(sx, sy, 0, 0)

                elif event.button == 3 and world_pos is not None:
                    if editor_mode == "object":
                        idx = find_deco_at(world_pos)
                        if idx is not None:
                            decoracion.pop(idx)
                            if selected_deco_idx == idx:
                                selected_deco_idx = None
                            elif selected_deco_idx is not None and selected_deco_idx > idx:
                                selected_deco_idx -= 1
                            push_deco_history()
                    else:
                        if _delete_npc_at_world_pos(world_pos):
                            continue
                        if _delete_spawn_at_world_pos(world_pos):
                            continue
                        for idx in range(len(hitboxes) - 1, -1, -1):
                            h = hitboxes[idx]
                            hit = False
                            if h["type"] == "rect" and denormalize_rect(h, world_rect).collidepoint(world_pos):
                                hit = True
                            elif h["type"] == "circle":
                                cx = world_rect.x + h["cx"] * world_rect.width
                                cy = world_rect.y + h["cy"] * world_rect.height
                                hit = math.hypot(world_pos[0] - cx, world_pos[1] - cy) <= h["r"] * world_rect.width
                            elif h["type"] == "line":
                                x1 = world_rect.x + h["x1"] * world_rect.width
                                y1 = world_rect.y + h["y1"] * world_rect.height
                                x2 = world_rect.x + h["x2"] * world_rect.width
                                y2 = world_rect.y + h["y2"] * world_rect.height
                                hit = point_to_line_distance(world_pos, (x1, y1), (x2, y2)) <= line_thickness_px(h, world_rect) / 2 + 4 * U
                            if hit:
                                hitboxes.pop(idx)
                                if selected_hitbox_idx == idx:
                                    selected_hitbox_idx = None
                                elif selected_hitbox_idx is not None and selected_hitbox_idx > idx:
                                    selected_hitbox_idx -= 1
                                selected_set.discard(idx)
                                push_history()
                                break

            elif event.type == pygame.MOUSEMOTION:
                if moving_deco_idx is not None:
                    world_pos = screen_to_world(event.pos)
                    if world_pos is not None:
                        obj = decoracion[moving_deco_idx]
                        r = get_deco_world_rect(obj)
                        nx = snap_val(int(world_pos[0] - deco_move_offset[0]), world_rect.width)
                        ny = snap_val(int(world_pos[1] - deco_move_offset[1]), world_rect.height)
                        nx, ny = clamp_deco_pos(nx, ny, r.width, r.height)
                        obj.update(normalize_deco(nx, ny, r.width, r.height))

                elif moving_hitbox is not None:
                    world_pos = screen_to_world(event.pos)
                    if world_pos is not None:
                        h = hitboxes[moving_hitbox]
                        if h["type"] == "rect":
                            r = denormalize_rect(h, world_rect)
                            r.x = snap_val(int(world_pos[0] - move_offset[0]), world_rect.width)
                            r.y = snap_val(int(world_pos[1] - move_offset[1]), world_rect.height)
                            r.clamp_ip(world_rect)
                            hitboxes[moving_hitbox].update(normalize_rect(r, world_rect))
                        elif h["type"] == "circle":
                            cx = world_pos[0] - move_offset[0]
                            cy = world_pos[1] - move_offset[1]
                            radius_px = h["r"] * world_rect.width
                            cx = max(world_rect.left + radius_px, min(cx, world_rect.right - radius_px))
                            cy = max(world_rect.top + radius_px, min(cy, world_rect.bottom - radius_px))
                            h["cx"] = (cx - world_rect.x) / world_rect.width
                            h["cy"] = (cy - world_rect.y) / world_rect.height
                        elif h["type"] == "line":
                            x1 = world_rect.x + h["x1"] * world_rect.width
                            y1 = world_rect.y + h["y1"] * world_rect.height
                            x2 = world_rect.x + h["x2"] * world_rect.width
                            y2 = world_rect.y + h["y2"] * world_rect.height
                            dx = world_pos[0] - move_offset[0] - x1
                            dy = world_pos[1] - move_offset[1] - y1
                            x1 += dx; y1 += dy; x2 += dx; y2 += dy
                            min_x, max_x = min(x1, x2), max(x1, x2)
                            min_y, max_y = min(y1, y2), max(y1, y2)
                            if min_x < world_rect.left:
                                x1 += world_rect.left - min_x; x2 += world_rect.left - min_x
                            if max_x > world_rect.right:
                                x1 -= max_x - world_rect.right; x2 -= max_x - world_rect.right
                            if min_y < world_rect.top:
                                y1 += world_rect.top - min_y; y2 += world_rect.top - min_y
                            if max_y > world_rect.bottom:
                                y1 -= max_y - world_rect.bottom; y2 -= max_y - world_rect.bottom
                            h["x1"] = (x1 - world_rect.x) / world_rect.width
                            h["y1"] = (y1 - world_rect.y) / world_rect.height
                            h["x2"] = (x2 - world_rect.x) / world_rect.width
                            h["y2"] = (y2 - world_rect.y) / world_rect.height

                elif deco_crop_dragging:
                    world_pos = screen_to_world(event.pos)
                    if world_pos is not None:
                        deco_crop_current = world_pos

                elif dragging and editor_mode == "hitbox":
                    if current_shape == "rect":
                        world_pos = screen_to_world(event.pos)
                        if world_pos is not None:
                            x1, y1 = start_pos
                            x2 = snap_val(int(world_pos[0]), world_rect.width)
                            y2 = snap_val(int(world_pos[1]), world_rect.height)
                            current_rect = pygame.Rect(min(x1, x2), min(y1, y2),
                                                        abs(x2 - x1), abs(y2 - y1))

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    if deco_crop_dragging:
                        if deco_crop_start is not None and deco_crop_current is not None:
                            apply_crop_to_selected_deco(
                                make_deco_crop_rect_from_points(deco_crop_start, deco_crop_current))
                        deco_crop_dragging = False
                        deco_crop_start = None
                        deco_crop_current = None
                    if moving_deco_idx is not None:
                        moving_deco_idx = None
                        push_deco_history()
                    if moving_hitbox is not None:
                        moving_hitbox = None
                        push_history()
                    if dragging and editor_mode == "hitbox":
                        world_pos = screen_to_world(event.pos)
                        dragging = False
                        if world_pos is not None and current_rect is not None:
                            if current_shape == "rect":
                                fixed = clamp_rect_to_image(current_rect, world_rect)
                                if fixed.width > 6 and fixed.height > 6:
                                    hitboxes.append(_build_hitbox_payload(
                                        {"type": "rect", **normalize_rect(fixed, world_rect)}))
                                    selected_hitbox_idx = len(hitboxes) - 1
                                    selected_set = {selected_hitbox_idx}
                                    push_history()
                            elif current_shape == "circle":
                                dx = world_pos[0] - start_pos[0]
                                dy = world_pos[1] - start_pos[1]
                                r = math.hypot(dx, dy)
                                if r > 3:
                                    hitboxes.append(_build_hitbox_payload({
                                        "type": "circle",
                                        "cx": (start_pos[0] - world_rect.x) / world_rect.width,
                                        "cy": (start_pos[1] - world_rect.y) / world_rect.height,
                                        "r": r / world_rect.width,
                                    }))
                                    selected_hitbox_idx = len(hitboxes) - 1
                                    selected_set = {selected_hitbox_idx}
                                    push_history()
                            elif current_shape == "line":
                                dx = abs(world_pos[0] - start_pos[0])
                                dy = abs(world_pos[1] - start_pos[1])
                                if dx > 3 or dy > 3:
                                    hitboxes.append(_build_hitbox_payload({
                                        "type": "line",
                                        "x1": (start_pos[0] - world_rect.x) / world_rect.width,
                                        "y1": (start_pos[1] - world_rect.y) / world_rect.height,
                                        "x2": (world_pos[0] - world_rect.x) / world_rect.width,
                                        "y2": (world_pos[1] - world_rect.y) / world_rect.height,
                                        "thickness": current_line_thickness_px / world_rect.width,
                                    }))
                                    selected_hitbox_idx = len(hitboxes) - 1
                                    selected_set = {selected_hitbox_idx}
                                    push_history()
                        current_rect = None

            # ── Keyboard ──────────────────────────────────────────────────────
            elif event.type == pygame.KEYDOWN:
                mods = pygame.key.get_mods()
                ctrl = bool(mods & pygame.KMOD_CTRL)
                shift = bool(mods & pygame.KMOD_SHIFT)
                alt = bool(mods & pygame.KMOD_ALT)

                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_z and ctrl:
                    if editor_mode == "object":
                        if deco_history_index > 0:
                            deco_history_index -= 1
                            decoracion[:] = copy.deepcopy(deco_history[deco_history_index])
                    else:
                        if history_index > 0:
                            history_index -= 1
                            hitboxes[:] = copy.deepcopy(history[history_index])
                            if selected_hitbox_idx is not None and selected_hitbox_idx >= len(hitboxes):
                                selected_hitbox_idx = None

                elif event.key == pygame.K_y and ctrl:
                    if editor_mode == "object":
                        if deco_history_index < len(deco_history) - 1:
                            deco_history_index += 1
                            decoracion[:] = copy.deepcopy(deco_history[deco_history_index])
                    else:
                        if history_index < len(history) - 1:
                            history_index += 1
                            hitboxes[:] = copy.deepcopy(history[history_index])
                            if selected_hitbox_idx is not None and selected_hitbox_idx >= len(hitboxes):
                                selected_hitbox_idx = None

                elif event.key == pygame.K_d and ctrl:
                    if editor_mode == "object" and selected_deco_idx is not None:
                        dup = copy.deepcopy(decoracion[selected_deco_idx])
                        r = get_deco_world_rect(dup)
                        nx = min(world_rect.width - r.width, r.x + 16)
                        ny = min(world_rect.height - r.height, r.y + 16)
                        dup.update(normalize_deco(nx, ny, r.width, r.height))
                        decoracion.append(dup)
                        selected_deco_idx = len(decoracion) - 1
                        push_deco_history()
                    else:
                        duplicate_selected_hitbox()

                elif event.key == pygame.K_a and ctrl:
                    select_all_of_role()

                elif event.key == pygame.K_r and editor_mode == "object":
                    if shift:
                        reset_selected_deco_crop()
                        print("Recorte reiniciado")
                    else:
                        deco_crop_mode = not deco_crop_mode
                        deco_crop_dragging = False
                        deco_crop_start = None
                        deco_crop_current = None
                        print("MODO RECORTE OBJ ACTIVADO" if deco_crop_mode else "MODO RECORTE OBJ DESACTIVADO")

                elif event.key == pygame.K_c and ctrl and shift:
                    if editor_mode == "object":
                        copy_selected_deco()
                    else:
                        copy_selected_hitbox()
                elif event.key == pygame.K_c and ctrl:
                    if editor_mode == "object":
                        copy_all_deco()
                    else:
                        copy_walls_to_clipboard()
                elif event.key == pygame.K_v and ctrl and shift:
                    if editor_mode == "object":
                        paste_selected_deco()
                    else:
                        paste_selected_hitbox()
                elif event.key == pygame.K_v and ctrl:
                    if editor_mode == "object":
                        paste_all_deco()
                    else:
                        paste_walls_from_clipboard()
                elif event.key == pygame.K_l and ctrl:
                    do_load()

                elif event.key == pygame.K_RETURN:
                    do_save()

                elif event.key == pygame.K_c and not ctrl:
                    hitboxes.clear()
                    selected_hitbox_idx = None
                    selected_set.clear()
                    push_history()

                elif event.key == pygame.K_l and not ctrl:
                    show_labels = not show_labels

                elif event.key == pygame.K_g:
                    grid_snap = not grid_snap
                    print("Grid snap:", "ON" if grid_snap else "OFF")

                elif event.key == pygame.K_o:
                    editor_mode = "object" if editor_mode == "hitbox" else "hitbox"
                    print("Modo:", editor_mode.upper())

                elif event.key == pygame.K_f:
                    shapes = ["rect", "circle", "line"]
                    current_shape = shapes[(shapes.index(current_shape) + 1) % 3]

                elif event.key == pygame.K_i:
                    current_role = "interactable" if current_role == "wall" else "wall"

                elif event.key == pygame.K_j:
                    if editor_mode == "object":
                        current_object_idx = (current_object_idx + 1) % max(1, len(available_objects))
                        pending_placement_frames = 1
                    else:
                        current_target_bg_idx = (current_target_bg_idx + 1) % len(available_backgrounds)

                elif event.key == pygame.K_h:
                    if editor_mode == "object":
                        current_object_idx = (current_object_idx - 1) % max(1, len(available_objects))
                        pending_placement_frames = 1
                    else:
                        current_target_bg_idx = (current_target_bg_idx - 1) % len(available_backgrounds)

                elif event.key == pygame.K_k:
                    idx = interactable_actions.index(current_interactable_action)
                    current_interactable_action = interactable_actions[(idx + 1) % len(interactable_actions)]

                elif event.key == pygame.K_n:
                    if editor_mode == "object" and selected_deco_idx is not None:
                        obj = decoracion[selected_deco_idx]
                        if "pupitre" in obj.get("name", "").lower():
                            npc_modal_source = "deco"
                            owner = obj.get("npc_owner", "")
                            npc_modal_selected = (npc_character_options.index(owner)
                                                  if owner in npc_character_options
                                                  else current_npc_character_idx)
                        else:
                            npc_modal_source = "hitbox"
                            npc_modal_selected = current_npc_character_idx
                    else:
                        npc_modal_source = "hitbox"
                        npc_modal_selected = current_npc_character_idx
                    npc_char_modal = True

                elif event.key == pygame.K_b:
                    if editor_mode == "object" and selected_deco_idx is not None:
                        obj = decoracion[selected_deco_idx]
                        if "pupitre" in obj.get("name", "").lower():
                            npc_modal_source = "deco"
                            owner = obj.get("npc_owner", "")
                            if owner and owner != npc_character_options[current_npc_character_idx]:
                                if owner in npc_character_options:
                                    current_npc_character_idx = npc_character_options.index(owner)
                                    current_npc_animation_options = _animations_for_character(owner)
                                    current_npc_animation_idx = 0
                            saved_anim = obj.get("npc_animation", "")
                            npc_anim_modal_selected = (current_npc_animation_options.index(saved_anim)
                                                       if saved_anim in current_npc_animation_options
                                                       else current_npc_animation_idx)
                        else:
                            npc_modal_source = "hitbox"
                            npc_anim_modal_selected = current_npc_animation_idx
                    else:
                        npc_modal_source = "hitbox"
                        npc_anim_modal_selected = current_npc_animation_idx
                    npc_anim_modal = True

                elif event.key == pygame.K_m:
                    move_mode = not move_mode
                    print("Modo mover:", "ON" if move_mode else "OFF")

                elif event.key == pygame.K_t:
                    test_mode = not test_mode
                    if test_mode:
                        reset_test_player_to_spawn()
                        center_camera_on_rect(test_player)

                elif event.key == pygame.K_p:
                    if shift:
                        set_spawn_to_mouse(mouse_pos_screen)
                        spawn_modal_selected = 0
                        for sidx, opt in enumerate(spawn_modal_options):
                            if opt != "Cualquier fondo" and opt not in spawn_rules.get("by_origin", {}):
                                spawn_modal_selected = sidx
                                break
                        spawn_modal_active = True
                    else:
                        reset_test_player_to_spawn()
                        center_camera_on_rect(test_player)

                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    if editor_mode == "object":
                        if ctrl:
                            # Ctrl++ → solo anchura
                            if selected_deco_idx is not None:
                                scale_selected_deco_w(DECO_SCALE_STEP)
                            else:
                                scale_placement_deco_w(DECO_SCALE_STEP)
                        elif alt:
                            # Alt++ → solo altura
                            if selected_deco_idx is not None:
                                scale_selected_deco_h(DECO_SCALE_STEP)
                            else:
                                scale_placement_deco_h(DECO_SCALE_STEP)
                        else:
                            if selected_deco_idx is not None:
                                scale_selected_deco(DECO_SCALE_STEP)
                            else:
                                scale_placement_deco(DECO_SCALE_STEP)
                    else:
                        current_line_thickness_px = min(64, current_line_thickness_px + 1)

                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    if editor_mode == "object":
                        if ctrl:
                            # Ctrl+- → solo anchura
                            if selected_deco_idx is not None:
                                scale_selected_deco_w(1 / DECO_SCALE_STEP)
                            else:
                                scale_placement_deco_w(1 / DECO_SCALE_STEP)
                        elif alt:
                            # Alt+- → solo altura
                            if selected_deco_idx is not None:
                                scale_selected_deco_h(1 / DECO_SCALE_STEP)
                            else:
                                scale_placement_deco_h(1 / DECO_SCALE_STEP)
                        else:
                            if selected_deco_idx is not None:
                                scale_selected_deco(1 / DECO_SCALE_STEP)
                            else:
                                scale_placement_deco(1 / DECO_SCALE_STEP)
                    else:
                        current_line_thickness_px = max(1, current_line_thickness_px - 1)

                # ── Frames del spritesheet: [ baja, ] sube ────────────────────
                elif event.key == pygame.K_LEFTBRACKET and editor_mode == "object":
                    if selected_deco_idx is not None:
                        obj = decoracion[selected_deco_idx]
                        f = max(1, int(obj.get("frames", 1)) - 1)
                        if f == 1:
                            obj.pop("frames", None)
                        else:
                            obj["frames"] = f
                        push_deco_history()
                    else:
                        pending_placement_frames = max(1, pending_placement_frames - 1)

                elif event.key == pygame.K_RIGHTBRACKET and editor_mode == "object":
                    if selected_deco_idx is not None:
                        obj = decoracion[selected_deco_idx]
                        obj["frames"] = int(obj.get("frames", 1)) + 1
                        push_deco_history()
                    else:
                        pending_placement_frames += 1

                elif event.key == pygame.K_1 and shift:
                    _set_npc_at_mouse("sara", mouse_pos_screen)
                elif event.key == pygame.K_2 and shift:
                    _set_npc_at_mouse("diego", mouse_pos_screen)
                elif event.key == pygame.K_1:
                    selected_npc_name = "sara"
                    spawn_status_message = "NPC seleccionado: Sara."
                    spawn_status_timer = 120
                elif event.key == pygame.K_2:
                    selected_npc_name = "diego"
                    spawn_status_message = "NPC seleccionado: Diego."
                    spawn_status_timer = 120
                elif event.key in (pygame.K_LEFTBRACKET,):
                    _change_npc_site_size(selected_npc_name, -8)
                elif event.key in (pygame.K_RIGHTBRACKET,):
                    _change_npc_site_size(selected_npc_name, 8)

        # ── Test mode physics ─────────────────────────────────────────────────
        if test_mode:
            keys = pygame.key.get_pressed()
            mx = ((1 if keys[pygame.K_d] else 0) - (1 if keys[pygame.K_a] else 0)) * test_speed
            my = ((1 if keys[pygame.K_s] else 0) - (1 if keys[pygame.K_w] else 0)) * test_speed
            prev_x = test_player.x
            test_player.x += mx
            test_player.clamp_ip(world_rect)
            for h in hitboxes:
                if h.get("role") != "wall":
                    continue
                if collides_rect_with_hitbox(test_player, h, world_rect):
                    test_player.x = prev_x
                    break
            prev_y = test_player.y
            test_player.y += my
            test_player.clamp_ip(world_rect)
            for h in hitboxes:
                if h.get("role") != "wall":
                    continue
                if collides_rect_with_hitbox(test_player, h, world_rect):
                    test_player.y = prev_y
                    break
            center_camera_on_rect(test_player)
        else:
            keys = pygame.key.get_pressed()
            cam_speed = 10 / zoom          # 10 px de pantalla por cuadro, con cualquier zoom
            camera_x += ((1 if keys[pygame.K_d] else 0) - (1 if keys[pygame.K_a] else 0)) * cam_speed
            camera_y += ((1 if keys[pygame.K_s] else 0) - (1 if keys[pygame.K_w] else 0)) * cam_speed
            if arrastre_camara is not None:
                mx, my = pygame.mouse.get_pos()
                camera_x = arrastre_camara[2] - (mx - arrastre_camara[0]) / zoom
                camera_y = arrastre_camara[3] - (my - arrastre_camara[1]) / zoom
            clamp_camera()

        # ── RENDER ────────────────────────────────────────────────────────────
        screen.fill((28, 28, 34))

        # Clip rendering to viewport
        draw_map()
        prev_clip_vista = screen.get_clip()
        screen.set_clip(viewport_rect)

        # Grid overlay
        if grid_snap:
            step_x = max(1, int(GRID_SIZE * world_rect.width))
            step_y = max(1, int(GRID_SIZE * world_rect.height))
            grid_col = (55, 55, 70)
            start_wx = int(camera_x // step_x) * step_x
            wx = start_wx
            while wx <= camera_x + viewport_rect.width / zoom:
                sx = round(world_to_screen((wx, 0))[0])
                pygame.draw.line(screen, grid_col, (sx, viewport_rect.y), (sx, viewport_rect.bottom), 1)
                wx += step_x
            start_wy = int(camera_y // step_y) * step_y
            wy = start_wy
            while wy <= camera_y + viewport_rect.height / zoom:
                sy = round(world_to_screen((0, wy))[1])
                pygame.draw.line(screen, grid_col, (viewport_rect.x, sy), (viewport_rect.right, sy), 1)
                wy += step_y

        # Decoracion objects
        if show_objects:
            for j, obj in enumerate(decoracion):
                obj_img = load_object_image(obj["name"])
                if obj_img:
                    r = get_deco_world_rect(obj)
                    sr = rect_to_screen(r)
                    sx, sy = sr.topleft
                    frames = int(obj.get("frames", 1))
                    if frames > 1:
                        # Spritesheet animado: w ya es 1 frame → subsurface + escalar a r.width×r.height
                        frame_idx  = (pygame.time.get_ticks() // 120) % frames
                        iw = obj_img.get_width()
                        ih = obj_img.get_height()
                        fw = max(1, iw // frames)
                        frame_surf = obj_img.subsurface(pygame.Rect(frame_idx * fw, 0, fw, ih))
                        scaled = pygame.transform.smoothscale(frame_surf, sr.size)
                    else:
                        source_img = get_cropped_deco_image(obj, obj_img)
                        scaled = pygame.transform.smoothscale(source_img, sr.size)
                    screen.blit(scaled, (sx, sy))
                    border_col = (255, 235, 80) if selected_deco_idx == j else (80, 220, 100)
                    pygame.draw.rect(screen, border_col, sr, 2 if selected_deco_idx != j else 3)
                    if show_labels:
                        crop_tag  = " [C]" if "crop" in obj else ""
                        anim_tag  = f" [{frames}f]" if frames > 1 else ""
                        owner_tag = f" [{obj['npc_owner']}]" if obj.get("npc_owner") else ""
                        lbl = tiny.render(f"D{j+1} {obj['name'][:12]}{crop_tag}{anim_tag}{owner_tag}", True, (130, 240, 130))
                        screen.blit(lbl, (sr.x + 2, sr.y + 2))

        # Crop drag preview
        if deco_crop_dragging and deco_crop_start and deco_crop_current:
            preview = make_deco_crop_rect_from_points(deco_crop_start, deco_crop_current)
            if selected_deco_idx is not None and 0 <= selected_deco_idx < len(decoracion):
                preview = preview.clip(get_deco_world_rect(decoracion[selected_deco_idx]))
            screen_preview = rect_to_screen(preview)
            if screen_preview.width > 0 and screen_preview.height > 0:
                dim = pygame.Surface((screen_preview.width, screen_preview.height), pygame.SRCALPHA)
                dim.fill((255, 235, 120, 50))
                screen.blit(dim, screen_preview.topleft)
                pygame.draw.rect(screen, (255, 235, 120), screen_preview, 2)

        # Object mode placement preview
        if editor_mode == "object" and not moving_deco_idx and available_objects:
            obj_name = available_objects[current_object_idx]
            obj_img = load_object_image(obj_name)
            if obj_img and mouse_world and viewport_rect.collidepoint(mouse_pos_screen):
                ow, oh = get_placement_size(obj_name, obj_img)
                px = int(mouse_world[0] - ow / 2)
                py = int(mouse_world[1] - oh / 2)
                sx, sy = world_to_screen((px, py))
                cur_frames = pending_placement_frames
                if cur_frames > 1:
                    fidx   = (pygame.time.get_ticks() // 120) % cur_frames
                    iw     = obj_img.get_width()
                    ih     = obj_img.get_height()
                    fwp    = max(1, iw // cur_frames)
                    source = obj_img.subsurface(pygame.Rect(fidx * fwp, 0, fwp, ih))
                else:
                    source = obj_img
                prev = pygame.transform.smoothscale(source, rect_to_screen(pygame.Rect(px, py, ow, oh)).size).copy()
                prev.set_alpha(100)
                screen.blit(prev, (sx, sy))

        # Hitboxes
        anim_frame_idx = (pygame.time.get_ticks() // 180)
        for i, h in enumerate(hitboxes):
            role = h.get("role", "wall")
            if role == "wall" and not show_walls:
                continue
            if role == "interactable" and not show_interactables:
                continue
            is_selected = (selected_hitbox_idx == i) or (i in selected_set)
            color = (90, 160, 255) if role == "wall" else (255, 210, 80)
            label_color = (160, 210, 255) if role == "wall" else (255, 235, 150)

            if h["type"] == "rect":
                r = denormalize_rect(h, world_rect)
                sr = rect_to_screen(r)
                pygame.draw.rect(screen, color, sr, 2)
                if is_selected:
                    pygame.draw.rect(screen, (255, 255, 255), sr, 4)
                if show_labels:
                    screen.blit(tiny.render(str(i + 1), True, label_color), (sr.x + 4, sr.y + 2))
                if role == "interactable":
                    action = h.get("action", "puerta")
                    act_lbl = _interactable_label(action)
                    if show_labels:
                        lbl = small.render(act_lbl, True, (255, 245, 180))
                        screen.blit(lbl, lbl.get_rect(center=sr.center))
                    if action == "npc":
                        frames = _load_npc_preview_frames(h.get("npc_character", "Sara"),
                                                          h.get("npc_animation", ""))
                        if frames:
                            fidx = anim_frame_idx % len(frames)
                            frame = frames[fidx]
                            fw, fh = frame.get_size()
                            s = min(min(max(12, sr.width), 160) / fw,
                                    min(max(12, sr.height), 160) / fh, 1.0)
                            scaled = pygame.transform.smoothscale(frame,
                                (max(12, int(fw * s)), max(12, int(fh * s))))
                            screen.blit(scaled, scaled.get_rect(center=sr.center))
                        if show_labels:
                            info = f"{h.get('npc_character','NPC')} | {h.get('npc_animation','')}"
                            screen.blit(tiny.render(info, True, (255, 205, 150)),
                                        (sr.x + 4, sr.bottom + 2))
                    elif action == "puerta" and show_labels:
                        dest = h.get("target_image", "")
                        if dest:
                            screen.blit(tiny.render(f"→ {dest[:20]}", True, (200, 200, 255)),
                                        (sr.x + 4, sr.bottom + 2))

            elif h["type"] == "circle":
                cx = world_rect.x + h["cx"] * world_rect.width
                cy = world_rect.y + h["cy"] * world_rect.height
                rr = h["r"] * world_rect.width * zoom
                sx, sy = world_to_screen((cx, cy))
                pygame.draw.circle(screen, color, (int(sx), int(sy)), int(rr), 2)
                if is_selected:
                    pygame.draw.circle(screen, (255, 255, 255), (int(sx), int(sy)), int(rr), 4)
                if show_labels:
                    screen.blit(tiny.render(str(i + 1), True, label_color), (sx - 10, sy - 10))
                if role == "interactable":
                    action = h.get("action", "puerta")
                    if show_labels:
                        lbl = small.render(_interactable_label(action), True, (255, 245, 180))
                        screen.blit(lbl, lbl.get_rect(center=(int(sx), int(sy))))
                    if action == "npc":
                        frames = _load_npc_preview_frames(h.get("npc_character", "Sara"),
                                                          h.get("npc_animation", ""))
                        if frames:
                            frame = frames[anim_frame_idx % len(frames)]
                            diam = min(max(12, int(rr * 2)), 160)
                            fw, fh = frame.get_size()
                            s = min(diam / fw, diam / fh, 1.0)
                            scaled = pygame.transform.smoothscale(frame,
                                (max(12, int(fw * s)), max(12, int(fh * s))))
                            screen.blit(scaled, scaled.get_rect(center=(int(sx), int(sy))))

            elif h["type"] == "line":
                x1 = world_rect.x + h["x1"] * world_rect.width
                y1 = world_rect.y + h["y1"] * world_rect.height
                x2 = world_rect.x + h["x2"] * world_rect.width
                y2 = world_rect.y + h["y2"] * world_rect.height
                sx1, sy1 = world_to_screen((x1, y1))
                sx2, sy2 = world_to_screen((x2, y2))
                thickness = max(1, round(line_thickness_px(h, world_rect) * zoom))
                pygame.draw.line(screen, color, (sx1, sy1), (sx2, sy2), thickness)
                if is_selected:
                    pygame.draw.line(screen, (255, 255, 255), (sx1, sy1), (sx2, sy2),
                                     max(thickness + 4, 5))
                if show_labels:
                    mx_pt = ((sx1 + sx2) / 2, (sy1 + sy2) / 2)
                    screen.blit(tiny.render(str(i + 1), True, label_color),
                                (mx_pt[0] - 10, mx_pt[1] - 10))

        # Dragging preview
        if current_rect is not None:
            pr = rect_to_screen(clamp_rect_to_image(current_rect, world_rect))
            pygame.draw.rect(screen, (120, 200, 255), pr, 2)
        elif dragging and current_shape == "circle" and mouse_world:
            dx = mouse_world[0] - start_pos[0]
            dy = mouse_world[1] - start_pos[1]
            rr = math.hypot(dx, dy) * zoom
            ss = world_to_screen(start_pos)
            pygame.draw.circle(screen, (120, 200, 255), (int(ss[0]), int(ss[1])), int(rr), 2)
        elif dragging and current_shape == "line" and mouse_world:
            ss = world_to_screen(start_pos)
            sm = world_to_screen(mouse_world)
            pygame.draw.line(screen, (120, 200, 255), ss, sm, max(1, round(current_line_thickness_px * zoom)))

        # Test player
        if test_mode:
            tv = rect_to_screen(test_player)
            pygame.draw.rect(screen, (255, 190, 90), tv, 2)

        # Spawn markers
        if isinstance(spawn_rules.get("default"), dict):
            d = spawn_rules["default"]
            dr = pygame.Rect(int(d["rx"] * world_rect.width), int(d["ry"] * world_rect.height),
                             spawn_rect.width, spawn_rect.height)
            dr = rect_to_screen(dr)
            pygame.draw.rect(screen, (255, 90, 90), dr, 2)
            if show_labels:
                screen.blit(small.render("Spawn:default", True, (255, 120, 120)),
                            (dr.x, dr.y - 16))
        for origin_name, sdata in spawn_rules.get("by_origin", {}).items():
            if not isinstance(sdata, dict):
                continue
            sr = pygame.Rect(int(sdata["rx"] * world_rect.width), int(sdata["ry"] * world_rect.height),
                             spawn_rect.width, spawn_rect.height)
            sr = rect_to_screen(sr)
            pygame.draw.rect(screen, (255, 180, 70), sr, 2)
            if show_labels:
                screen.blit(small.render(f"Spawn:{origin_name[:18]}", True, (255, 210, 120)),
                            (sr.x, sr.y - 16))

        # NPC legacy positions
        for npc_name, data in npc_positions.items():
            if not isinstance(data, dict):
                continue
            nx, ny = _denormalize_world_point(data)
            site_w = max(24, int(float(data.get("rw", npc_default_site_w / world_rect.width)) * world_rect.width))
            site_h = max(24, int(float(data.get("rh", npc_default_site_h / world_rect.height)) * world_rect.height))
            sx, sy = world_to_screen((nx, ny))
            npc_sr = pygame.Rect(0, 0, max(4, round(site_w * zoom)), max(4, round(site_h * zoom)))
            npc_sr.center = (int(sx), int(sy))
            pygame.draw.rect(screen, (255, 120, 200), npc_sr, 1)
            pygame.draw.circle(screen, (255, 80, 170), (int(sx), int(sy)), 10, 2)
            pygame.draw.line(screen, (255, 80, 170), (int(sx) - 7, int(sy)), (int(sx) + 7, int(sy)), 2)
            pygame.draw.line(screen, (255, 80, 170), (int(sx), int(sy) - 7), (int(sx), int(sy) + 7), 2)
            if show_labels:
                screen.blit(small.render(f"NPC:{npc_name}", True, (255, 180, 220)),
                            (int(sx) + 12, int(sy) - 12))

        if pending_spawn_rect is not None:
            pv = rect_to_screen(pending_spawn_rect)
            pygame.draw.rect(screen, (255, 255, 0), pv, 2)
            screen.blit(small.render("Spawn pendiente", True, (255, 255, 140)), (pv.x, pv.y - 16))

        screen.set_clip(prev_clip_vista)
        pygame.draw.rect(screen, (235, 235, 235), viewport_rect, 2)
        # Zoom actual (píxeles de pantalla por píxel del dibujo).
        k_zoom = zoom * ESCALA_MAPA
        txt_zoom = small.render(f"Zoom {k_zoom:.2f}x  (rueda / 0 / clic del medio arrastra)", True, (220, 220, 235))
        caja_zoom = txt_zoom.get_rect(topright=(viewport_rect.right - 8, viewport_rect.y + 8))
        pygame.draw.rect(screen, (20, 20, 28), caja_zoom.inflate(10, 6))
        screen.blit(txt_zoom, caja_zoom)

        # ── Right panel ───────────────────────────────────────────────────────
        pygame.draw.rect(screen, (35, 35, 48), panel_rect)
        pygame.draw.line(screen, (80, 80, 100), (panel_rect.x, panel_rect.y),
                         (panel_rect.x, panel_rect.bottom), 1)

        px = panel_rect.x + 4
        py = panel_rect.y + 6
        panel_title = small.render("Elementos", True, (200, 200, 220))
        screen.blit(panel_title, (px, py))
        py += 22

        # Toggle buttons
        def draw_toggle(rect, label, active):
            col = (60, 120, 60) if active else (80, 40, 40)
            pygame.draw.rect(screen, col, rect, border_radius=4)
            pygame.draw.rect(screen, (120, 120, 140), rect, 1, border_radius=4)
            lbl = tiny.render(label, True, (230, 230, 230))
            screen.blit(lbl, lbl.get_rect(center=rect.center))

        draw_toggle(pygame.Rect(px, py, 58, 18), f"W({sum(1 for h in hitboxes if h.get('role')=='wall')})",
                    show_walls)
        draw_toggle(pygame.Rect(px + 62, py, 58, 18),
                    f"I({sum(1 for h in hitboxes if h.get('role')=='interactable')})", show_interactables)
        draw_toggle(pygame.Rect(px + 124, py, 58, 18), f"O({len(decoracion)})", show_objects)
        py += 26

        pygame.draw.line(screen, (60, 60, 80), (panel_rect.x, py), (panel_rect.right, py), 1)
        py += 4

        list_top = py
        list_h = panel_rect.bottom - list_top
        panel_clip = pygame.Rect(panel_rect.x, list_top, panel_rect.width, list_h)

        items = _panel_items()
        total_list_h = len(items) * PANEL_ROW_H
        max_scroll = max(0, total_list_h - list_h + 8)
        panel_scroll = min(panel_scroll, max_scroll)

        screen.set_clip(panel_clip)
        for row_i, (label, color, kind, real_idx) in enumerate(items):
            ry = list_top + row_i * PANEL_ROW_H - panel_scroll
            if ry + PANEL_ROW_H < list_top or ry > panel_rect.bottom:
                continue
            is_panel_sel = (kind == "hitbox" and real_idx == selected_hitbox_idx) or \
                           (kind == "deco" and real_idx == selected_deco_idx)
            if is_panel_sel:
                pygame.draw.rect(screen, (55, 60, 80),
                                 pygame.Rect(panel_rect.x, ry, panel_rect.width, PANEL_ROW_H))
            pygame.draw.rect(screen, color, pygame.Rect(px, ry + 4, 8, 14), border_radius=2)
            lbl = tiny.render(label, True, (220, 220, 230))
            screen.blit(lbl, (px + 12, ry + 4))
        screen.set_clip(None)

        # Scrollbar
        if total_list_h > list_h:
            sb_h = max(20, int(list_h * list_h / total_list_h))
            sb_y = list_top + int(panel_scroll / max_scroll * (list_h - sb_h)) if max_scroll else list_top
            pygame.draw.rect(screen, (80, 80, 110),
                             pygame.Rect(panel_rect.right - 6, sb_y, 4, sb_h), border_radius=2)

        # ── Status bar ────────────────────────────────────────────────────────
        pygame.draw.rect(screen, (22, 22, 32), status_rect_layout)
        pygame.draw.line(screen, (60, 60, 80), status_rect_layout.topleft,
                         (status_rect_layout.right, status_rect_layout.y), 1)
        npc_char = npc_character_options[current_npc_character_idx] if npc_character_options else "?"
        npc_anim = (current_npc_animation_options[current_npc_animation_idx]
                    if current_npc_animation_options else "?")
        mode_str = editor_mode.upper()
        tool_str = (f"{current_shape}/{current_role}/{current_interactable_action}"
                    if editor_mode == "hitbox" else
                    (available_objects[current_object_idx] if available_objects else "sin objetos"))
        status_parts = [
            f"Fondo: {os.path.basename(image_path)}",
            f"Modo: {mode_str}{'  MOVER' if move_mode else ''}{'  TEST' if test_mode else ''}",
            f"Tool: {tool_str}",
            f"NPC: {npc_char}/{npc_anim[:18]}",
            f"Cursor: ({norm_cursor})",
            f"FPS: {fps:.0f}",
            f"HBs: {len(hitboxes)} + {len(decoracion)} obj",
            f"Grid: {'ON' if grid_snap else 'off'}  Labels: {'ON' if show_labels else 'off'}",
        ]
        # ── Frames indicator (modo objeto) ────────────────────────────────────
        if editor_mode == "object":
            if selected_deco_idx is not None and 0 <= selected_deco_idx < len(decoracion):
                _fi = int(decoracion[selected_deco_idx].get("frames", 1))
                _fi_label = f"[ Frames: {_fi} ]   [  baja  /  ]  sube"
                _fi_color = (255, 220, 80) if _fi > 1 else (170, 170, 200)
            else:
                _fi = pending_placement_frames
                _fi_label = f"[ Frames: {_fi} ]   [  baja  /  ]  sube  (próximo objeto)"
                _fi_color = (130, 220, 255) if _fi > 1 else (140, 160, 180)
            _fi_surf = small.render(_fi_label, True, _fi_color)
            _fi_bg   = pygame.Surface((_fi_surf.get_width() + 16, _fi_surf.get_height() + 8))
            _fi_bg.fill((18, 18, 28))
            _fi_bg.set_alpha(210)
            _fi_ox = viewport_rect.x + 10
            _fi_oy = viewport_rect.y + 10
            screen.blit(_fi_bg,   (_fi_ox, _fi_oy))
            screen.blit(_fi_surf, (_fi_ox + 8, _fi_oy + 4))

        if current_role == "interactable" and current_interactable_action == "puerta" and available_backgrounds:
            dest = available_backgrounds[current_target_bg_idx]
            overlay = font.render(f"DESTINO PUERTA: {dest}", True, (255, 255, 0))
            bg_surf = pygame.Surface((overlay.get_width() + 16, overlay.get_height() + 8))
            bg_surf.fill((20, 20, 20))
            bg_surf.set_alpha(200)
            ox = viewport_rect.x + 10
            oy = viewport_rect.y + 10
            screen.blit(bg_surf, (ox, oy))
            screen.blit(overlay, (ox + 8, oy + 4))
            
        sx_pos = 8
        sy_pos = status_rect_layout.y + (STATUS_H - small.get_height()) // 2
        for part in status_parts:
            s = tiny.render(part, True, (180, 190, 210))
            screen.blit(s, (sx_pos, sy_pos))
            sx_pos += s.get_width() + 18
            if sx_pos > win_w - PANEL_W - 10:
                break

        # ── Bottom instruction area ───────────────────────────────────────────
        if spawn_status_timer > 0 and spawn_status_message:
            spawn_status_timer -= 1
            msg_color = (255, 180, 120) if "Ya existe" in spawn_status_message else (180, 255, 180)
            msg = small.render(spawn_status_message, True, msg_color)
            screen.blit(msg, msg.get_rect(midtop=(viewport_rect.centerx, viewport_rect.bottom + 4)))

        ui_y = viewport_rect.bottom + (26 if spawn_status_timer > 0 else 8)
        max_txt_w = win_w - panel_rect.width - padding * 2 - 8

        lines = [
            ("HITBOX: arrastra=crear | WASD=camara | F=forma | I=wall/inter | K=accion | M=mover | T=test | P/Shift+P=spawn | click-der=borrar | C=limpiar | ENTER=guardar | Ctrl+L=cargar | ESC=salir", (235, 235, 235)),
            ("O=modo objeto | J/H=obj/fondo | N=selector NPC | B=selector anim | G=grid | L=etiquetas | +/-=escala | Ctrl++/-=solo ancho | Alt++/-=solo alto | [/]=frames- / frames+ | Ctrl+D=dup | Ctrl+A=sel-todo | Ctrl+C/V=copiar/pegar todos | Ctrl+Shift+C/V=sel individual | R=recortar obj | Shift+R=quitar recorte", (210, 210, 160)),
        ]
        for line_txt, line_col in lines:
            ui_y = draw_wrapped_text(screen, line_txt, tiny, line_col,
                                     padding, ui_y, max_txt_w)

        # ── Spawn modal ───────────────────────────────────────────────────────
        if spawn_modal_active:
            modal_w = min(760, win_w - 120)
            modal_h = min(520, win_h - 120)
            modal = pygame.Rect((win_w - modal_w) // 2, (win_h - modal_h) // 2, modal_w, modal_h)
            dim = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 140))
            screen.blit(dim, (0, 0))
            pygame.draw.rect(screen, (245, 245, 245), modal, border_radius=10)
            pygame.draw.rect(screen, (20, 20, 20), modal, 3, border_radius=10)
            screen.blit(font.render("Spawn si el jugador viene de:", True, (20, 20, 20)),
                        (modal.x + 20, modal.y + 20))
            screen.blit(small.render("UP/DOWN=elegir  ENTER=confirmar  ESC=cancelar",
                                     True, (70, 70, 70)), (modal.x + 20, modal.y + 54))
            list_y = modal.y + 96
            max_rows = max(1, (modal.height - 130) // 26)
            start = max(0, spawn_modal_selected - max_rows + 1)
            end = min(len(spawn_modal_options), start + max_rows)
            for idx in range(start, end):
                txt = spawn_modal_options[idx]
                row = pygame.Rect(modal.x + 20, list_y + (idx - start) * 26, modal.width - 40, 24)
                if idx == spawn_modal_selected:
                    pygame.draw.rect(screen, (210, 230, 255), row, border_radius=4)
                label_txt = txt
                if txt != "Cualquier fondo" and txt in spawn_rules.get("by_origin", {}):
                    label_txt = f"{txt} [YA TIENE SPAWN]"
                screen.blit(small.render(label_txt, True, (20, 20, 20)), (row.x + 8, row.y + 2))

        # ── NPC character modal ───────────────────────────────────────────────
        if npc_char_modal and npc_character_options:
            cols = THUMB_COLS
            cell = THUMB + THUMB_GAP
            modal_w = cols * cell + THUMB_GAP * 2 + 20
            rows_count = math.ceil(len(npc_character_options) / cols)
            modal_h = min(win_h - 80, rows_count * cell + 80)
            modal = pygame.Rect((win_w - modal_w) // 2, (win_h - modal_h) // 2, modal_w, modal_h)
            dim = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 160))
            screen.blit(dim, (0, 0))
            pygame.draw.rect(screen, (40, 40, 55), modal, border_radius=10)
            pygame.draw.rect(screen, (120, 120, 160), modal, 2, border_radius=10)
            screen.blit(font.render("Elegir personaje NPC  (Flechas + Enter / ESC)",
                                    True, (220, 220, 240)), (modal.x + 10, modal.y + 10))
            mx0 = modal.x + THUMB_GAP
            my0 = modal.y + 42
            for ci, char_name in enumerate(npc_character_options):
                col_i = ci % cols
                row_i = ci // cols
                cx = mx0 + col_i * cell
                cy = my0 + row_i * cell
                cell_rect = pygame.Rect(cx, cy, THUMB + 4, THUMB + 18)
                if ci == npc_modal_selected:
                    pygame.draw.rect(screen, (80, 140, 220), cell_rect, border_radius=6)
                thumb = _load_thumbnail(char_name)
                if thumb:
                    tw, th = thumb.get_size()
                    screen.blit(thumb, (cx + (THUMB - tw) // 2 + 2, cy + 2))
                screen.blit(tiny.render(char_name[:12], True, (220, 220, 240)),
                            (cx + 2, cy + THUMB + 4))
                # Mouse click detection
                if pygame.mouse.get_pressed()[0] and cell_rect.collidepoint(pygame.mouse.get_pos()):
                    npc_modal_selected = ci
                    current_npc_character_idx = ci
                    current_npc_animation_options = _animations_for_character(npc_character_options[ci])
                    current_npc_animation_idx = 0
                    if npc_modal_source == "deco" and selected_deco_idx is not None:
                        decoracion[selected_deco_idx]["npc_owner"] = npc_character_options[ci]
                        push_deco_history()
                    npc_char_modal = False

        # ── NPC animation modal ───────────────────────────────────────────────
        if npc_anim_modal and current_npc_animation_options:
            char_name = npc_character_options[current_npc_character_idx]
            cols = THUMB_COLS
            cell = THUMB + THUMB_GAP
            modal_w = cols * cell + THUMB_GAP * 2 + 20
            rows_count = math.ceil(len(current_npc_animation_options) / cols)
            modal_h = min(win_h - 80, rows_count * cell + 80)
            modal = pygame.Rect((win_w - modal_w) // 2, (win_h - modal_h) // 2, modal_w, modal_h)
            dim = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 160))
            screen.blit(dim, (0, 0))
            pygame.draw.rect(screen, (40, 40, 55), modal, border_radius=10)
            pygame.draw.rect(screen, (120, 120, 160), modal, 2, border_radius=10)
            screen.blit(font.render(f"Animacion de {char_name}  (Flechas + Enter / ESC)",
                                    True, (220, 220, 240)), (modal.x + 10, modal.y + 10))
            mx0 = modal.x + THUMB_GAP
            my0 = modal.y + 42
            for ai, anim_file in enumerate(current_npc_animation_options):
                col_i = ai % cols
                row_i = ai // cols
                cx = mx0 + col_i * cell
                cy = my0 + row_i * cell
                cell_rect = pygame.Rect(cx, cy, THUMB + 4, THUMB + 18)
                if ai == npc_anim_modal_selected:
                    pygame.draw.rect(screen, (80, 140, 220), cell_rect, border_radius=6)
                thumb = _load_thumbnail(char_name, anim_file)
                if thumb:
                    tw, th = thumb.get_size()
                    screen.blit(thumb, (cx + (THUMB - tw) // 2 + 2, cy + 2))
                screen.blit(tiny.render(anim_file[:12], True, (220, 220, 240)),
                            (cx + 2, cy + THUMB + 4))
                if pygame.mouse.get_pressed()[0] and cell_rect.collidepoint(pygame.mouse.get_pos()):
                    npc_anim_modal_selected = ai
                    current_npc_animation_idx = ai
                    if npc_modal_source == "deco" and selected_deco_idx is not None:
                        decoracion[selected_deco_idx]["npc_animation"] = current_npc_animation_options[ai]
                        push_deco_history()
                    npc_anim_modal = False

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
