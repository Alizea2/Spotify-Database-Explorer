"""
Spotify DB — ER Diagram Generator
Produces two PNG files with DISTINCT purposes:

  er_diagram_no_cardinality.png   → Diagram 1: Conceptual E/R Model
      Real-world view of the Spotify domain BEFORE relational mapping.
      - Track ↔ Artist via M:N "performs" diamond; is_primary on the relationship
      - Track ↔ Genre via M:N "classified_as" diamond (faithful to raw CSV)
      - AudioFeature as a weak entity (double rectangle)
      - No cardinality labels (purely conceptual)

  er_diagram_with_cardinality.png → Diagram 2: Relational E/R Model
      Implementation view — what actually exists in MySQL.
      - track_artist associative ENTITY replacing the M:N diamond
      - is_primary moves INTO track_artist (relations can't store attrs)
      - Genre simplified to 1:M FK on Track (implementation decision)
      - AudioFeature becomes a regular entity; track_id is full PK/FK
      - Full cardinality labels on every relationship
      - PK annotations on key attributes
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Ellipse
import numpy as np


# ─────────────────────────────────────────────────────────────────────────────
# Shared colour palette
# ─────────────────────────────────────────────────────────────────────────────
ENT_EC, ENT_FC = '#1D4ED8', '#DBEAFE'   # entity box
REL_EC, REL_FC = '#6D28D9', '#EDE9FE'   # relationship diamond
ATR_EC, ATR_FC = '#047857', '#D1FAE5'   # attribute ellipse
PK_FC           = '#FEF3C7'              # PK / partial-key fill
CARD_C          = '#B91C1C'              # cardinality label
LINE_C          = '#374151'              # connector lines
BG              = '#F9FAFB'             # background

EW, EH   = 2.8, 0.85     # entity box size
RR, RRX  = 0.72, 1.25    # relationship diamond half-heights / half-widths


def _setup_canvas(w=35, h=24):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis('off')
    ax.set_facecolor(BG)
    fig.patch.set_facecolor(BG)
    return fig, ax


def _primitives(ax, show_cardinality=True):
    """Return drawing helpers bound to *ax*."""

    def ent(cx, cy, label, weak=False):
        ax.add_patch(mpatches.FancyBboxPatch(
            (cx - EW/2, cy - EH/2), EW, EH,
            boxstyle='square,pad=0', linewidth=2.8,
            edgecolor=ENT_EC, facecolor=ENT_FC, zorder=4))
        if weak:
            ax.add_patch(mpatches.FancyBboxPatch(
                (cx - EW/2 + 0.13, cy - EH/2 + 0.10), EW - 0.26, EH - 0.20,
                boxstyle='square,pad=0', linewidth=1.6,
                edgecolor=ENT_EC, facecolor='none', zorder=5))
        ax.text(cx, cy, label, ha='center', va='center',
                fontsize=10, fontweight='bold', color='#1E3A8A', zorder=6)

    def rel(cx, cy, label, double=False):
        pts = [[cx, cy + RR], [cx + RRX, cy],
               [cx, cy - RR], [cx - RRX, cy]]
        ax.add_patch(plt.Polygon(pts, closed=True, linewidth=2.2,
                                 edgecolor=REL_EC, facecolor=REL_FC, zorder=4))
        if double:
            s = 0.11
            pts2 = [[cx, cy + RR - s], [cx + RRX - s*1.7, cy],
                    [cx, cy - RR + s], [cx - RRX + s*1.7, cy]]
            ax.add_patch(plt.Polygon(pts2, closed=True, linewidth=1.5,
                                     edgecolor=REL_EC, facecolor='none', zorder=5))
        ax.text(cx, cy, label, ha='center', va='center',
                fontsize=8, fontweight='bold', color='#4C1D95', zorder=6)

    def atr(cx, cy, label, pk=False, derived=False, partial=False):
        fc = PK_FC if (pk or partial) else ATR_FC
        ls = '--' if derived else '-'
        lw = 2.2 if (pk or partial) else 1.5
        ew = max(len(label) * 0.17 + 0.6, 2.0)
        ax.add_patch(Ellipse((cx, cy), ew, 0.52, linewidth=lw,
                             edgecolor=ATR_EC, facecolor=fc,
                             linestyle=ls, zorder=4))
        fw = 'bold' if (pk or partial) else 'normal'
        ax.text(cx, cy + 0.06, label, ha='center', va='center',
                fontsize=7.5, fontweight=fw, color='#064E3B', zorder=6)
        if pk or partial:
            uw = min(len(label) * 0.087, ew * 0.78)
            ax.plot([cx - uw/2, cx + uw/2], [cy - 0.08, cy - 0.08],
                    color='#064E3B', linewidth=1.3, zorder=7)

    def ln(x1, y1, x2, y2, double=False):
        ax.plot([x1, x2], [y1, y2], color=LINE_C, linewidth=1.6, zorder=2)
        if double:
            dx, dy = x2 - x1, y2 - y1
            L = np.hypot(dx, dy)
            if L:
                nx, ny = -dy/L * 0.09, dx/L * 0.09
                ax.plot([x1+nx, x2+nx], [y1+ny, y2+ny],
                        color=LINE_C, linewidth=1.6, zorder=2)

    def card(x, y, txt):
        if show_cardinality:
            ax.text(x, y, txt, ha='center', va='center',
                    fontsize=12, fontweight='bold', color=CARD_C, zorder=8,
                    bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                              edgecolor='#FCA5A5', linewidth=1.2))

    def al(entity_pos, cx, cy, label, **kw):
        """Attribute with connector from entity centre."""
        ln(entity_pos[0], entity_pos[1], cx, cy)
        atr(cx, cy, label, **kw)

    return ent, rel, atr, ln, card, al


def _legend(ax, lx=13.0, ly=8.3, extra_rows=None):
    """Draw the Chen-notation legend box."""
    SP = 0.75
    rows = [
        (ly,        'Entity',                          'rect'),
        (ly - SP,   'Weak Entity (double rectangle)',  'weak'),
        (ly - 2*SP, 'Relationship',                    'diamond'),
        (ly - 3*SP, 'Attribute',                       'ellipse'),
        (ly - 4*SP, 'Primary Key (underlined)',        'pk'),
        (ly - 5*SP, 'Derived Attribute (dashed)',      'derived'),
        (ly - 6*SP, 'Partial Key of Weak Entity',      'partial'),
        (ly - 7*SP, 'Double line = Total Participation','dline'),
    ]
    if extra_rows:
        rows += extra_rows

    for y, txt, kind in rows:
        if kind == 'rect':
            ax.add_patch(mpatches.FancyBboxPatch(
                (lx+0.1, y-0.24), 1.6, 0.48,
                boxstyle='square,pad=0', linewidth=2.2,
                edgecolor=ENT_EC, facecolor=ENT_FC, zorder=10))
        elif kind == 'weak':
            ax.add_patch(mpatches.FancyBboxPatch(
                (lx+0.1, y-0.24), 1.6, 0.48,
                boxstyle='square,pad=0', linewidth=2.2,
                edgecolor=ENT_EC, facecolor=ENT_FC, zorder=10))
            ax.add_patch(mpatches.FancyBboxPatch(
                (lx+0.22, y-0.13), 1.36, 0.26,
                boxstyle='square,pad=0', linewidth=1.3,
                edgecolor=ENT_EC, facecolor='none', zorder=11))
        elif kind == 'diamond':
            cx = lx + 0.90
            pts = [[cx, y+0.30], [cx+0.60, y], [cx, y-0.30], [cx-0.60, y]]
            ax.add_patch(plt.Polygon(pts, closed=True, linewidth=1.6,
                                     edgecolor=REL_EC, facecolor=REL_FC, zorder=10))
        elif kind in ('ellipse', 'pk', 'derived', 'partial'):
            fc = PK_FC if kind in ('pk', 'partial') else ATR_FC
            ls = '--' if kind == 'derived' else '-'
            ax.add_patch(Ellipse((lx+0.90, y), 1.5, 0.42, linewidth=1.5,
                                 edgecolor=ATR_EC, facecolor=fc,
                                 linestyle=ls, zorder=10))
            if kind in ('pk', 'partial'):
                ax.plot([lx+0.90-0.42, lx+0.90+0.42], [y-0.10, y-0.10],
                        color='#064E3B', linewidth=1.2, zorder=11)
        elif kind == 'dline':
            ax.plot([lx+0.1, lx+1.7], [y+0.07, y+0.07], color=LINE_C, lw=1.8, zorder=10)
            ax.plot([lx+0.1, lx+1.7], [y-0.07, y-0.07], color=LINE_C, lw=1.8, zorder=10)

        ax.text(lx + 2.05, y, txt, ha='left', va='center',
                fontsize=8.5, color='#111827', zorder=10)

    box_h = 7 * SP + 0.85
    ax.add_patch(mpatches.FancyBboxPatch(
        (lx - 0.20, ly - 7*SP - 0.42), 7.0, box_h + 0.42,
        boxstyle='round,pad=0.15', linewidth=1.5,
        edgecolor='#6B7280', facecolor='white', alpha=0.92, zorder=9))
    ax.text(lx + 3.3, ly + 0.45, 'LEGEND',
            ha='center', va='center', fontsize=10, fontweight='bold',
            color='#1F2937', zorder=10)


# ══════════════════════════════════════════════════════════════════════════════
#  DIAGRAM 1 — Conceptual E/R Model  (Real-World View)
# ══════════════════════════════════════════════════════════════════════════════
def make_conceptual_er(out_path: str):
    fig, ax = _setup_canvas()
    ent, rel, atr, ln, card, al = _primitives(ax, show_cardinality=False)

    # Entity centres
    TR = (18.5, 13.0); AL = (8.5,  19.5); AR = (29.0, 19.5)
    GE = ( 5.0, 13.0); MC = (5.5,   6.5); AF = (29.5, 13.0)
    MK = (29.5,  5.5)

    # Relationship centres
    BL = (12.5, 16.5)  # belongs_to    Track – Album
    PE = (24.0, 16.5)  # performs      Track – Artist  (M:N)
    CL = (11.5, 13.0)  # classified_as Track – Genre   (M:N in reality)
    AS = (11.5,  9.5)  # assigned_to   Track – MoodCategory
    HF = (24.5, 13.0)  # has_features  Track – AudioFeature
    IK = (29.5,  9.0)  # in_key        AudioFeature – MusicalKey

    # Connectors (no cardinality labels)
    ln(*TR, *BL); ln(*BL, *AL)
    ln(*TR, *PE); ln(*PE, *AR)
    ln(*TR, *CL); ln(*CL, *GE)
    ln(*TR, *AS); ln(*AS, *MC)
    ln(*TR, *HF); ln(*HF, *AF, double=True)   # double = total participation
    ln(*AF, *IK); ln(*IK, *MK)

    # Entities
    ent(*TR, 'Track');  ent(*AL, 'Album');  ent(*AR, 'Artist')
    ent(*GE, 'Genre');  ent(*MC, 'Mood\nCategory')
    ent(*AF, 'AudioFeature', weak=True)
    ent(*MK, 'MusicalKey')

    # Relationships
    rel(*BL, 'belongs\nto')
    rel(*PE, 'performs')          # M:N
    rel(*CL, 'classified\nas')    # M:N in the real dataset
    rel(*AS, 'assigned\nto')
    rel(*HF, 'has\nfeatures', double=True)
    rel(*IK, 'in key')

    # Track attributes
    al(TR, 15.5, 15.0, 'track_id',   pk=True)
    al(TR, 18.5, 15.0, 'track_name')
    al(TR, 21.5, 15.0, 'popularity')
    al(TR, 15.5, 11.2, 'duration_ms')
    al(TR, 18.5, 11.2, 'explicit')

    # Album attributes
    al(AL,  6.0, 21.5, 'album_id',    pk=True)
    al(AL,  8.5, 21.5, 'album_name')
    al(AL, 11.5, 21.5, 'total_tracks', derived=True)

    # Artist attributes
    al(AR, 26.5, 21.5, 'artist_id',   pk=True)
    al(AR, 30.0, 21.5, 'artist_name')

    # Relationship attribute: is_primary on performs
    ln(PE[0], PE[1], 24.0, 18.5)
    atr(24.0, 18.5, 'is_primary')

    # Genre attributes
    al(GE, 3.0, 14.2, 'genre_id',   pk=True)
    al(GE, 3.0, 12.0, 'genre_name')

    # MoodCategory attributes
    al(MC, 3.0,  7.8, 'mood_id',    pk=True)
    al(MC, 3.0,  6.5, 'mood_name')
    al(MC, 3.0,  5.2, 'description')
    al(MC, 5.5,  4.2, 'valence_min')
    al(MC, 7.8,  4.2, 'valence_max')
    al(MC, 5.5,  8.5, 'energy_min')
    al(MC, 7.8,  8.5, 'energy_max')

    # AudioFeature attributes
    for cx, cy, lbl in [(33.0,14.8,'danceability'),(33.0,13.8,'energy'),
                        (33.0,12.8,'loudness'),(33.0,11.8,'mode'),
                        (33.0,10.8,'speechiness'),(33.0,9.8,'acousticness')]:
        al(AF, cx, cy, lbl)
    for cx, cy, lbl in [(26.0,14.8,'instrumentalness'),(26.0,13.8,'liveness'),
                        (26.0,12.8,'valence'),(26.0,11.8,'tempo'),
                        (26.0,10.8,'time_signature')]:
        al(AF, cx, cy, lbl)
    al(AF, 29.5, 15.5, 'track_id', partial=True)   # partial key of weak entity

    # MusicalKey attributes
    al(MK, 26.5, 3.8, 'key_id',      pk=True)
    al(MK, 29.5, 3.8, 'key_name')
    al(MK, 32.5, 3.8, 'key_notation')

    _legend(ax, lx=13.0, ly=8.3)

    ax.text(18.5, 23.2,
            'Spotify Tracks Database  —  Diagram 1: Conceptual E/R Model  (Real-World View)',
            ha='center', va='center', fontsize=13, fontweight='bold', color='#111827')
    ax.text(18.5, 22.6,
            'Shows the Spotify domain as it truly exists — M:N relationships, weak entities, '
            'relationship attributes — before any relational implementation decisions.',
            ha='center', va='center', fontsize=9, color='#6B7280', style='italic')

    plt.savefig(out_path, dpi=160, bbox_inches='tight', pad_inches=0.4, facecolor=BG)
    plt.close()
    print(f'✅  Saved: {out_path}')


# ══════════════════════════════════════════════════════════════════════════════
#  DIAGRAM 2 — Relational E/R Model  (MySQL Implementation)
# ══════════════════════════════════════════════════════════════════════════════
def make_relational_er(out_path: str):
    """
    Implementation view: shows the schema actually built in MySQL.

    Key transformations from the conceptual model:
      1. M:N Track ↔ Artist   →  track_artist ASSOCIATIVE ENTITY
         - is_primary moves from relationship attribute → entity attribute
      2. M:N Track ↔ Genre    →  simplified to 1:M (single genre_id FK on Track)
      3. Weak AudioFeature    →  regular entity; track_id is the full PK (shared/borrowed)
      4. Full cardinalities on every relationship
    """
    fig, ax = _setup_canvas()
    ent, rel, atr, ln, card, al = _primitives(ax, show_cardinality=True)

    # ── Entity centres ────────────────────────────────────────────────────────
    TR = (17.0, 13.0)   # Track (slightly left of centre)
    AL = ( 8.0, 19.5)   # Album
    AR = (31.0, 20.5)   # Artist (pushed right to give room for TrackArtist)
    TA = (24.5, 17.5)   # track_artist  ← ASSOCIATIVE ENTITY (was M:N diamond)
    GE = ( 4.5, 13.0)   # Genre
    MC = ( 5.0,  6.5)   # MoodCategory
    AF = (29.5, 13.0)   # AudioFeature  ← now a REGULAR entity (not weak)
    MK = (29.5,  5.5)   # MusicalKey

    # ── Relationship centres ──────────────────────────────────────────────────
    BL = (11.5, 16.5)   # belongs_to    Track – Album
    CL = (10.5, 13.0)   # classified_as Track – Genre  (1:M simplified)
    AS = (10.5,  9.5)   # assigned_to   Track – MoodCategory
    HF = (23.0, 13.0)   # has_features  Track – AudioFeature  (1:1 regular)
    IK = (29.5,  9.0)   # in_key        AudioFeature – MusicalKey

    # ── Connectors ────────────────────────────────────────────────────────────

    # Track – belongs_to – Album
    ln(*TR, *BL); ln(*BL, *AL)
    card((TR[0]+BL[0])/2 + 0.50, (TR[1]+BL[1])/2 - 0.30, 'M')
    card((AL[0]+BL[0])/2 - 0.30, (AL[1]+BL[1])/2 + 0.40, '1')

    # Track – classified_as – Genre  (1:M — implementation simplification)
    ln(*TR, *CL); ln(*CL, *GE)
    card((TR[0]+CL[0])/2 + 0.25, (TR[1]+CL[1])/2 + 0.40, 'M')
    card((GE[0]+CL[0])/2 + 0.25, (GE[1]+CL[1])/2 + 0.40, '1')

    # Track – assigned_to – MoodCategory
    ln(*TR, *AS); ln(*AS, *MC)
    card((TR[0]+AS[0])/2 + 0.65, (TR[1]+AS[1])/2 + 0.15, 'M')
    card((MC[0]+AS[0])/2 - 0.60, (MC[1]+AS[1])/2 + 0.30, '1')

    # Track – has_features – AudioFeature  (1:1 regular — no double line)
    ln(*TR, *HF); ln(*HF, *AF)
    card((TR[0]+HF[0])/2 - 0.40, (TR[1]+HF[1])/2 + 0.40, '1')
    card((AF[0]+HF[0])/2 + 0.35, (AF[1]+HF[1])/2 + 0.40, '1')

    # AudioFeature – in_key – MusicalKey
    ln(*AF, *IK); ln(*IK, *MK)
    card((AF[0]+IK[0])/2 + 0.55, (AF[1]+IK[1])/2 + 0.20, 'M')
    card((MK[0]+IK[0])/2 + 0.55, (MK[1]+IK[1])/2 - 0.25, '1')

    # Track → track_artist  (1:M — one track has many track_artist rows)
    ln(*TR, *TA)
    card((TR[0]+TA[0])/2 - 0.70, (TR[1]+TA[1])/2 + 0.10, '1')
    card((TR[0]+TA[0])/2 + 0.50, (TR[1]+TA[1])/2 - 0.10, 'M')

    # Artist → track_artist  (1:M — one artist has many track_artist rows)
    ln(*AR, *TA)
    card((AR[0]+TA[0])/2 + 0.70, (AR[1]+TA[1])/2 + 0.10, '1')
    card((AR[0]+TA[0])/2 - 0.50, (AR[1]+TA[1])/2 - 0.10, 'M')

    # ── Draw entities ─────────────────────────────────────────────────────────
    ent(*TR, 'Track')
    ent(*AL, 'Album')
    ent(*AR, 'Artist')
    ent(*TA, 'track_artist')     # ← associative entity (normal rectangle)
    ent(*GE, 'Genre')
    ent(*MC, 'Mood\nCategory')
    ent(*AF, 'AudioFeature')     # ← regular entity (NO double rectangle)
    ent(*MK, 'MusicalKey')

    # ── Draw relationships ────────────────────────────────────────────────────
    rel(*BL, 'belongs\nto')
    rel(*CL, 'classified\nas')
    rel(*AS, 'assigned\nto')
    rel(*HF, 'has\nfeatures')    # regular diamond (not double — AF not weak)
    rel(*IK, 'in key')
    # NOTE: No "performs" diamond — replaced by track_artist entity above

    # ── Annotation: label the two FK edges on track_artist ───────────────────
    ax.text((TR[0]+TA[0])/2 - 0.05, (TR[1]+TA[1])/2 + 0.55,
            'track_id  (FK)', ha='center', fontsize=7.5,
            color='#1E40AF', fontweight='bold', zorder=8)
    ax.text((AR[0]+TA[0])/2 + 0.10, (AR[1]+TA[1])/2 - 0.55,
            'artist_id  (FK)', ha='center', fontsize=7.5,
            color='#1E40AF', fontweight='bold', zorder=8)

    # ── track_artist attributes ───────────────────────────────────────────────
    al(TA, 21.5, 20.2, 'track_id',  pk=True)    # composite PK col 1
    al(TA, 25.5, 20.2, 'artist_id', pk=True)    # composite PK col 2
    al(TA, 28.0, 17.5, 'is_primary')            # moved out of relationship diamond

    # Label composite PK note
    ax.text(23.5, 20.9, '(composite PK)',
            ha='center', fontsize=7, color='#92400E', style='italic', zorder=8)

    # ── Track attributes ──────────────────────────────────────────────────────
    al(TR, 14.0, 15.0, 'track_id',   pk=True)
    al(TR, 17.0, 15.0, 'track_name')
    al(TR, 20.0, 15.0, 'popularity')
    al(TR, 14.0, 11.2, 'duration_ms')
    al(TR, 17.0, 11.2, 'explicit')

    # ── Album attributes ──────────────────────────────────────────────────────
    al(AL,  5.5, 21.5, 'album_id',    pk=True)
    al(AL,  8.0, 21.5, 'album_name')
    al(AL, 11.0, 21.5, 'total_tracks', derived=True)

    # ── Artist attributes ─────────────────────────────────────────────────────
    al(AR, 29.0, 22.5, 'artist_id',   pk=True)
    al(AR, 32.5, 22.5, 'artist_name')

    # ── Genre attributes ──────────────────────────────────────────────────────
    al(GE, 2.5, 14.2, 'genre_id',   pk=True)
    al(GE, 2.5, 12.0, 'genre_name')

    # ── MoodCategory attributes ───────────────────────────────────────────────
    al(MC, 2.5,  7.8, 'mood_id',    pk=True)
    al(MC, 2.5,  6.5, 'mood_name')
    al(MC, 2.5,  5.2, 'description')
    al(MC, 5.0,  4.2, 'valence_min')
    al(MC, 7.3,  4.2, 'valence_max')
    al(MC, 5.0,  8.5, 'energy_min')
    al(MC, 7.3,  8.5, 'energy_max')

    # ── AudioFeature attributes  (track_id is FULL PK, not partial) ───────────
    al(AF, 29.5, 15.5, 'track_id', pk=True)    # full PK — shared with Track
    for cx, cy, lbl in [(33.0,14.8,'danceability'),(33.0,13.8,'energy'),
                        (33.0,12.8,'loudness'),(33.0,11.8,'mode'),
                        (33.0,10.8,'speechiness'),(33.0,9.8,'acousticness')]:
        al(AF, cx, cy, lbl)
    for cx, cy, lbl in [(26.0,14.8,'instrumentalness'),(26.0,13.8,'liveness'),
                        (26.0,12.8,'valence'),(26.0,11.8,'tempo'),
                        (26.0,10.8,'time_signature')]:
        al(AF, cx, cy, lbl)

    # ── MusicalKey attributes ─────────────────────────────────────────────────
    al(MK, 26.5, 3.8, 'key_id',      pk=True)
    al(MK, 29.5, 3.8, 'key_name')
    al(MK, 32.5, 3.8, 'key_notation')

    # ── Implementation notes box ──────────────────────────────────────────────
    nx, ny = 5.5, 2.8
    ax.add_patch(mpatches.FancyBboxPatch(
        (nx, ny - 1.55), 7.5, 1.70,
        boxstyle='round,pad=0.15', linewidth=1.2,
        edgecolor='#C4B5FD', facecolor='#EDE9FE', alpha=0.88, zorder=3))
    ax.text(nx + 0.20, ny - 0.30,
            'Implementation changes from Conceptual Model:\n'
            '  \u2460  M:N Track\u2194Artist  \u2192  track_artist entity (junction table)\n'
            '  \u2461  is_primary: relationship attr  \u2192  entity attribute\n'
            '  \u2462  M:N Genre  \u2192  1:M (single genre_id FK on Track)\n'
            '  \u2463  Weak AudioFeature  \u2192  regular entity; track_id = full PK',
            fontsize=8, color='#3B0764', va='top', zorder=4, linespacing=1.55)

    # ── Legend ────────────────────────────────────────────────────────────────
    _legend(ax, lx=14.5, ly=7.8)

    # ── Title ─────────────────────────────────────────────────────────────────
    ax.text(18.5, 23.2,
            'Spotify Tracks Database  —  Diagram 2: Relational E/R Model  (MySQL Implementation)',
            ha='center', va='center', fontsize=13, fontweight='bold', color='#111827')
    ax.text(18.5, 22.6,
            'Shows the schema as implemented in MySQL — associative entities, shared PKs, '
            '1:M simplifications, and explicit cardinalities.',
            ha='center', va='center', fontsize=9, color='#6B7280', style='italic')

    plt.savefig(out_path, dpi=160, bbox_inches='tight', pad_inches=0.4, facecolor=BG)
    plt.close()
    print(f'✅  Saved: {out_path}')


# ── Generate both diagrams ─────────────────────────────────────────────────────
BASE = '/Users/alizeaarif/Desktop/DATABASES FY/'
make_conceptual_er(out_path=BASE + 'er_diagram_no_cardinality.png')
make_relational_er(out_path=BASE + 'er_diagram_with_cardinality.png')
