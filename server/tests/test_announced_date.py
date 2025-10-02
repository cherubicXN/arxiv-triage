from server.routers.papers import _announced_date


def test_announced_date_weekdays_boundaries():
    # Times are UTC; comparisons use ET cutoff at 14:00
    cases = [
        ("2024-09-16T17:59:00+00:00", "2024-09-16"),  # Mon 13:59 ET -> Mon
        ("2024-09-16T18:00:00+00:00", "2024-09-17"),  # Mon 14:00 ET -> Tue
        ("2024-09-17T17:59:00+00:00", "2024-09-17"),  # Tue 13:59 ET -> Tue
        ("2024-09-17T18:00:00+00:00", "2024-09-18"),  # Tue 14:00 ET -> Wed
        ("2024-09-18T17:59:00+00:00", "2024-09-18"),  # Wed 13:59 ET -> Wed
        ("2024-09-18T18:00:00+00:00", "2024-09-19"),  # Wed 14:00 ET -> Thu
        ("2024-09-19T17:59:00+00:00", "2024-09-19"),  # Thu 13:59 ET -> Thu
        ("2024-09-19T18:00:00+00:00", "2024-09-22"),  # Thu 14:00 ET -> Sun
        ("2024-09-20T17:59:00+00:00", "2024-09-22"),  # Fri 13:59 ET -> Sun
        ("2024-09-20T18:00:00+00:00", "2024-09-23"),  # Fri 14:00 ET -> Mon
        ("2024-09-21T14:00:00+00:00", "2024-09-23"),  # Sat -> Mon
        ("2024-09-22T14:00:00+00:00", "2024-09-23"),  # Sun -> Mon
    ]
    for submitted, expected in cases:
        assert _announced_date(submitted) == expected

