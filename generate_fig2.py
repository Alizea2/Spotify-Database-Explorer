"""
Spotify DB — Figure 2: Modified Relational Compatibility Diagram
Two transformations shown side-by-side (before ER → after relational):
  (A) M:N Track ↔ Artist   →  track_artist junction table
  (B) AudioFeature weak entity  →  audio_features with shared PK
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Ellipse
import numpy as np

fig, ax = plt.subplots(figsize=(24, 17))
ax.set_xlim(0, 24)
ax.set_ylim(0, 17)
ax.axis('off')
BG = '#F9FAFB'
ax.set_facecolor(BG)
fig.patch.set_facecolor(BG)

# ── colour palette ────────────────────────────────────────────────────────────
ENT_EC, ENT_FC = '#1D4ED8', '#DBEAFE'
REL_EC, REL_FC = '#6D28D9', '#EDE9FE'
ATR_EC, ATR_FC = '#047857', '#D1FAE5'
PK_FC           = '#FEF3C7'
TBL_H_BG        = '#065F46'
TBL_EC_COL      = '#047857'
LINE_C          = '#374151'
PK_C            = '#92400E'
FK_C            = '#1E40AF'
CARD_C          = '#B91C1C'

EW, EH   = 2.6, 0.72
RR, RRX  = 0.62, 1.05

# ── primitives ────────────────────────────────────────────────────────────────
def ent(cx, cy, label, weak=False):
    r = FancyBboxPatch((cx - EW/2, cy - EH/2), EW, EH,
                       boxstyle='square,pad=0', linewidth=2.5,
                       edgecolor=ENT_EC, facecolor=ENT_FC, zorder=4)
    ax.add_patch(r)
    if weak:
        r2 = FancyBboxPatch((cx - EW/2 + 0.11, cy - EH/2 + 0.10),
                            EW - 0.22, EH - 0.20,
                            boxstyle='square,pad=0', linewidth=1.5,
                            edgecolor=ENT_EC, facecolor='none', zorder=5)
        ax.add_patch(r2)
    ax.text(cx, cy, label, ha='center', va='center',
            fontsize=9.5, fontweight='bold', color='#1E3A8A', zorder=6)


def rel_diamond(cx, cy, label, double=False):
    pts = [[cx, cy + RR], [cx + RRX, cy], [cx, cy - RR], [cx - RRX, cy]]
    p = plt.Polygon(pts, closed=True, linewidth=2.1,
                    edgecolor=REL_EC, facecolor=REL_FC, zorder=4)
    ax.add_patch(p)
    if double:
        s = 0.09
        pts2 = [[cx, cy + RR - s], [cx + RRX - s*1.7, cy],
                [cx, cy - RR + s], [cx - RRX + s*1.7, cy]]
        ax.add_patch(plt.Polygon(pts2, closed=True, linewidth=1.4,
                                 edgecolor=REL_EC, facecolor='none', zorder=5))
    ax.text(cx, cy, label, ha='center', va='center',
            fontsize=7.5, fontweight='bold', color='#4C1D95', zorder=6)


def atr(cx, cy, label, pk=False):
    fc = PK_FC if pk else ATR_FC
    lw = 2.1 if pk else 1.4
    ew = max(len(label) * 0.17 + 0.5, 1.9)
    ax.add_patch(Ellipse((cx, cy), ew, 0.46, linewidth=lw,
                         edgecolor=ATR_EC, facecolor=fc, zorder=4))
    fw = 'bold' if pk else 'normal'
    ax.text(cx, cy + 0.05, label, ha='center', va='center',
            fontsize=7.5, fontweight=fw, color='#064E3B', zorder=6)
    if pk:
        uw = min(len(label) * 0.085, ew * 0.75)
        ax.plot([cx - uw/2, cx + uw/2], [cy - 0.09, cy - 0.09],
                color='#064E3B', linewidth=1.2, zorder=7)


def ln(x1, y1, x2, y2, double=False, lw=1.6):
    ax.plot([x1, x2], [y1, y2], color=LINE_C, linewidth=lw, zorder=2)
    if double:
        dx, dy = x2 - x1, y2 - y1
        L = np.hypot(dx, dy)
        if L:
            nx, ny = -dy/L * 0.08, dx/L * 0.08
            ax.plot([x1+nx, x2+nx], [y1+ny, y2+ny],
                    color=LINE_C, linewidth=lw, zorder=2)


def card(x, y, txt):
    ax.text(x, y, txt, ha='center', va='center',
            fontsize=11, fontweight='bold', color=CARD_C, zorder=8,
            bbox=dict(boxstyle='round,pad=0.12', facecolor='white',
                      edgecolor='#FCA5A5', linewidth=1.0))


def transform_arrow(x1, x2, y, label='transforms to'):
    ax.annotate('', xy=(x2, y), xytext=(x1, y),
                arrowprops=dict(arrowstyle='->', color='#6B7280',
                                lw=2.8, mutation_scale=22))
    ax.text((x1 + x2) / 2, y + 0.30, label,
            ha='center', va='bottom', fontsize=8, color='#6B7280', style='italic')


def draw_table(x, y, title, columns, col_width=3.8, row_h=0.42):
    """
    Draw a relational table box.
    columns = list of (col_name, tag)  tag: 'PK', 'FK', 'PK/FK', or ''
    Returns bottom y of the table.
    """
    # header
    ax.add_patch(FancyBboxPatch((x, y - row_h), col_width, row_h,
                                boxstyle='square,pad=0', linewidth=1.8,
                                edgecolor=TBL_EC_COL, facecolor=TBL_H_BG, zorder=4))
    ax.text(x + col_width / 2, y - row_h / 2, title,
            ha='center', va='center', fontsize=9, fontweight='bold',
            color='white', zorder=6)
    for i, (cname, tag) in enumerate(columns):
        ry = y - (i + 2) * row_h
        fc = PK_FC if 'PK' in tag else '#FFFFFF'
        ax.add_patch(FancyBboxPatch((x, ry), col_width, row_h,
                                    boxstyle='square,pad=0', linewidth=1.0,
                                    edgecolor=TBL_EC_COL, facecolor=fc, zorder=4))
        fw = 'bold' if 'PK' in tag else 'normal'
        ax.text(x + 0.15, ry + row_h / 2, cname,
                ha='left', va='center', fontsize=8.5,
                fontweight=fw, color='#111827', zorder=6)
        if tag:
            tc = PK_C if tag == 'PK' else FK_C
            ax.text(x + col_width - 0.13, ry + row_h / 2, tag,
                    ha='right', va='center', fontsize=7.5,
                    fontweight='bold', color=tc, zorder=6)
    return y - (len(columns) + 1) * row_h  # bottom edge


def fk_arrow(x1, y, x2, label='FK →'):
    """Horizontal arrow between two tables with label."""
    ax.annotate('', xy=(x2, y), xytext=(x1, y),
                arrowprops=dict(arrowstyle='->', color=FK_C, lw=1.8, mutation_scale=14))
    ax.text((x1 + x2) / 2, y + 0.13, label,
            ha='center', va='bottom', fontsize=7.5,
            fontweight='bold', color=FK_C)


# ═════════════════════════════════════════════════════════════════════════════
# MAIN TITLE
# ═════════════════════════════════════════════════════════════════════════════
ax.text(12.0, 16.6,
        'Figure 2  —  Modified Relational Compatibility Diagram',
        ha='center', va='center', fontsize=13.5, fontweight='bold', color='#111827')
ax.axhline(16.2, color='#D1D5DB', linewidth=1.2, xmin=0.01, xmax=0.99)

# ═════════════════════════════════════════════════════════════════════════════
# PANEL A  —  M:N  →  Junction Table
# ═════════════════════════════════════════════════════════════════════════════
ax.text(0.3, 15.85,
        'A   M:N Relationship  →  track_artist Junction Table',
        fontsize=10.5, fontweight='bold', color='#1F2937')
ax.axhline(15.65, color='#E5E7EB', linewidth=0.8, xmin=0.01, xmax=0.99)

# --- ER side (BEFORE) ---
ax.text(4.2, 15.35, 'BEFORE  (Conceptual E/R)',
        ha='center', fontsize=8.5, color='#6B7280', style='italic')

TR_A = (2.5, 14.1)
PE_A = (4.2, 12.7)
AR_A = (5.9, 14.1)

ln(*TR_A, *PE_A)
ln(*PE_A, *AR_A)
card(3.0,  13.65, 'M')
card(5.4,  13.65, 'N')
ent(*TR_A, 'Track')
ent(*AR_A, 'Artist')
rel_diamond(*PE_A, 'performs')

# is_primary attribute on the 'performs' diamond
ln(PE_A[0], PE_A[1], PE_A[0], 11.55)
atr(PE_A[0], 11.35, 'is_primary')
ax.text(PE_A[0], 11.0, '(relationship attr.)',
        ha='center', fontsize=6.5, color='#6B7280', style='italic')

# --- transform arrow ---
transform_arrow(7.1, 8.7, 12.9)

# --- Relational side (AFTER) ---
ax.text(16.5, 15.35, 'AFTER  (Relational Schema)',
        ha='center', fontsize=8.5, color='#6B7280', style='italic')

# track table
draw_table(9.0, 15.0, 'track',
           [('track_id', 'PK'), ('track_name', ''), ('popularity', ''), ('...', '')],
           col_width=3.2)

# track_artist junction
draw_table(13.0, 15.0, 'track_artist',
           [('track_id',   'PK/FK'),
            ('artist_id',  'PK/FK'),
            ('is_primary', '')],
           col_width=3.8)

# artist table
draw_table(17.5, 15.0, 'artist',
           [('artist_id', 'PK'), ('artist_name', ''), ('...', '')],
           col_width=3.0)

# FK relationship arrows
fk_arrow(12.2, 12.85, 13.0, 'FK →')
fk_arrow(16.8, 12.85, 17.5, '← FK')

# Annotation box for Panel A
ax.add_patch(FancyBboxPatch((9.0, 11.1), 11.5, 0.88,
                             boxstyle='round,pad=0.15', linewidth=1.2,
                             edgecolor='#C4B5FD', facecolor='#EDE9FE', alpha=0.85, zorder=3))
ax.text(9.25, 11.54,
        'Key point: The M:N "performs" relationship cannot be represented as a single FK. '
        'A junction table is required.\n'
        'track_artist uses a composite PK (track_id, artist_id). '
        'is_primary moves from the diamond into the junction row.',
        fontsize=8, color='#3B0764', va='center', zorder=4)


# ═════════════════════════════════════════════════════════════════════════════
# PANEL B  —  Weak Entity  →  Shared PK
# ═════════════════════════════════════════════════════════════════════════════
ax.axhline(10.75, color='#D1D5DB', linewidth=1.2, xmin=0.01, xmax=0.99)
ax.text(0.3, 10.55,
        'B   Weak Entity  →  audio_features with Shared Primary Key',
        fontsize=10.5, fontweight='bold', color='#1F2937')
ax.axhline(10.35, color='#E5E7EB', linewidth=0.8, xmin=0.01, xmax=0.99)

# --- ER side (BEFORE) ---
ax.text(3.8, 10.05, 'BEFORE  (Conceptual E/R)',
        ha='center', fontsize=8.5, color='#6B7280', style='italic')

TR_B = (1.7, 8.5)
HF_B = (3.8, 8.5)
AF_B = (5.9, 8.5)

ln(*TR_B, *HF_B)
ln(*HF_B, *AF_B, double=True)
card(2.6, 8.82, '1')
card(5.0, 8.82, '1')
ent(*TR_B, 'Track')
ent(*AF_B, 'AudioFeature', weak=True)
rel_diamond(*HF_B, 'has\nfeatures', double=True)

# partial key attribute below AudioFeature
ln(AF_B[0], AF_B[1] - EH/2, AF_B[0], 7.6)
atr(AF_B[0], 7.4, 'track_id', pk=True)
ax.text(AF_B[0], 7.07, 'partial key',
        ha='center', fontsize=6.5, color='#92400E', style='italic')

ax.text(3.8, 9.4, 'Double line = total participation\n(every AudioFeature must have a Track)',
        ha='center', fontsize=7, color='#374151', style='italic')

# --- transform arrow ---
transform_arrow(7.2, 8.7, 8.5)

# --- Relational side (AFTER) ---
ax.text(16.5, 10.05, 'AFTER  (Relational Schema)',
        ha='center', fontsize=8.5, color='#6B7280', style='italic')

# track table  (top y = 9.8, 3 data rows + header = 4 × 0.42 = 1.68 tall  → bottom = 8.12)
draw_table(9.0, 9.8, 'track',
           [('track_id', 'PK'), ('track_name', ''), ('...', '')],
           col_width=3.2)

# audio_features table  (4 data rows + header = 5 × 0.42 = 2.10 tall → bottom = 7.70)
draw_table(13.5, 9.8, 'audio_features',
           [('track_id',     'PK/FK'),
            ('danceability', ''),
            ('energy',       ''),
            ('key_id',       'FK'),
            ('... (11 cols)','')],
           col_width=4.2)

# Shared PK arrow between track.track_id row and audio_features.track_id row
fk_arrow(12.2, 9.17, 13.5, 'Shared PK / FK')

# Annotation box for Panel B  (starts at 5.60, ends at 6.75 — well below table bottom 7.70)
ax.add_patch(FancyBboxPatch((9.0, 5.60), 9.5, 1.10,
                             boxstyle='round,pad=0.15', linewidth=1.2,
                             edgecolor='#6EE7B7', facecolor='#ECFDF5', alpha=0.9, zorder=3))
ax.text(9.25, 6.15,
        'Key point: AudioFeature is a weak entity — it cannot exist without its owner Track.\n'
        'In the relational schema, track_id serves as the PRIMARY KEY of audio_features\n'
        '(not a surrogate). This enforces the 1:1 constraint and the weak-entity dependency.',
        fontsize=8, color='#064E3B', va='center', zorder=4)


# ═════════════════════════════════════════════════════════════════════════════
# LEGEND STRIP (bottom)
# ═════════════════════════════════════════════════════════════════════════════
ax.axhline(5.95, color='#D1D5DB', linewidth=1.0, xmin=0.01, xmax=0.99)
legend_items = [
    (PK_FC,    TBL_EC_COL, 'Yellow row = Primary Key (PK)'),
    ('#FFFFFF', TBL_EC_COL, 'White row = regular attribute'),
    (ENT_FC,   ENT_EC,     'Blue box = Entity'),
    (REL_FC,   REL_EC,     'Purple diamond = Relationship'),
]
lx = 1.0
for fc, ec, lbl in legend_items:
    ax.add_patch(FancyBboxPatch((lx, 5.32), 0.7, 0.38,
                                boxstyle='square,pad=0', linewidth=1.2,
                                edgecolor=ec, facecolor=fc, zorder=4))
    ax.text(lx + 0.85, 5.51, lbl, va='center', fontsize=7.8, color='#374151')
    lx += 4.8

ax.text(12.0, 0.5,
        'Spotify Tracks Database  —  Stage 2 Design Documentation',
        ha='center', fontsize=8.5, color='#9CA3AF', style='italic')

plt.savefig('/Users/alizeaarif/Desktop/DATABASES FY/fig2_relational_mapping.png',
            dpi=160, bbox_inches='tight', pad_inches=0.4, facecolor=BG)
plt.close()
print('Saved: fig2_relational_mapping.png')

