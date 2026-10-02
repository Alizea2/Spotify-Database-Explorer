'use strict';
/**
 * Pure helper functions for SVG coordinate generation and data
 * classification. All SVG geometry is computed here, server-side,
 * before being handed to the EJS templates — templates only place
 * numbers into markup, they never compute layout.
 */

/** Point on a circle of given radius/center at an angle (degrees, 0 = up). */
function polar(cx, cy, angleDeg, radius) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return {
    x: Math.round((cx + radius * Math.cos(rad)) * 100) / 100,
    y: Math.round((cy + radius * Math.sin(rad)) * 100) / 100,
  };
}

/** Error function approximation (Abramowitz & Stegun 7.1.26), used to turn a Z-score into a percentile. */
function erf(x) {
  const sign = x < 0 ? -1 : 1;
  x = Math.abs(x);
  const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741, a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
  const t = 1 / (1 + p * x);
  const y = 1 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
  return sign * y;
}

/** Converts a Z-score to a percentile (0-100) under a normal-distribution assumption. */
function zToPercentile(z) {
  const p = 0.5 * (1 + erf(z / Math.SQRT2)) * 100;
  return Math.min(99.9, Math.max(0.1, p));
}

/** Weighted mean of a numeric field across rows, weighted by track_count. */
function weightedAvg(rows, field, weightField = 'track_count') {
  let sumW = 0;
  let sumWV = 0;
  for (const r of rows) {
    const w = Number(r[weightField]) || 0;
    const v = Number(r[field]);
    if (Number.isFinite(v)) {
      sumW += w;
      sumWV += w * v;
    }
  }
  return sumW > 0 ? sumWV / sumW : 0;
}

/** Builds the 6-axis SVG radar polygon (points string) for a mood profile. */
const RADAR_AXES = [
  { key: 'danceability', label: 'Danceability' },
  { key: 'energy', label: 'Energy' },
  { key: 'valence', label: 'Valence' },
  { key: 'tempo', label: 'Tempo' },
  { key: 'acousticness', label: 'Acousticness' },
  { key: 'speechiness', label: 'Speechiness' },
];

function buildRadar(values, cx, cy, maxRadius) {
  const n = RADAR_AXES.length;
  const step = 360 / n;
  const axisLines = [];
  const labelPoints = [];
  const polygonPoints = [];

  RADAR_AXES.forEach((axis, i) => {
    const angle = i * step;
    const tip = polar(cx, cy, angle, maxRadius);
    axisLines.push({ x1: cx, y1: cy, x2: tip.x, y2: tip.y });

    const labelPt = polar(cx, cy, angle, maxRadius + 18);
    labelPoints.push({ x: labelPt.x, y: labelPt.y, label: axis.label });

    const value = Math.max(0, Math.min(1, values[axis.key] ?? 0));
    const pt = polar(cx, cy, angle, value * maxRadius);
    polygonPoints.push(`${pt.x},${pt.y}`);
  });

  return {
    axisLines,
    labelPoints,
    polygon: polygonPoints.join(' '),
  };
}

/** Smooth SVG path (Catmull-Rom → cubic Bezier) through a list of {x,y} points. */
function smoothPath(points) {
  if (points.length < 2) return '';
  const r2 = (n) => Math.round(n * 100) / 100;
  const d = [`M ${r2(points[0].x)} ${r2(points[0].y)}`];
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i === 0 ? 0 : i - 1];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2 < points.length ? i + 2 : i + 1];
    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;
    d.push(`C ${r2(cp1x)} ${r2(cp1y)}, ${r2(cp2x)} ${r2(cp2y)}, ${r2(p2.x)} ${r2(p2.y)}`);
  }
  return d.join(' ');
}

/** Plain-English anomaly explanation, mirrors the Node.js server logic in the spec. */
function generateAnomalyExplanation(track) {
  const parts = [];
  if (Math.abs(track.energy_zscore) > 1.8) {
    parts.push(
      `energy ${track.energy_zscore > 0 ? 'far above' : 'far below'} ` +
      `its ${track.genre_name} peers (${track.energy_zscore}σ)`
    );
  }
  if (Math.abs(track.valence_zscore) > 1.8) {
    parts.push(
      `unusually ${track.valence_zscore > 0 ? 'cheerful' : 'dark'} ` +
      `for its genre (${track.valence_zscore}σ)`
    );
  }
  if (Math.abs(track.dance_zscore) > 1.8) {
    parts.push(
      `danceability ${track.dance_zscore > 0 ? 'shockingly high' : 'surprisingly low'} ` +
      `(${track.dance_zscore}σ)`
    );
  }
  if (Math.abs(track.acoustic_zscore) > 1.8) {
    parts.push(
      `acousticness ${track.acoustic_zscore > 0 ? 'far too acoustic' : 'far too synthetic'} ` +
      `(${track.acoustic_zscore}σ)`
    );
  }
  if (parts.length === 0) return `This ${track.genre_name} track is a borderline statistical anomaly.`;
  return `This ${track.genre_name} track is ${parts.join(', and ')}.`;
}

module.exports = {
  polar,
  weightedAvg,
  buildRadar,
  smoothPath,
  zToPercentile,
  generateAnomalyExplanation,
};
