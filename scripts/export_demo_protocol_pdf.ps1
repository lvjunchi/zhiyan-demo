param([Parameter(Mandatory=$true)][string]$InputPath,[Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference='Stop'
$resolvedInput=(Resolve-Path -LiteralPath $InputPath).Path
$resolvedOutput=[IO.Path]::GetFullPath($OutputPath)
if(Test-Path -LiteralPath $resolvedOutput){throw 'PDF目标已存在；请先核对版本，不覆盖已有文件'}
$word=$null
$document=$null
try {
 $word=New-Object -ComObject Word.Application
 $word.Visible=$false
 $word.DisplayAlerts=0
 $document=$word.Documents.Open($resolvedInput,$false,$true,$false)
 $document.ExportAsFixedFormat($resolvedOutput,17)
 Write-Output "Native Word PDF exported: $resolvedOutput"
} finally {
 if($null -ne $document){$document.Close(0);[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)}
 if($null -ne $word){if($word.Documents.Count -eq 0){$word.Quit()};[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)}
}
