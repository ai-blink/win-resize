# WindowResizer

[English](README.md) | [한국어](README.ko.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md)

WindowResizer는 실행 중인 Windows 창을 찾고, 위치 또는 크기를 조절하며, 저장한 창
프로필을 반복 적용할 수 있는 Windows 데스크톱 애플리케이션입니다.

현재 릴리스: 0.02.0 (.NET 10 WPF로 새로 작성, 이전 PyQt5 앱은 v0.01.5)

## 주요 기능

- 실행 중인 창을 검색해 보고, 프로필을 맞는 창 전부에 한 번에 적용합니다(버튼, 메뉴, Enter, 전역 단축키).
- 창의 위치와 크기를 프로필로 저장(Ctrl+S)하고, 창에서 프로필 위치를 덮어쓰고(되돌리기 가능), 사이드바
  편집 창에서 프로필을 고칩니다.
- 실행 파일 전체 경로, 프로세스 이름, 창 제목(포함, 일치, 정규식), 또는 이들의 결합으로 프로필을 매칭해
  파일명이 같은 앱도 구분합니다.
- 프로필 위치 잠금: 옮겨진 창을 적용했던 자리로 되돌립니다.
- 프로필 창이 앞에 있는 동안 마우스를 그 창 안에 가둡니다(탈출 키 지원).
- 앱을 켠 뒤에 새로 뜬 창에 맞는 프로필을 자동으로 적용합니다.
- 오버레이 버튼: 각자 자기 창 위치·크기를 저장한 떠 있는 버튼으로, 누르면 직전에 쓰던 창을 그 자리로
  옮깁니다. 속성 창(실제 크기 미리보기)에서 직전 창이나 화면에서 직접 고른 창의 자리를 가져올 수 있습니다.
- 프로필별 전역 단축키(여러 조합, 여러 동작), 전체 적용 단축키, 항상 위 전환.
- 밝게·어둡게·시스템 따르기 테마(Windows 고대비 지원), 75%~250% 앱 배율, 한국어·영어 표시, Windows 시작 때 자동 실행, 로그 페이지.
- 메인 창을 닫으면 트레이에 남고, 같은 Windows 세션에서 한 벌만 실행됩니다(두 번째 실행은 첫 앱의 창을
  앞으로 냅니다).

## 0.02.0에 아직 없는 것

- PyQt5가 3초 동안 보여 주던 프로필 미리보기 테두리.
- 앱 표시 언어의 중국어·일본어(한국어와 영어만 있습니다. 문서는 4개 언어입니다).
- 설치 프로그램과 업데이트 방식. 릴리스는 자체 완결형 실행 파일 하나입니다.

## 요구 사항

- Windows 10 또는 Windows 11, 64비트. 릴리스 실행 파일에 .NET 런타임이 들어 있어 따로 설치할 것이
  없습니다.

관리자 권한으로 실행 중인 대상 창은 일반 권한의 WindowResizer에서 조작하지 못합니다. 필요한 경우
WindowResizer도 같은 권한 수준으로 실행하세요.

## 릴리스 실행

GitHub 릴리스에서 `WindowResizer.exe`를 내려받아 실행합니다. 프로필은 실행 파일 옆 `profiles` 폴더에서
읽고 쓰며, 설정은 `HKCU\Software\WindowResizer\Next` 아래에 저장됩니다. 자세한 내용은
[설치와 실행 안내](docs/INSTALLATION.md)를 보세요.

## 소스에서 빌드

~~~powershell
dotnet build next\WindowResizer.slnx
dotnet test next\WindowResizer.slnx
powershell -NoProfile -File next\tools\publish.ps1
~~~

마지막 명령은 단일 파일 실행 파일을 `next\publish\win-x64\`에 만듭니다. 빌드에는 .NET 10 SDK가
필요합니다.

## 문서

설치와 사용 문서는 한국어이며, 릴리스 노트와 변경 기록은 영어·한국어·중국어 간체·일본어로 제공됩니다.

- [설치와 실행 안내](docs/INSTALLATION.md)
- [사용 안내](docs/USER_GUIDE.md)
- [변경 기록: English](docs/CHANGELOG.md) | [한국어](docs/CHANGELOG.ko.md) |
  [中文](docs/CHANGELOG.zh-CN.md) | [日本語](docs/CHANGELOG.ja.md)
- 릴리스 노트: `doc/releases/`

## 저장소 구성

- next/: WPF 애플리케이션(src/ 앱, tests/, tools/ 게시 스크립트)
- doc/, docs/: 릴리스 노트, 변경 기록, 사용자 문서
- rules/: 개발 메모와 결정 기록
- src/, run_gui.py, final_build.py, tests/: 이전 PyQt5 애플리케이션(v0.01.5, 태그 `last-pyqt5-stable`), 참고용으로 남김
