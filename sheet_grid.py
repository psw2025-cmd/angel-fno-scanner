"""Replace a worksheet without a destructive pre-clear or out-of-grid cleanup."""
from gspread.utils import rowcol_to_a1


def write_grid(ws, rows):
    if not rows:
        raise ValueError("Refusing to replace a worksheet with empty output")
    width = max(len(row) for row in rows)
    if width < 1:
        raise ValueError("Worksheet output has no columns")
    normalized = [list(row) + [""] * (width - len(row)) for row in rows]
    row_limit, col_limit = int(ws.row_count), int(ws.col_count)
    if len(rows) > row_limit or width > col_limit:
        row_limit, col_limit = max(row_limit, len(rows)), max(col_limit, width)
        ws.resize(rows=row_limit, cols=col_limit)
    ws.update(range_name="A1", values=normalized, value_input_option="RAW")
    cleanup = []
    if len(rows) < row_limit:
        cleanup.append(f"A{len(rows) + 1}:{rowcol_to_a1(row_limit, col_limit)}")
    if width < col_limit:
        cleanup.append(f"{rowcol_to_a1(1, width + 1)}:{rowcol_to_a1(len(rows), col_limit)}")
    if cleanup:
        # Cleanup is part of success: stale rows/columns must not survive silently.
        ws.batch_clear(cleanup)
