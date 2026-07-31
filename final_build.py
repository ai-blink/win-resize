#!/usr/bin/env python3
"""
최종 WindowResizer 빌드 스크립트 - 모든 모듈 포함
"""
import subprocess
import sys
from pathlib import Path


def create_build_command(project_root, main_script):
    """Create a build command using only optional, source-controlled assets."""
    icon_path = project_root / "src" / "img" / "windowresizer.ico"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",           # 단일 실행 파일
        "--windowed",          # 콘솔 창 숨기기
        "--name=WindowResizer", # 실행 파일 이름
        "--clean",             # 이전 빌드 정리
        "--noconfirm",         # 확인 없이 진행
        "--paths=src",         # src 패키지를 hidden import 분석 경로에 추가
        "--add-data=src;src",  # src 디렉토리 포함
        
        # 핵심 Python 모듈들
        "--hidden-import=concurrent.futures",  # 새로 추가
        "--hidden-import=concurrent.futures.thread",
        "--hidden-import=concurrent.futures.process",
        "--hidden-import=multiprocessing",
        "--hidden-import=threading", 
        "--hidden-import=queue",
        "--hidden-import=json",
        "--hidden-import=logging",
        "--hidden-import=pathlib",
        "--hidden-import=dataclasses",
        "--hidden-import=enum",
        "--hidden-import=typing",
        "--hidden-import=collections",
        "--hidden-import=functools",
        "--hidden-import=itertools",
        
        # PyQt5 전체 모듈
        "--hidden-import=PyQt5",
        "--hidden-import=PyQt5.QtCore",
        "--hidden-import=PyQt5.QtGui", 
        "--hidden-import=PyQt5.QtWidgets",
        "--hidden-import=PyQt5.QtTest",
        "--hidden-import=PyQt5.sip",
        
        # Windows API - 완전 포함
        "--hidden-import=ctypes",
        "--hidden-import=ctypes.wintypes",
        "--hidden-import=ctypes.util",
        "--hidden-import=win32api",
        "--hidden-import=win32con",
        "--hidden-import=win32gui",
        "--hidden-import=win32process",
        "--hidden-import=win32security",
        "--hidden-import=win32event",
        "--hidden-import=win32file",
        
        # 시스템 모듈
        "--hidden-import=psutil",
        "--hidden-import=os",
        "--hidden-import=sys",
        "--hidden-import=time",
        "--hidden-import=datetime",
        "--hidden-import=subprocess",
        
        # WindowResizer 모든 핵심 모듈
        "--hidden-import=src",
        "--hidden-import=src.core",
        "--hidden-import=src.gui", 
        "--hidden-import=core.windows_api",
        "--hidden-import=core.window_enumerator",
        "--hidden-import=core.enhanced_window_manipulator",
        "--hidden-import=core.profile_manager",
        "--hidden-import=core.process_monitor",
        "--hidden-import=core.hotkey_manager",
        "--hidden-import=core.window_state_manager",
        "--hidden-import=core.cursor_control",
        "--hidden-import=core.error_handler",
        "--hidden-import=gui.main_window",
        "--hidden-import=gui.theme_manager",
        "--hidden-import=gui.preset_controls",
        "--hidden-import=gui.profile_dialog",
        "--hidden-import=gui.system_tray",
        
        # 불필요한 모듈들 제외
        "--exclude-module=matplotlib",
        "--exclude-module=numpy", 
        "--exclude-module=pandas",
        "--exclude-module=scipy",
        "--exclude-module=tkinter",
        "--exclude-module=IPython",
        "--exclude-module=jupyter",
        "--exclude-module=notebook",
        "--exclude-module=sphinx",
        "--exclude-module=setuptools",

        str(main_script)
    ]

    if icon_path.is_file():
        cmd.insert(-1, f"--icon={icon_path}")

    version_file = project_root / "version_info.txt"
    if version_file.is_file():
        cmd.insert(-1, f"--version-file={version_file}")

    return cmd, icon_path

def build_windowresizer():
    """완전한 WindowResizer 빌드"""

    project_root = Path(__file__).parent
    main_script = project_root / "run_gui.py"

    if not main_script.exists():
        print(f"오류: 메인 스크립트를 찾을 수 없습니다: {main_script}")
        return False

    print("WindowResizer 최종 빌드 시작...")
    print(f"메인 스크립트: {main_script}")

    cmd, icon_path = create_build_command(project_root, main_script)
    if icon_path.is_file():
        print(f"소스 아이콘 사용: {icon_path}")
    else:
        print("소스 아이콘이 없어 기본 실행 파일 아이콘으로 빌드합니다.")

    print("빌드 명령어 실행 중...")
    
    try:
        # 빌드 실행
        result = subprocess.run(
            cmd, 
            cwd=project_root, 
            capture_output=True, 
            text=True, 
            timeout=900  # 15분 타임아웃
        )
        
        if result.returncode == 0:
            print("빌드 성공!")
            
            # 실행 파일 확인
            exe_path = project_root / "dist" / "WindowResizer.exe"
            if exe_path.exists():
                size_mb = exe_path.stat().st_size / (1024 * 1024)
                print(f"실행 파일 생성: {exe_path}")
                print(f"파일 크기: {size_mb:.1f} MB")
                return True
            else:
                print("오류: 실행 파일이 생성되지 않았습니다")
                return False
        else:
            print(f"빌드 실패 (코드: {result.returncode})")
            print("오류 출력:")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("빌드 시간 초과 (15분)")
        return False
    except Exception as e:
        print(f"빌드 중 오류 발생: {e}")
        return False

if __name__ == "__main__":
    success = build_windowresizer()
    if success:
        print("\n최종 빌드 완료!")
        print(f"실행 파일: {Path(__file__).parent / 'dist' / 'WindowResizer.exe'}")
        print("\n이제 GUI가 정상적으로 실행됩니다.")
    else:
        print("\n최종 빌드 실패!")
    sys.exit(0 if success else 1)
