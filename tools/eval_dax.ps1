[System.Reflection.Assembly]::LoadFrom("C:\Program Files\Microsoft Power BI Desktop\bin\Microsoft.PowerBI.AdomdClient.dll") | Out-Null
$conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:60713;")
$conn.Open()
$cmd = $conn.CreateCommand()
$cmd.CommandText = "EVALUATE ROW(
    `"Universe Health`", [Universe Health],
    `"Live Symbols`", [Live Symbols],
    `"Top Gap Up`", [Top Gap Up Display Safe],
    `"Top Gap Down`", [Top Gap Down Display Safe],
    `"Top Actionable CE`", [Top Actionable CE Display],
    `"Top Actionable PE`", [Top Actionable PE Display],
    `"Top Raw CE`", [Top Raw CE Display],
    `"Top Raw PE`", [Top Raw PE Display],
    `"Largest Expected Gap Up`", [Largest Expected Gap Up %],
    `"Largest Expected Gap Down`", [Largest Expected Gap Down %],
    `"Average Confidence`", [Average Confidence %],
    `"Average PCR`", [Average PCR]
)"
$adapter = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdDataAdapter($cmd)
$ds = New-Object System.Data.DataSet
$adapter.Fill($ds) | Out-Null
$conn.Close()
$ds.Tables[0] | Format-List
