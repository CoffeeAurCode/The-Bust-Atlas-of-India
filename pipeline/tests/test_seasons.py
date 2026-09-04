import pandas as pd

from pipeline.seasons import SEASONS, season_code_series, season_of, season_series


def test_all_months():
    expected = {
        1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJAS",
        7: "JJAS", 8: "JJAS", 9: "JJAS", 10: "ON", 11: "ON", 12: "DJF",
    }
    for m, s in expected.items():
        assert season_of(f"2022-{m:02d}-15") == s


def test_series_and_codes():
    s = pd.Series(pd.to_datetime(["2022-01-01", "2022-07-01"]))
    assert list(season_series(s)) == ["DJF", "JJAS"]
    assert list(season_code_series(s)) == [SEASONS.index("DJF"), SEASONS.index("JJAS")]
