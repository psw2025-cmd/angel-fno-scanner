import pytest

import publication


def test_equal_matrices_have_no_diff():
    a = [["x", 1, 2.50], ["y"]]
    b = [["x", "1", "2.5"], ["y", ""]]
    assert publication.first_diff(a, b) is None
    assert publication.matrix_hash(a) == publication.matrix_hash(b)


def test_first_diff_reports_row_col_and_values():
    exp = [["a", "b"], ["c", "=====", "z"]]
    act = [["a", "b"], ["c", "#ERROR!", "z"]]
    assert publication.first_diff(exp, act) == (2, 2, "=====", "#ERROR!")


def test_first_diff_reports_row_count_mismatch():
    assert publication.first_diff([["a"], ["b"]], [["a"]]) == (2, 0, "2 rows", "1 rows")


def test_verify_outputs_error_names_cell(monkeypatch):
    rows_actual = [["h"], ["v", "BAD"]]

    class WS:
        def get_all_values(self, **kw):
            return rows_actual

    class SH:
        def worksheet(self, title):
            return WS()

    monkeypatch.setattr(publication, "require_verified_symbols", lambda s: None)
    monkeypatch.setattr(publication, "sheet_symbols", lambda t, r: [])
    expected = {t: [["h"], ["v", "GOOD"]] for t in publication.REQUIRED_TABS}
    with pytest.raises(RuntimeError) as ei:
        publication.verify_outputs(SH(), None, None, {}, expected)
    msg = str(ei.value)
    assert "first difference" in msg and "GOOD" in msg and "BAD" in msg
