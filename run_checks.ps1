[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location -LiteralPath $PSScriptRoot

$agentPython = $null
foreach ($candidate in @('python', 'python3', 'py')) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($null -ne $cmd) { $agentPython = $cmd.Source; break }
}
if ($null -eq $agentPython) {
    throw '未找到 Python。请先安装 Python 3.10 或更高版本，并确保 python 在 PATH 中。'
}

& $agentPython -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
