$ErrorActionPreference = 'Stop'
$dir = (Resolve-Path (Join-Path $PSScriptRoot '..\report')).Path
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    foreach ($name in @('project01_CT_08_934_NguyenMinhVinh_cap_nhat','tieuluan_final_CT_08_934_NguyenMinhVinh_cap_nhat')) {
        $doc = $word.Documents.Open((Join-Path $dir "$name.docx"), $false, $true)
        try { $doc.ExportAsFixedFormat((Join-Path $dir "$name.pdf"), 17) }
        finally { $doc.Close($false) }
    }
} finally { $word.Quit() }
