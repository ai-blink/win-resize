# 설치와 실행

## 요구 사항

- Windows 10 또는 11, 64비트
- 릴리스 실행 파일(`WindowResizer.exe`)에는 .NET 런타임이 들어 있어 따로 설치할 것이 없습니다.
- 소스에서 빌드하려면 .NET 10 SDK가 필요합니다.

## 릴리스 실행

1. GitHub 릴리스에서 `WindowResizer.exe`를 내려받습니다.
2. 원하는 폴더에 두고 실행합니다. 처음 실행은 내부 라이브러리를 임시 폴더에 푸느라 몇 초 걸릴 수 있습니다.
3. 프로필은 실행 파일 옆 `profiles` 폴더(`profiles.json`)에서 읽고 씁니다. 이전 PyQt5 앱(v0.01.5)의 프로필
   폴더를 그대로 쓰려면 아래 `--profiles-dir`로 그 폴더를 지정하세요. **쓰기도 하므로, 먼저 폴더를 복사해 두는 것을
   권합니다.**
4. 설정(테마, 화면 배율, 언어, 오버레이 버튼, 전체 적용 단축키)은 `HKCU\Software\WindowResizer\Next` 아래에 저장됩니다.
   처음 실행할 때 이전 PyQt5 앱의 테마와 화면 배율, 오버레이 사용 프로필을 한 번 가져옵니다.

이전 PyQt5 앱과 같은 Windows 세션에서 동시에 실행할 수 없습니다(같은 중복 실행 방지를 씁니다).

## 실행 인자

| 인자 | 뜻 |
|---|---|
| `--profiles-dir <폴더>` | 프로필 폴더를 바꿉니다. |
| `--minimized` | 창 없이 트레이로만 뜹니다(Windows 시작 때 자동 실행이 붙이는 인자). |
| `--overlay-key`, `--hotkey-key`, `--settings-key`, `--run-key <HKCU 아래 경로>` | 설정 레지스트리 키를 바꿉니다(검증용). |
| `--instance-key <이름>` | 중복 실행 방지 이름을 바꿉니다(검증용). |

## 소스에서 빌드

```powershell
dotnet build next\WindowResizer.slnx
dotnet test next\WindowResizer.slnx
powershell -NoProfile -File next\tools\publish.ps1
```

마지막 명령은 자체 완결형 단일 파일 실행 파일을 `next\publish\win-x64\WindowResizer.App.exe`에 만듭니다.
`publish/`, `bin/`, `obj/`는 생성물이며 소스 제어에 포함하지 않습니다. 실행 중인 앱이 `bin/`을 잠그므로 빌드 전에
앱을 종료하세요(트레이에 숨은 앱 포함).

## 권한 관련 참고

관리자 권한으로 실행 중인 대상 창은 일반 권한 앱이 조작하지 못합니다. 그런 창에 프로필을 적용하거나 잠금을 걸어야
하면 WindowResizer도 관리자 권한으로 실행하세요.

## 이전 PyQt5 앱

`src/`, `run_gui.py`, `final_build.py`는 이전 PyQt5 앱(v0.01.5)입니다. 참고용으로 남겨 두었고, 필요하면 태그
`last-pyqt5-stable`에서 그대로 실행할 수 있습니다.
