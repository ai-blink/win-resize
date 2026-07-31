# 설치와 실행

## 요구 사항

- Windows 10 또는 11
- Python 3.12 개발 환경 또는 준비된 실행 파일
- 프로젝트 의존성 설치: `C:\Python312\python.exe -m pip install -r requirements.txt`

## 개발 실행

프로젝트 루트에서 실행합니다.

```powershell
C:\Python312\python.exe run_gui.py
```

기본 `python` 명령이 다른 Python을 가리킬 수 있으므로, 이 저장소에서는 검증된
Python 3.12 경로를 우선 사용합니다.

## 실행 파일 빌드

```powershell
C:\Python312\python.exe final_build.py
```

성공하면 `dist/WindowResizer.exe`가 생성됩니다. `dist/`와 `build/`는 생성물이며
소스 제어에 포함하지 않습니다.

## 권한 관련 참고

관리자 권한으로 실행 중인 대상 창은 일반 권한 앱이 조작하지 못할 수 있습니다.
그 경우 WindowResizer도 같은 수준의 권한으로 실행해야 합니다.
