"""Point values retain half-points throughout recycling and spending."""

MAX_POINTS = 9007199254740991


def valid_points(value):
    return (type(value) in (int, float) and 0 <= value <= MAX_POINTS
            and value % 0.5 == 0)


def read_points(value):
    if not valid_points(value):
        raise ValueError("Invalid points balance.")
    return value
