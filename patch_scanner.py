import re

with open('scanner.py', 'r') as f:
    content = f.read()

old_block = """                heartbeat = worksheet(book, "HEARTBEAT")
                heartbeat.update(
                    range_name="A2",
                    values=[[stamped, "CONNECTED_ANGEL_SMARTAPI", len(forensic_rows), f"Loop #{loop} OK | {len(chain_quotes)} option quotes"]],
                    value_input_option="RAW",
                )"""

new_block = """                heartbeat = worksheet(book, "HEARTBEAT")
                telemetry_header = [
                    "Last Data Fetch (IST)", 
                    "Angel Broker Connection Status", 
                    "Last BigQuery Sync (IST)", 
                    "Stream Health", 
                    "Outage Start (IST)", 
                    "Outage End (IST)", 
                    "Outage Duration (s)", 
                    "Data Missed Estimate (Rows)"
                ]
                
                try:
                    existing_header = heartbeat.row_values(1)
                except Exception:
                    existing_header = []
                    
                if existing_header != telemetry_header:
                    heartbeat.update(range_name="A1", values=[telemetry_header], value_input_option="RAW")
                    existing_header = telemetry_header
                
                try:
                    last_fetch_str = heartbeat.acell("A2").value
                except Exception:
                    last_fetch_str = None
                
                outage_start = ""
                outage_end = ""
                outage_duration = ""
                data_missed = ""
                
                if last_fetch_str:
                    try:
                        last_time = datetime.datetime.strptime(str(last_fetch_str).strip(), "%Y-%m-%d %H:%M:%S")
                        gap = (now - last_time).total_seconds()
                        if gap > 300 and market_is_open(last_time) and market_is_open(now):
                            outage_start = str(last_time.strftime("%Y-%m-%d %H:%M:%S"))
                            outage_end = stamped
                            outage_duration = str(int(gap))
                            data_missed = str(int(gap / 30) * max(1, len(forensic_rows)))
                    except Exception:
                        pass
                
                row_data = {
                    "Last Data Fetch (IST)": stamped,
                    "Angel Broker Connection Status": "CONNECTED_ANGEL_SMARTAPI",
                    "Stream Health": "🟢 HEALTHY" if not outage_duration else "🔴 OUTAGE RECOVERED",
                }
                
                if outage_duration:
                    row_data["Outage Start (IST)"] = outage_start
                    row_data["Outage End (IST)"] = outage_end
                    row_data["Outage Duration (s)"] = outage_duration
                    row_data["Data Missed Estimate (Rows)"] = data_missed
                
                try:
                    current_row = heartbeat.row_values(2)
                except Exception:
                    current_row = []
                    
                current_row = (current_row + [""] * len(telemetry_header))[:len(telemetry_header)]
                
                for i, col in enumerate(telemetry_header):
                    if col in row_data:
                        current_row[i] = row_data[col]
                        
                heartbeat.update(range_name="A2", values=[current_row], value_input_option="RAW")"""

if old_block in content:
    content = content.replace(old_block, new_block)
    with open('scanner.py', 'w') as f:
        f.write(content)
    print("Patched scanner.py successfully")
else:
    print("Could not find the block to patch in scanner.py")

