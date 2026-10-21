[System.Reflection.Assembly]::LoadFrom("C:\Program Files\Microsoft Power BI Desktop\bin\Microsoft.PowerBI.AdomdClient.dll") | Out-Null
$conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:60713;")
$conn.Open()
$cmd = $conn.CreateCommand()
$cmd.CommandText = "EVALUATE ROW(
    `"OptionPredictions Total`", COUNTROWS(OptionPredictions),
    `"OptionPredictions Valid Prob`", COUNTROWS(FILTER(OptionPredictions, OptionPredictions[probability_valid] = TRUE())),
    `"ForensicLive Total`", COUNTROWS(ForensicLive),
    `"ForensicLive Valid CE`", COUNTROWS(FILTER(ForensicLive, ForensicLive[ce_valid] = TRUE())),
    `"ForensicLive Valid PE`", COUNTROWS(FILTER(ForensicLive, ForensicLive[pe_valid] = TRUE())),
    `"ForensicLive Actionable CE`", COUNTROWS(FILTER(ForensicLive, ForensicLive[ce_valid] = TRUE() && ForensicLive[ce_ltp] >= 20 && ForensicLive[ce_oi] >= 100000 && NOT(CONTAINSSTRING(UPPER(ForensicLive[forensic_signal]), `"ILLIQUID`")) && NOT(CONTAINSSTRING(UPPER(ForensicLive[forensic_signal]), `"AVOID`")))),
    `"ForensicLive Actionable PE`", COUNTROWS(FILTER(ForensicLive, ForensicLive[pe_valid] = TRUE() && ForensicLive[pe_ltp] >= 20 && ForensicLive[pe_oi] >= 100000 && NOT(CONTAINSSTRING(UPPER(ForensicLive[forensic_signal]), `"ILLIQUID`")) && NOT(CONTAINSSTRING(UPPER(ForensicLive[forensic_signal]), `"AVOID`")))),
    `"PaperLog Total`", COUNTROWS(PaperLog),
    `"CERank Total`", COUNTROWS(CERank),
    `"Heartbeat Total`", COUNTROWS(Heartbeat)
)"
$adapter = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdDataAdapter($cmd)
$ds = New-Object System.Data.DataSet
$adapter.Fill($ds) | Out-Null
$conn.Close()
$ds.Tables[0] | Format-List
