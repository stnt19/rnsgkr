param([Parameter(Mandatory=$true)][string]$Batch)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime]
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1
function Await($Operation, [Type]$ResultType) {
    $task = $asTask.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.GetAwaiter().GetResult()
}
$language = New-Object Windows.Globalization.Language('ko')
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
if ($null -eq $engine) { throw 'Windows Korean OCR language pack is required.' }
$jobs = Get-Content -LiteralPath $Batch -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($job in $jobs) {
    $stream = $null; $bitmap = $null
    try {
        $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($job.image)) ([Windows.Storage.StorageFile])
        $stream = Await ($file.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        $lines = @($result.Lines | ForEach-Object {
            @{ text=$_.Text; words=@($_.Words | ForEach-Object {
                @{ text=$_.Text; x=$_.BoundingRect.X; y=$_.BoundingRect.Y;
                   width=$_.BoundingRect.Width; height=$_.BoundingRect.Height }
            }) }
        })
        $output = @{ page=$job.page; text=($lines.text -join "`n"); lines=$lines;
                     width=$bitmap.PixelWidth; height=$bitmap.PixelHeight;
                     engine='Windows.Media.Ocr'; language='ko'; textAngle=$result.TextAngle }
        [IO.File]::WriteAllText($job.output, ($output | ConvertTo-Json -Depth 8 -Compress), (New-Object Text.UTF8Encoding($false)))
        Write-Output "OCR page $($job.page)"
    } finally {
        if ($null -ne $bitmap) { $bitmap.Dispose() }
        if ($null -ne $stream) { $stream.Dispose() }
    }
}
