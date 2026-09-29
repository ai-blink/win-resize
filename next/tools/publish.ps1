# WindowResizer.App 을 self-contained 단일 파일 exe 로 게시한다(D-029).
# 산출물은 next\publish\win-x64 에 만들어지고 git 이 무시한다. 실사용 exe(C:\app\WindowResizer.exe)는 건드리지 않는다 -
# 교체는 사용자 승인 뒤에만 한다.
#
# 사용:  powershell -NoProfile -File next\tools\publish.ps1 [-Output <폴더>]
param([string]$Output = (Join-Path $PSScriptRoot '..\publish\win-x64'))

$ErrorActionPreference = 'Stop'
$project = Join-Path $PSScriptRoot '..\src\WindowResizer.App\WindowResizer.App.csproj'

# 실행 중이거나 트레이에 숨은 앱은 bin 을 잠가 게시가 옛 파일을 쓰게 만든다.
$running = Get-Process WindowResizer.App -ErrorAction SilentlyContinue
if ($running) { throw 'WindowResizer.App 이 실행 중이다. 종료한 뒤 다시 실행하라.' }

# 런타임을 exe 에 넣는다(.NET 이 없는 PC 에서도 뜬다). 네이티브 DLL 도 exe 안에 넣고 처음 실행 때 풀어 쓴다.
# 압축을 켜면 크기가 크게 줄고 첫 실행이 조금 느리다.
dotnet publish $project -c Release -r win-x64 --self-contained true `
    -p:PublishSingleFile=true `
    -p:IncludeNativeLibrariesForSelfExtract=true `
    -p:EnableCompressionInSingleFile=true `
    -p:DebugType=none -p:DebugSymbols=false `
    -o $Output
if ($LASTEXITCODE -ne 0) { throw "dotnet publish 실패 ($LASTEXITCODE)" }

$exe = Join-Path $Output 'WindowResizer.App.exe'
$item = Get-Item $exe
'{0}  {1:N1} MB  version {2}' -f $item.FullName, ($item.Length / 1MB), $item.VersionInfo.ProductVersion
