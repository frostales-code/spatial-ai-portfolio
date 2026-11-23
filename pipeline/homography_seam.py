"""Perspective-Aware Modulus Seam Projection via deterministic 2D Homography (H / H^-1)."""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np
from pydantic import BaseModel, Field


class Point2D(BaseModel):
    """2D coordinate in image pixel space or orthographic millimeter space."""

    x: float
    y: float


class OpeningRectMm(BaseModel):
    """Door or window cutout in orthographic facade plane coordinates (millimeters)."""

    x_min: float = Field(..., ge=0.0)
    y_min: float = Field(..., ge=0.0)
    x_max: float = Field(..., gt=0.0)
    y_max: float = Field(..., gt=0.0)


class SeamLine2D(BaseModel):
    """Projected panel seam line segment in image pixel space."""

    orientation: str
    start: Point2D
    end: Point2D


class SeamProjectionResult(BaseModel):
    """Deterministic perspective panel grid output ready for SVG overlay or ControlNet conditioning."""

    homography_matrix: list[list[float]]
    inverse_homography_matrix: list[list[float]]
    seam_segments: list[SeamLine2D]
    vertical_vanishing_deviation_deg: float
    panel_count_estimate: int


def compute_homography(src_pts: Iterable[Point2D], dst_pts: Iterable[Point2D]) -> np.ndarray:
    """Solve 3x3 planar homography H mapping src_pts -> dst_pts via Direct Linear Transform (DLT)."""
    src = [(p.x, p.y) for p in src_pts]
    dst = [(p.x, p.y) for p in dst_pts]
    if len(src) != 4 or len(dst) != 4:
        raise ValueError("Exactly 4 corresponding point pairs are required for homography.")

    rows: list[list[float]] = []
    for (x, y), (u, v) in zip(src, dst):
        rows.append([-x, -y, -1.0, 0.0, 0.0, 0.0, x * u, y * u, u])
        rows.append([0.0, 0.0, 0.0, -x, -y, -1.0, x * v, y * v, v])

    a_mat = np.asarray(rows, dtype=np.float64)
    _, _, vt = np.linalg.svd(a_mat)
    h = vt[-1].reshape(3, 3)
    if abs(h[2, 2]) < 1e-12:
        raise ValueError("Degenerate homography configuration.")
    return h / h[2, 2]


def _apply_homography(h_mat: np.ndarray, x: float, y: float) -> Point2D:
    vec = h_mat @ np.array([x, y, 1.0], dtype=np.float64)
    if abs(vec[2]) < 1e-12:
        raise ValueError("Point projects to infinity under homography.")
    return Point2D(x=float(vec[0] / vec[2]), y=float(vec[1] / vec[2]))


def _clip_line_outside_rects(
    coord_const: float,
    span_start: float,
    span_end: float,
    is_vertical: bool,
    cutouts: list[OpeningRectMm],
) -> list[tuple[float, float]]:
    """Subtract door/window opening intervals so seam lines never cross glazing or doors."""
    intervals: list[tuple[float, float]] = [(span_start, span_end)]
    for rect in cutouts:
        in_band = (rect.x_min < coord_const < rect.x_max) if is_vertical else (rect.y_min < coord_const < rect.y_max)
        if not in_band:
            continue
        cut_a = rect.y_min if is_vertical else rect.x_min
        cut_b = rect.y_max if is_vertical else rect.x_max
        next_intervals: list[tuple[float, float]] = []
        for s, e in intervals:
            if cut_b <= s or cut_a >= e:
                next_intervals.append((s, e))
            else:
                if s < cut_a:
                    next_intervals.append((s, cut_a))
                if cut_b < e:
                    next_intervals.append((cut_b, e))
        intervals = next_intervals
    return [(round(s, 2), round(e, 2)) for s, e in intervals if e - s > 20.0]


def project_panel_seams(
    image_quad: list[Point2D],
    facade_width_mm: float,
    facade_height_mm: float,
    panel_width_mm: float,
    panel_height_mm: float,
    openings_mm: list[OpeningRectMm] | None = None,
) -> SeamProjectionResult:
    """Project CAD-accurate millimeter panel grids back to perspective pixel coordinates via H^-1."""
    if len(image_quad) != 4:
        raise ValueError("image_quad must contain 4 points: [top-left, top-right, bottom-right, bottom-left].")

    ortho_quad = [
        Point2D(x=0.0, y=0.0),
        Point2D(x=facade_width_mm, y=0.0),
        Point2D(x=facade_width_mm, y=facade_height_mm),
        Point2D(x=0.0, y=facade_height_mm),
    ]
    h_img_to_ortho = compute_homography(image_quad, ortho_quad)
    h_ortho_to_img = np.linalg.inv(h_img_to_ortho)
    h_ortho_to_img = h_ortho_to_img / h_ortho_to_img[2, 2]

    cutouts = openings_mm or []
    seams: list[SeamLine2D] = []

    # Generate internal vertical joint lines (excluding outer perimeter x=0 and x=facade_width_mm).
    x_cursor = panel_width_mm
    cols = 1
    while x_cursor < facade_width_mm - 20.0:
        cols += 1
        for y0, y1 in _clip_line_outside_rects(x_cursor, 0.0, facade_height_mm, True, cutouts):
            seams.append(
                SeamLine2D(
                    orientation="vertical",
                    start=_apply_homography(h_ortho_to_img, x_cursor, y0),
                    end=_apply_homography(h_ortho_to_img, x_cursor, y1),
                )
            )
        x_cursor += panel_width_mm

    # Generate internal horizontal joint courses.
    y_cursor = panel_height_mm
    rows = 1
    while y_cursor < facade_height_mm - 20.0:
        rows += 1
        for x0, x1 in _clip_line_outside_rects(y_cursor, 0.0, facade_width_mm, False, cutouts):
            seams.append(
                SeamLine2D(
                    orientation="horizontal",
                    start=_apply_homography(h_ortho_to_img, x0, y_cursor),
                    end=_apply_homography(h_ortho_to_img, x1, y_cursor),
                )
            )
        y_cursor += panel_height_mm

    # Measure mean deviation of vertical seams from ideal vertical edge angle interpolation.
    left_dx = image_quad[3].x - image_quad[0].x
    left_dy = image_quad[3].y - image_quad[0].y
    ideal_angle = math.degrees(math.atan2(left_dy, left_dx))
    deviations: list[float] = []
    for seg in seams:
        if seg.orientation == "vertical":
            ang = math.degrees(math.atan2(seg.end.y - seg.start.y, seg.end.x - seg.start.x))
            deviations.append(abs(ang - ideal_angle))
    mean_dev = round(sum(deviations) / len(deviations), 4) if deviations else 0.0

    return SeamProjectionResult(
        homography_matrix=[[round(float(v), 6) for v in row] for row in h_img_to_ortho],
        inverse_homography_matrix=[[round(float(v), 6) for v in row] for row in h_ortho_to_img],
        seam_segments=seams,
        vertical_vanishing_deviation_deg=mean_dev,
        panel_count_estimate=cols * rows,
    )
