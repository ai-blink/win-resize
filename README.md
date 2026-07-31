# win-resize

Windows 창의 위치와 크기를 관리하는 PyQt 데스크톱 앱입니다.

버전 0.01 최초 릴리스입니다.

## 주요 기능

- 실행 중인 창 선택, 이동, 크기 조절
- 창별 위치와 크기를 저장하고 다시 적용하는 프로필
- 실행 파일 전체 경로를 이용한 안정적인 프로필 매칭
- 적용 전에 배치를 확인하는 프로필 미리보기
- 조건에 일치하는 새 창의 선택형 자동 적용
- 프로필별 창 위치 고정과 마우스 커서 제한
- 라이트, 다크, 고대비 테마
- 닫기 버튼으로 시스템 트레이에 숨김, 별도 `프로그램 종료` 버튼으로 완전 종료

## 요구 사항

- Windows 10 또는 11
- Python 3.12

## 개발 실행

```powershell
C:\Python312\python.exe -m pip install -r requirements.txt
C:\Python312\python.exe run_gui.py
```

## 실행 파일 빌드

```powershell
C:\Python312\python.exe final_build.py
```

빌드가 끝나면 `dist/WindowResizer.exe`가 생성됩니다.

## 테스트

```powershell
C:\Python312\python.exe test_close_to_tray.py
C:\Python312\python.exe test_profile_deletion.py
C:\Python312\python.exe test_profile_preview_and_auto_apply.py
C:\Python312\python.exe test_profile_editor_lock_settings.py
```

## 문서

- [설치와 실행](docs/INSTALLATION.md)
- [사용 안내](docs/USER_GUIDE.md)
- [변경 기록](docs/CHANGELOG.md)

## 저장소 구성

- `src/`: 애플리케이션 소스
- `run_gui.py`: 개발 실행 진입점
- `final_build.py`: PyInstaller 빌드 스크립트
- `requirements.txt`: Python 의존성
- `docs/`: 공개 사용 문서
