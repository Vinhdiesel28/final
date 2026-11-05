param([switch]$ProjectOnly, [switch]$FinalOnly)
$ErrorActionPreference = 'Stop'
$reportDir = (Resolve-Path (Join-Path $PSScriptRoot '..\report')).Path
$inputs = @(
    (Join-Path $reportDir 'tieuluan_final_CT_08_934_NguyenMinhVinh.docx'),
    (Join-Path $reportDir 'project01_CT_08_934_NguyenMinhVinh.docx')
)
if ($ProjectOnly) {
    $inputs = @((Join-Path $reportDir 'project01_CT_08_934_NguyenMinhVinh.docx'))
}
if ($FinalOnly) {
    $inputs = @((Join-Path $reportDir 'tieuluan_final_CT_08_934_NguyenMinhVinh.docx'))
}
$word = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    foreach ($inputPath in $inputs) {
        if (-not (Test-Path -LiteralPath $inputPath)) { throw "Missing input: $inputPath" }
        $pdfPath = [System.IO.Path]::ChangeExtension($inputPath, '.pdf')
        $doc = $word.Documents.Open($inputPath, $false, $false)
        try {
            $doc.Fields.Update() | Out-Null
            foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
            $doc.Save()
            $doc.ExportAsFixedFormat($pdfPath, 17)
        }
        finally { $doc.Close($false) }
        Write-Output $pdfPath
    }
}
finally {
    if ($null -ne $word) { $word.Quit() }
}
