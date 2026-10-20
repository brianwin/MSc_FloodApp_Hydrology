import pandas as pd
import pytest

from app.floodreadings.services.hydrology_readings import (
    compare_hydrology_source_frames,
)


MEASURE_A = "http://environment.data.gov.uk/hydrology/id/measures/A-level-i-900-m-qualified"
MEASURE_B = "http://environment.data.gov.uk/hydrology/id/measures/B-level-i-900-m-qualified"
MEASURE_C = "http://environment.data.gov.uk/hydrology/id/measures/C-level-i-900-m-qualified"
MEASURE_D = "http://environment.data.gov.uk/hydrology/id/measures/D-level-i-900-m-qualified"


def _row(measure, date_time, value, quality="Good"):
    return {
        "measure": measure,
        "dateTime": date_time,
        "date": "2026-07-20",
        "value": value,
        "completeness": "",
        "quality": quality,
        "qcode": "",
        "valid": "",
        "invalid": "",
        "missing": "",
    }


def test_source_delta_detects_added_changed_and_deleted_rows():
    previous = pd.DataFrame([
        _row(MEASURE_A, "2026-07-20T00:00:00", "1.000"),
        _row(MEASURE_B, "2026-07-20T00:15:00", "2.000"),
        _row(MEASURE_C, "2026-07-20T00:30:00", "3.000"),
    ])
    new = pd.DataFrame([
        _row(MEASURE_A, "2026-07-20T00:00:00", "1.000"),
        _row(MEASURE_B, "2026-07-20T00:15:00", "2.100"),
        _row(MEASURE_D, "2026-07-20T00:45:00", "4.000"),
    ])

    delta = compare_hydrology_source_frames(previous, new)

    assert delta["previous_row_count"] == 3
    assert delta["new_row_count"] == 3
    assert delta["added"] == 1
    assert delta["changed"] == 1
    assert delta["deleted"] == 1
    assert set(delta["delta_df"]["measure"]) == {MEASURE_B, MEASURE_D}
    assert delta["deleted_keys"] == [
        (MEASURE_C, "2026-07-20T00:30:00")
    ]


def test_source_delta_treats_null_and_empty_optional_values_as_equal():
    previous = pd.DataFrame([
        _row(MEASURE_A, "2026-07-20T00:00:00", "1.000"),
    ])
    new = previous.copy()
    previous.loc[0, "qcode"] = None
    new.loc[0, "qcode"] = ""

    delta = compare_hydrology_source_frames(previous, new)

    assert delta["changed"] == 0


def test_source_delta_rejects_duplicate_source_keys():
    duplicated = pd.DataFrame([
        _row(MEASURE_A, "2026-07-20T00:00:00", "1.000"),
        _row(MEASURE_A, "2026-07-20T00:00:00", "1.100"),
    ])

    with pytest.raises(ValueError, match="duplicate keys"):
        compare_hydrology_source_frames(duplicated, duplicated)
