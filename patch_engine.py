import re

with open('angel_prediction_engine.py', 'r') as f:
    content = f.read()

# Replace the HEARTBEAT update section
old_hb = """        # 2. Update HEARTBEAT with exact 6-column schema
        ws_hb = sh.worksheet("HEARTBEAT")
        hb_rows = [
            ["Last Ping (IST)", "Angel Session Status", "Auto-Discovered Symbols", "Engine Status", "Seconds Since Last Write", "Automated Feed Alert"],
            [ist_str, "CONNECTED_ANGEL_SMARTAPI", len(predictions), f"ACTIVE_PREDICTION_ENGINE | Cycle #{reconciliation['cycle']}", 0, "🟢 HEALTHY (ALL FEEDS ACTIVE)"],
            ["Metric", "Value", "Benchmark", "Component", "Protocol", "Status"],
            ["Session Auth", "CONNECTED_ANGEL_SMARTAPI", "ACTIVE", "Angel One SmartAPI", "TOTP / JWT WebSocket", "🟢 HEALTHY"],
            ["Writer age", '=IF(ISNUMBER(E2),E2&"s","0s")', "Clock age, not exchange age", "Sheet write timestamp", "Daemon loop", "🟢 HEALTHY (ALL FEEDS ACTIVE)"],
            ["Self-Calibration Hit Rate", f"{reconciliation['hit_rate_pct']}%", "Self-Calibration Loop", "Reconciliation Engine", "Ground Truth Compare", "🟢 CALIBRATED"],
            ["Recall @ 10", f"{reconciliation['recall_at_10']}", "Top 10 Prediction Match", "Self-Calibration Loop", "Online Weights", "🟢 ACTIVE"],
            ["Mean Rank", f"{reconciliation['mean_rank']}", "Actual Movers Rank", "Greeks & News Model", "Dynamic Calibration", "🟢 HIGH ACCURACY"]
        ]
        ws_hb.clear()
        ws_hb.update(range_name="A1:F8", values=hb_rows, value_input_option="USER_ENTERED")"""

new_hb = """        # 2. Update HEARTBEAT with engine metrics, without destroying telemetry
        ws_hb = sh.worksheet("HEARTBEAT")
        hb_rows = [
            ["Metric", "Value", "Benchmark", "Component", "Protocol", "Status"],
            ["Session Auth", "CONNECTED_ANGEL_SMARTAPI", "ACTIVE", "Angel One SmartAPI", "TOTP / JWT WebSocket", "🟢 HEALTHY"],
            ["Self-Calibration Hit Rate", f"{reconciliation['hit_rate_pct']}%", "Self-Calibration Loop", "Reconciliation Engine", "Ground Truth Compare", "🟢 CALIBRATED"],
            ["Recall @ 10", f"{reconciliation['recall_at_10']}", "Top 10 Prediction Match", "Self-Calibration Loop", "Online Weights", "🟢 ACTIVE"],
            ["Mean Rank", f"{reconciliation['mean_rank']}", "Actual Movers Rank", "Greeks & News Model", "Dynamic Calibration", "🟢 HIGH ACCURACY"]
        ]
        # Update metrics starting at row 5
        ws_hb.update(range_name="A5:F9", values=hb_rows, value_input_option="USER_ENTERED")
        
        # Also dynamically update Last BigQuery Sync
        headers = ws_hb.row_values(1)
        if "Last BigQuery Sync (IST)" in headers:
            col_idx = headers.index("Last BigQuery Sync (IST)")
            col_letter = chr(65 + col_idx)
            ws_hb.update(range_name=f"{col_letter}2", values=[[ist_str]])
"""
content = content.replace(old_hb, new_hb)

with open('angel_prediction_engine.py', 'w') as f:
    f.write(content)

