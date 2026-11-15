"""Ground geometry helpers for the sample project."""


def slant_range_m(height_m: float, pitch_rad: float) -> float:
    """Return the camera-to-ground distance along the optical axis.

    Args:
        height_m: Camera height above the ground, in meters.
        pitch_rad: Downward pitch from horizontal, in radians.

    Returns:
        Slant range in meters.
    """
    import math

    return height_m / math.sin(pitch_rad)


def _helper(x: int) -> int:
    return x
