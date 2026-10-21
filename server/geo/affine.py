"""Affine raster boundaries, including rotation and shear."""
import math


def raster_boundary(transform, width, height, segments=1):
    if len(transform) != 6 or not all(math.isfinite(v) for v in transform):
        raise ValueError("Raster must have a finite, six-element affine transform")
    if width <= 0 or height <= 0 or segments < 1:
        raise ValueError("Raster dimensions and segment count must be positive")
    if transform[1] * transform[5] - transform[2] * transform[4] == 0:
        raise ValueError("Raster affine transform is singular")
    corners = [(0, 0), (width, 0), (width, height), (0, height), (0, 0)]
    points = []
    for start, end in zip(corners, corners[1:]):
        for step in range(segments):
            fraction = step / segments
            col = start[0] + (end[0] - start[0]) * fraction
            row = start[1] + (end[1] - start[1]) * fraction
            points.append((transform[0] + col * transform[1] + row * transform[2],
                           transform[3] + col * transform[4] + row * transform[5]))
    points.append(points[0])
    return points


def point_bounds(points):
    xs, ys = zip(*points)
    return {"west": min(xs), "south": min(ys), "east": max(xs), "north": max(ys)}
