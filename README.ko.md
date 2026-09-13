# WindowResizer

[English](README.md) | [한국어](README.ko.md) | [中文](README.zh-CN.md) | [日本語](README.ja.md)

WindowResizer는 실행 중인 Windows 창을 찾고, 위치 또는 크기를 조절하며, 저장한 창
프로필을 반복 적용할 수 있는 Windows 데스크톱 애플리케이션입니다.

현재 문서화된 릴리스: 0.01.4

## 앱 화면

![WindowResizer 메인 화면](docs/images/windowresizer-main-window.png)

## 주요 기능

- 실행 중인 창을 선택해 이동하거나 크기를 조절합니다.
- 창의 위치와 크기를 재사용 가능한 프로필로 저장합니다.
- 실행 파일 전체 경로로 프로필을 매칭해 파일명이 같은 앱도 구분합니다.
- 실제 창에 적용하기 전에 저장된 배치를 미리 봅니다.
- 조건에 맞는 새 창이 감지되면 선택적으로 프로필을 자동 적용합니다.
- 프로필별 창 위치 고정과 마우스 커서 제한을 독립적으로 설정합니다.
- 프로필 동작을 빠르게 실행할 수 있는 전역 단축키를 등록합니다.
- 라이트, 다크, 고대비 테마를 선택하고 저장된 창 크기에 영향을 주지 않는 앱 UI
  배율을 조정합니다.
- 메인 창을 닫아도 시스템 트레이에서 계속 사용할 수 있으며, 필요할 때 명시적인
  종료 동작으로 앱을 완전히 종료합니다.
- 같은 Windows 세션에서 앱이 중복 실행되는 것을 막습니다.

## 요구 사항

- Windows 10 또는 Windows 11
- 개발 실행용 Python 3.12 또는 빌드된 Windows 실행 파일

관리자 권한으로 실행 중인 대상 창은 일반 권한의 WindowResizer에서 조작하지 못할 수
있습니다. 필요한 경우 WindowResizer도 같은 권한 수준으로 실행하세요.

## 소스에서 실행하기

저장소 루트에서 의존성을 설치한 뒤 앱을 실행합니다.

~~~powershell
C:\Python312\python.exe -m pip install -r requirements.txt
C:\Python312\python.exe run_gui.py
~~~

문서의 명령은 기본 python이 다른 버전을 가리키는 상황을 피하기 위해 검증된
Python 3.12 경로를 사용합니다.

## 실행 파일 빌드

~~~powershell
C:\Python312\python.exe final_build.py
~~~

성공하면 dist/WindowResizer.exe가 생성됩니다. dist/와 build/는 생성물이므로
소스 제어에 포함하지 않습니다.

## 변경 검증

변경한 영역의 집중 회귀 테스트를 실행하세요. 추적 중인 테스트 전체를 실행하려면
다음 명령을 사용합니다.

~~~powershell
C:\Python312\python.exe -m unittest discover -s tests -p 'test_*.py'
~~~

## 문서

설치와 사용 문서는 현재 한국어이며, 패치 노트는 영어·한국어·중국어 간체·일본어로
제공됩니다.

- [설치와 실행 안내](docs/INSTALLATION.md)
- [사용 안내](docs/USER_GUIDE.md)
- [변경 기록: English](docs/CHANGELOG.md) | [한국어](docs/CHANGELOG.ko.md) |
  [中文](docs/CHANGELOG.zh-CN.md) | [日本語](docs/CHANGELOG.ja.md)

## 저장소 구성

- src/: 애플리케이션 소스 코드
- run_gui.py: 개발 실행 진입점
- final_build.py: PyInstaller 빌드 스크립트
- requirements.txt: Python 의존성
- tests/: 추적 중인 회귀 테스트
- docs/: 사용자 문서와 이미지
