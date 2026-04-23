$lib = (Resolve-Path "$PSScriptRoot/../../..").Path
Push-Location $lib
py -m pytest acai/logging/_test/ -v
Pop-Location
