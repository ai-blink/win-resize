"""S2 게이트 3단계: C# 이 쓴 profiles.json 을 PyQt5 앱이 그대로 쓸 수 있는가.

사용법:
    python profile_roundtrip_check.py <원본 복사본> <C# 이 쓴 파일>

두 파일을 PyQt5 앱의 Profile.from_dict 로 각각 읽어 프로필 객체가 같은지 본다.
파일 바이트가 같을 필요는 없다. 기준은 "PyQt5 앱이 이 파일을 원본과 똑같이 읽는가"다.
추가로 json.load 결과(dict)도 비교한다 - C# 이 없던 키를 새로 써 넣으면 여기서 걸린다.

종료 코드: 0 같음, 1 다름, 2 사용법 오류.
원본 파일은 읽기만 한다.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.core.profile_manager import Profile  # noqa: E402


def load_raw(path: Path) -> dict:
    # utf-8 (BOM 없음) 으로 연다. PyQt5 앱의 load_profiles 와 같은 방식이다.
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_profiles(raw: dict) -> dict:
    # from_dict 가 입력 dict 를 고치므로 복사본을 넘긴다.
    copied = json.loads(json.dumps(raw))
    return {pid: Profile.from_dict(data) for pid, data in copied.get("profiles", {}).items()}


def main(argv: list) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2

    original_path, written_path = Path(argv[1]), Path(argv[2])
    original_raw = load_raw(original_path)
    written_raw = load_raw(written_path)

    failures = []

    for key in ("version", "created_at"):
        if original_raw.get(key) != written_raw.get(key):
            failures.append(f"top-level {key}: {original_raw.get(key)!r} != {written_raw.get(key)!r}")

    original_ids = list(original_raw.get("profiles", {}))
    written_ids = list(written_raw.get("profiles", {}))
    if original_ids != written_ids:
        failures.append(f"profile id order: {original_ids} != {written_ids}")

    for pid in original_ids:
        before = original_raw["profiles"].get(pid)
        after = written_raw.get("profiles", {}).get(pid)
        if before != after:
            changed = sorted(k for k in set(before or {}) | set(after or {})
                             if (before or {}).get(k) != (after or {}).get(k))
            failures.append(f"raw dict {pid}: keys differ {changed}")

    original_profiles = load_profiles(original_raw)
    written_profiles = load_profiles(written_raw)
    for pid, profile in original_profiles.items():
        if written_profiles.get(pid) != profile:
            failures.append(f"Profile object {pid} ({profile.name}) differs after C# round trip")

    print(f"profiles: {len(original_profiles)} original, {len(written_profiles)} written")
    if failures:
        for failure in failures:
            print("FAIL", failure)
        return 1

    print("PASS: Python reads the C# output to equal Profile objects and equal raw dicts")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
