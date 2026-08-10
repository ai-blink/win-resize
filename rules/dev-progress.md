# Development Progress

## Current

- 2026-08-11: 전체 UI 확대/축소를 추가했다. 기본 배율은 90%이며, 보기 메뉴의 슬라이더에서 75%~125%를 5% 단위로 즉시 변경하고 다음 실행에도 복원한다. 메인 창의 마지막 크기와 위치도 별도 저장해, 화면 구성 변경 뒤에도 현재 화면 안에서 다음 실행에 복원한다. UI 배율 변경은 사용자가 조정한 창 크기를 기본값으로 덮어쓰지 않는다. 전용 7건, 전체 47건 테스트와 공식 EXE 재빌드 및 기동을 확인했다.
- 2026-08-11: 프로필의 실시간 위치/크기 유지 토글이 켜진 활성 프로필이 있으면, 앱 시작과 프로필 저장·수정 뒤 새 창 감시기를 자동 시작하도록 보완했다. 최대화 창은 `GetWindowPlacement`로 상태를 확인해 복원 후 저장된 좌표를 적용한다. 집중 회귀 테스트, 공식 EXE 빌드, 활성 프로필이 있는 패키지의 자동 감시 기동 로그를 확인했다.
- 2026-08-10: Fixed the manual Apply All action so it waits for the asynchronous window refresh before matching profiles. Added a focused two-test regression suite; 36-test discovery and the official EXE rebuild passed.
- 2026-08-04: Added per-session single-instance protection to the packaged and development application entry point. A second launch now reports that WindowResizer is already running and exits without opening another main window. Focused regression coverage, 35-test discovery, native mutex validation, and an official EXE rebuild passed.
- 2026-07-31: 전체 코드 리뷰 후 프로필 원자 저장·백업 복구, 부드러운 투명도, 멀티 모니터 커서 해제, 시스템 테마, 무매칭 피드백, DPI 초기화, 깨끗한 빌드 명령을 보완했다. 회귀 테스트 23건, 공식 PyInstaller 빌드, 패키지 EXE 10초 기동 검사가 통과했다.

## Recently Completed

- 2026-07-31: added opt-in profile position locking in the profile editor and preserved existing advanced settings when saving edits.
- 2026-07-31: released active position and mouse constraints when those options are disabled.
- 2026-07-31: made main and profile editor styles use the active theme palette; added alternate-row colors and globally themed Qt message boxes.
- 2026-07-31: focused UI test passed 3 tests and the Windows executable build succeeded.
- 2026-07-31: 프로필 미리보기 오버레이, 자동 감지 토글, 정확한 자동 매칭과 전체 적용 경로를 추가했다.
- 2026-07-31: 실행 파일 경로 매칭, 경로 자동 채우기, 활성 입력 제어, 프로필 목록 경로 표시를 추가했다.
- 2026-07-31: 프로필 추가 직후 선택 누락으로 삭제가 어려운 문제를 회귀 테스트와 함께 수정했다.
- 2026-07-31: 닫기와 명시적 종료를 분리하고, 트레이 복원 및 종료 경로의 회귀 테스트를 추가했다.
- 2026-07-31: `tests/test_review_hardening.py`에 저장 실패 복구, 테마, 커서 해제, 투명도, 빌드 명령 회귀 검사를 추가했다.

## Next

- Manually verify the preview overlay on each monitor and executable-path automatic application against a real application launch.
- Manually verify one newly launched Blender window returns to its saved position and size after a move or resize.
- Manually confirm light/dark theme visibility, tray restore, and explicit exit in the packaged executable on a Windows desktop session.
- Manually verify the UI scale slider, reset action, and persisted 90% default in the packaged executable.

## Blockers

- None.
