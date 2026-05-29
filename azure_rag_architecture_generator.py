from PIL import Image, ImageDraw, ImageFont
import math, os

W, H = 920, 620
FRAMES = 48
FPS_DELAY = 60  # ms per frame → ~16fps

BG = (10, 15, 30)
GRID = (74, 144, 217, 20)

# Color palettes
BLUE_DARK  = (13, 34, 64)
BLUE_MID   = (46, 122, 212)
BLUE_TEXT  = (168, 212, 255)
ORANGE_DARK= (61, 31, 6)
ORANGE_MID = (212, 120, 14)
ORANGE_TEXT= (255, 179, 102)
GREEN_DARK = (26, 74, 36)
GREEN_MID  = (45, 158, 68)
GREEN_TEXT = (125, 232, 154)
TEAL_MID   = (26, 138, 138)
PANEL_BG   = (10, 21, 32)
CONTAINER_BG=(13, 29, 53)
CONTAINER_BORDER=(34, 85, 170)
LABEL_BLUE = (122, 184, 245)
FLOW_ORANGE= (212, 120, 14)
FLOW_GREEN = (45, 158, 68)
FLOW_BLUE  = (74, 144, 217)
FLOW_LBLUE = (26, 122, 212)
WHITE      = (255, 255, 255)
MUTED      = (100, 136, 170)

def lerp(a, b, t): return a + (b - a) * t
def ease(t): return t * t * (3 - 2 * t)

def blend(c1, c2, t):
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))

