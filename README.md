# Angel F&O scanner

The scanner reads NSE F&O quotes from Angel One SmartAPI and writes them to the OPTION_SHEET workbook.

`Sheet1` and `TOP_GAINERS` list contracts ranked by the Angel change percent. Previous close, net change, volume, and open interest come from the quote. When the quote has no previous close, the previous close is implied from the Angel LTP and the Angel change percent and the basis column says so. Black-76 IV, delta, and theta are inverted from that premium at a 6.5% discount rate. A missing quote field stays blank.

`HIGH MOMENTUM` is written only while the NSE session is open, the premium is at least ₹2, volume is at least 100,000, open interest is at least 5,000, the spread is at most 12% of premium, and the Angel change is at least 25%. A closed session is labeled `MARKET CLOSED`.

`PRODUCTION_APPROVED` counts `PAPER_ALERT_LOG` rows that already have a later session change. It does not create trades. New alerts are appended only during 09:15–15:30 IST on weekdays.

If `HEARTBEAT` was written in the last 90 seconds, the job does not open a second Angel session. It rebuilds the gainers board from `FORENSIC_LIVE`. Volume is blank on that path because that feed does not carry it, so those rows are not marked high momentum.
