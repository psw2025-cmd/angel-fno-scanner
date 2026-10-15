"""Offline-only fixture contract. Never import cloud SDKs here."""
PAPER_MODE = 1
LIVE_ORDER_AUTHORITY = 0
PRODUCTION_TARGET_DENYLIST = ("fno-angel-prod-1790444589", "1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs", "angel-market-scan-job", "option_predictions_live")
def assert_safe(target="", *, paper_mode=PAPER_MODE, live_order_authority=LIVE_ORDER_AUTHORITY):
    if paper_mode != 1 or live_order_authority != 0:
        raise RuntimeError("unsafe trading configuration")
    if any(blocked in str(target) for blocked in PRODUCTION_TARGET_DENYLIST):
        raise RuntimeError("production target denied")
    return True