def draw_3d_box(draw, x, y, w, h, fill, border, label, sublabel=None):
    depth = 8
    # right side
    pts = [(x+w, y), (x+w+depth, y-depth//2), (x+w+depth, y+h-depth//2), (x+w, y+h)]
    darker = tuple(max(0, c - 40) for c in fill)
    draw.polygon(pts, fill=darker, outline=border)
    # top face
    top_pts = [(x, y), (x+w, y), (x+w+depth, y-depth//2), (x+depth, y-depth//2)]
    lighter = tuple(min(255, c + 30) for c in fill)
    draw.polygon(top_pts, fill=lighter, outline=border)
    # front face
    draw.rectangle([x, y, x+w, y+h], fill=fill, outline=border)
    # label
    fx = x + w//2
    fy = y + (h//2 - 8 if sublabel else h//2)
    draw.text((fx, fy), label, fill=BLUE_TEXT if fill==BLUE_DARK else
              (ORANGE_TEXT if fill==ORANGE_DARK else GREEN_TEXT),
              anchor="mm", font=FONT_SM)
    if sublabel:
        draw.text((fx, y + h//2 + 9), sublabel, fill=MUTED, anchor="mm", font=FONT_XS)

def draw_container(draw, x, y, w, h, label):
    draw.rectangle([x, y, x+w, y+h], fill=CONTAINER_BG, outline=CONTAINER_BORDER)
    draw.rectangle([x, y, x+w, y+24], fill=(26, 58, 106), outline=CONTAINER_BORDER)
    draw.text((x+w//2, y+12), label, fill=LABEL_BLUE, anchor="mm", font=FONT_XS)

# def draw_grid(draw):
#     for gx in range(100, 920, 130):
#         draw.line([(gx, 0), (gx, H)], fill=GRID, width=1)
#     for gy in range(100, 620, 100):
#         draw.line([(0, gy), (W, gy)], fill=GRID, width=1)

def particle_pos(path_pts, t):
    """Interpolate position along a polyline at t∈[0,1]"""
    segs = []
    total = 0
    for i in range(len(path_pts)-1):
        dx = path_pts[i+1][0]-path_pts[i][0]
        dy = path_pts[i+1][1]-path_pts[i][1]
        d = math.sqrt(dx*dx+dy*dy)
        segs.append(d)
        total += d
    acc = 0
    target = t * total
    for i, d in enumerate(segs):
        if acc + d >= target:
            local_t = (target - acc) / d if d > 0 else 0
            x = lerp(path_pts[i][0], path_pts[i+1][0], local_t)
            y = lerp(path_pts[i][1], path_pts[i+1][1], local_t)
            return (x, y)
        acc += d
    return path_pts[-1]

def draw_flow_line(draw, pts, color, t_offset, num_particles=2):
    # build segment table
    segs, total = [], 0
    for i in range(len(pts)-1):
        dx,dy = pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1]
        d = math.sqrt(dx*dx+dy*dy)
        segs.append((pts[i], pts[i+1], d))
        total += d

    def pos_at(dist):
        acc = 0
        for p0,p1,d in segs:
            if acc+d >= dist or d == 0:
                lt = (dist-acc)/d if d else 0
                return (lerp(p0[0],p1[0],lt), lerp(p0[1],p1[1],lt))
            acc += d
        return pts[-1]

    # continuous dash across whole path
    dash, gap = 5, 3
    d = 0; drawing = True
    while d < total:
        end = min(d + (dash if drawing else gap), total)
        if drawing:
            x1,y1 = pos_at(d); x2,y2 = pos_at(end)
            draw.line([(x1,y1),(x2,y2)], fill=color+(150,), width=1)
        d = end; drawing = not drawing

    # animated particles
    for p in range(num_particles):
        t = (t_offset + p / num_particles) % 1.0
        pos = particle_pos(pts, t)
        r = 4
        draw.ellipse([pos[0]-r, pos[1]-r, pos[0]+r, pos[1]+r], fill=color+(230,))
        draw.ellipse([pos[0]-r-2, pos[1]-r-2, pos[0]+r+2, pos[1]+r+2], fill=color+(60,))

def draw_arrow(draw, pts, color):
    """Draw arrowhead at end of path"""
    if len(pts) < 2: return
    x2, y2 = pts[-1]
    x1, y1 = pts[-2]
    angle = math.atan2(y2-y1, x2-x1)
    size = 8
    ax = x2 - size * math.cos(angle - 0.4)
    ay = y2 - size * math.sin(angle - 0.4)
    bx = x2 - size * math.cos(angle + 0.4)
    by = y2 - size * math.sin(angle + 0.4)
    draw.polygon([(x2,y2),(ax,ay),(bx,by)], fill=color)

def draw_label(draw, x, y, text, color=None):
    draw.text((x, y), text, fill=color or MUTED, anchor="mm", font=FONT_XS)

def float_offset(frame, phase=0, amp=4):
    return amp * math.sin(2 * math.pi * (frame / FRAMES + phase))

# ---- Font setup ----
try:
    FONT_SM = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
    FONT_XS = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    FONT_LG = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    FONT_TI = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
except:
    FONT_SM = ImageFont.load_default()
    FONT_XS = FONT_SM
    FONT_LG = FONT_SM
    FONT_TI = FONT_SM

frames = []

for frame in range(FRAMES):
    t = frame / FRAMES  # 0..1 global time
    img = Image.new("RGBA", (W, H), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    # draw_grid(draw)

    # ── Node positions (x, y, w, h) ───────────────────────────────────
    UC  = (370, 12,  160, 34)   # User Client  (top-centre)
    ABS = (700, 50,  160, 42)   # Azure Blob Storage
    ADI = (30,  200, 170, 46)   # AI Doc Intelligence
    AAS = (370, 200, 180, 46)   # Azure App Service
    LLC = (370, 330, 180, 50)   # Logic / LangChain
    GPT = (30,  440, 178, 48)   # Azure OpenAI GPT-4
    EMB = (700, 200, 155, 44)   # OpenAI Embeddings
    AIS = (700, 420, 148, 44)   # Azure AI Search

    def cx(n): return n[0] + n[2]//2
    def cy(n): return n[1] + n[3]//2
    def top(n):  return (cx(n), n[1])
    def bot(n):  return (cx(n), n[1]+n[3])
    def left(n): return (n[0],  cy(n))
    def right(n):return (n[0]+n[2], cy(n))

    # --- Containers ---
    draw_container(draw, 18,  160, 200, 340, "Azure AI Services")
    draw_container(draw, 350, 160, 220, 230, "Interface & Logic")
    draw_container(draw, 678,  13, 230, 455, "Data Foundation")

    # --- 3D Nodes ---
    draw_3d_box(draw, *UC[:4],  BLUE_DARK,   BLUE_MID,   "User Client")
    draw_3d_box(draw, *ABS[:4], ORANGE_DARK, ORANGE_MID, "Azure Blob Storage", "PDF / Docs")
    draw_3d_box(draw, *ADI[:4], ORANGE_DARK, ORANGE_MID, "GPT-Vision", "Extract & Layout")
    draw_3d_box(draw, *AAS[:4], BLUE_DARK,   BLUE_MID,   "Azure App Service",  "Route & Format")
    draw_3d_box(draw, *LLC[:4], BLUE_DARK,   BLUE_MID,   "Logic Layer / Power Automate",  "Orchestrate")
    draw_3d_box(draw, *GPT[:4], GREEN_DARK,  GREEN_MID,  "Azure OpenAI GPT-4", "Grounded Response")
    draw_3d_box(draw, *EMB[:4], GREEN_DARK,  GREEN_MID,  "Azure OpenAI Embeddings",  "Vectorize")
    draw_3d_box(draw, *AIS[:4], BLUE_DARK,   FLOW_LBLUE, "Azure AI Search",    "Semantic Search")

    # ── Flows: all H/V segments only, 90-degree turns ─────────────────
    # Routing corridors
    BUS_L  = 340   # vertical bus between left-col and centre-col
    BUS_R  = 660   # vertical bus between centre-col and right-col
    BUS_LL = 12    # far-left return loop
    BUS_RR = 870   # far-right return loop

    flows = [
        # 1. Blob Storage → AI Doc Intelligence
        ( [(780, 92), (780, 150), (BUS_L, 150), (BUS_L, 200), (115, 200)],
          FLOW_ORANGE, t, 1, "1. Store PDF/Docs", (0, -10) ),

        # 2. AI Doc Intelligence → Logic/LangChain
        #    right from ADI → BUS_L → down to LLC cy → into LLC left
        ( [(200, 223), (BUS_L, 223), (BUS_L, 355), (370, 355)],
          FLOW_ORANGE, (t+0.08)%1, 1, "2. Extract Text & Layout", (0, -10) ),

        # 3. Logic/LangChain → OpenAI Embeddings
        #    right from LLC → BUS_R → up to EMB cy → into EMB left
        ( [(550, 348), (BUS_R, 348), (BUS_R, 222), (700, 222)],
          FLOW_GREEN, (t+0.16)%1, 1, "3. Convert Text to Vectors", (0, -10) ),

        # 4. OpenAI Embeddings → Azure AI Search
        #    straight down from EMB bot → AIS top
        ( [(777, 244), (777, 420)],
          FLOW_GREEN, (t+0.24)%1, 1, "4. Index Vector Data", (20, 0) ),

        # 5. User Client → Azure App Service  (left lane x=400)
        ( [(400, 46), (400, 200)],
          FLOW_BLUE, (t+0.32)%1, 1, "5. Submit NL Query", (-62, 0) ),

        # 6. Azure App Service → Logic/LangChain  (left lane x=400)
        ( [(400, 246), (400, 330)],
          FLOW_BLUE, (t+0.40)%1, 1, "6. Route Request", (-55, 0) ),

        # 7. Logic/LangChain → Azure AI Search
        #    right from LLC → BUS_R → down to AIS cy → into AIS left
        ( [(550, 362), (BUS_R, 362), (BUS_R, 442), (700, 442)],
          FLOW_BLUE, (t+0.48)%1, 1, "7. Semantic Search", (0, -10) ),

        # 8. Azure AI Search → Logic/LangChain  (far-right loop BUS_RR)
        ( [(848, 442), (BUS_RR, 442), (BUS_RR, 362), (550, 362)],
          FLOW_LBLUE, (t+0.56)%1, 1, "8. Return Data Chunks", (0, 10) ),

        # 9. Logic/LangChain → Azure OpenAI GPT-4
        #    left from LLC → BUS_L → down to GPT cy → into GPT right
        ( [(370, 348), (BUS_L, 348), (BUS_L, 464), (208, 464)],
          FLOW_GREEN, (t+0.64)%1, 1, "9. Send Context+Prompt", (0, -10) ),

        # 10. Azure OpenAI GPT-4 → Logic/LangChain  (far-left loop BUS_LL)
        ( [(30, 464), (BUS_LL, 464), (BUS_LL, 355), (370, 355)],
          FLOW_GREEN, (t+0.72)%1, 1, "10. Grounded Response", (0, 10) ),

        # 11. Logic/LangChain → Azure App Service  (right lane x=520)
        ( [(520, 330), (520, 246)],
          FLOW_LBLUE, (t+0.80)%1, 1, "11. Format Final Answer", (68, 0) ),

        # 12. Azure App Service → User Client  (right lane x=520, into UC bottom edge)
        ( [(520, 200), (520, 46)],
          FLOW_BLUE, (t+0.88)%1, 1, "12. Display Result", (55, 0) ),
    ]

    for pts, color, toff, np, label, (ox, oy) in flows:
        draw_flow_line(draw, pts, color, toff, np)
        draw_arrow(draw, pts, color)
        mid = particle_pos(pts, 0.5)
        lx, ly = mid[0] + ox, mid[1] + oy
        bbox = draw.textbbox((lx, ly), label, anchor="mm", font=FONT_XS)
        pad = 2
        draw.rectangle([bbox[0]-pad, bbox[1]-pad, bbox[2]+pad, bbox[3]+pad], fill=(10,15,30,210))
        draw.text((lx, ly), label, fill=color+(220,), anchor="mm", font=FONT_XS)

    # # --- Title ---
    # draw.text((W//2, 600), "AZURE RAG ARCHITECTURE", fill=FLOW_BLUE+(220,), anchor="mm", font=FONT_TI)

    # --- Legend box (bottom-left, clear of all nodes) ---
    draw.rectangle([18, 555, 310, 610], fill=PANEL_BG, outline=CONTAINER_BORDER)
    draw.text((164, 565), "Legend", fill=LABEL_BLUE, anchor="mm", font=FONT_XS)
    legend_items = [
        (580, FLOW_ORANGE, "Ingestion"),
        (580, FLOW_GREEN,  "Generation"),
        (595, FLOW_BLUE,   "Query/Response"),
        (595, FLOW_LBLUE,  "Return flow"),
    ]
    cols = [(25, 580, FLOW_ORANGE, "Ingestion pipeline"),
            (25, 595, FLOW_GREEN,  "Generation pipeline"),
            (165, 580, FLOW_BLUE,  "Query / response"),
            (165, 595, FLOW_LBLUE, "Return flow")]
    for lx2, ly2, lc2, lt2 in cols:
        draw.line([(lx2, ly2),(lx2+28, ly2)], fill=lc2, width=2)
        draw.text((lx2+32, ly2), lt2, fill=lc2, anchor="lm", font=FONT_XS)

    # Convert to RGB palette for GIF
    rgb = img.convert("RGB")
    frames.append(rgb.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG))

# Save GIF
out_path = "azure_rag_architecture.gif"
frames[0].save(
    out_path,
    save_all=True,
    append_images=frames[1:],
    optimize=True,
    loop=0,
    duration=FRAMES_DELAY if False else FPS_DELAY,
)
print(f"Saved: {out_path} ({os.path.getsize(out_path)//1024} KB)")
