# Development Progress

## Current

- 2026-07-31: 전체 코드 리뷰 후 프로필 원자 저장·백업 복구, 부드러운 투명도, 멀티 모니터 커서 해제, 시스템 테마, 무매칭 피드백, DPI 초기화, 깨끗한 빌드 명령을 보완했다. 회귀 테스트 23건은 통과했으며, 공식 빌드는 실행 중인 `dist\WindowResizer.exe` 파일 잠금 해제 후 다시 확인한다.

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

- Close the running packaged executable and rerun `C:\Python312\python.exe final_build.py`.
- Manually verify the preview overlay on each monitor and executable-path automatic application against a real application launch.
- Manually confirm tray restore and explicit exit in the rebuilt packaged executable on a Windows desktop session.

## Blockers

- `dist\WindowResizer.exe` is currently locked by a running process, preventing the final PyInstaller replacement step.
