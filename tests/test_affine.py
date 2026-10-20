import unittest
from server.geo.affine import point_bounds, raster_boundary


class AffineTests(unittest.TestCase):
    def test_rotated_raster_encloses_all_four_corners(self):
        points = raster_boundary((0, 1, 1, 0, 1, -1), 100, 100)
        self.assertEqual(point_bounds(points), {"west": 0, "east": 200, "south": -100, "north": 100})
        self.assertEqual(points[0], points[-1])

    def test_negative_pixel_width_and_positive_height(self):
        self.assertEqual(point_bounds(raster_boundary((20, -2, 0, 10, 0, 3), 5, 4)),
                         {"west": 10, "east": 20, "south": 10, "north": 22})

    def test_densification_does_not_change_native_bounds(self):
        transform = (47, 0.01, 0, 43, 0, -0.01)
        coarse = raster_boundary(transform, 100, 100)
        dense = raster_boundary(transform, 100, 100, segments=64)
        self.assertEqual(len(dense), 257)
        self.assertEqual(point_bounds(coarse), point_bounds(dense))

    def test_invalid_georeferencing_is_rejected(self):
        for transform in [(0, 0, 0, 0, 0, 0), (0, float("nan"), 0, 0, 0, 1)]:
            with self.assertRaises(ValueError):
                raster_boundary(transform, 100, 100)
