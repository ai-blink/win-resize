"""앱 아이콘(ICO) 생성기.

원본 PNG(투명 배경 한 장)에서 그림이 있는 영역만 잘라 정사각형으로 맞추고, 작업 표시줄/트레이/제목줄/탐색기가 쓰는
여러 크기를 한 ICO 파일에 담는다. 작은 크기는 큰 그림을 LANCZOS 로 줄여 만든다(크기마다 따로 손으로 그리지 않는다).

사용:
    python next/tools/make_app_icon.py <원본.png> <출력.ico>
기본값: 원본 = next/src/WindowResizer.App/Assets/app-icon-source.png, 출력 = 같은 폴더의 app.ico
"""
import sys
from pathlib import Path

from PIL import Image

SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]
MARGIN = 0.04  # 그림 둘레에 남길 여백(한 변 대비). 창 제목줄에서 가장자리가 잘려 보이지 않게.


def build(source: Path, target: Path) -> list[int]:
    image = Image.open(source).convert("RGBA")
    box = image.getchannel("A").getbbox()
    if box is None:
        raise SystemExit("원본에 그려진 픽셀이 없다: " + str(source))

    cropped = image.crop(box)
    side = max(cropped.size)
    pad = round(side * MARGIN)
    canvas_side = side + 2 * pad
    canvas = Image.new("RGBA", (canvas_side, canvas_side), (0, 0, 0, 0))
    canvas.paste(cropped, ((canvas_side - cropped.width) // 2, (canvas_side - cropped.height) // 2))

    # Pillow 는 가장 큰 그림에서 sizes 에 든 크기를 줄여 프레임으로 넣는다.
    master = canvas.resize((256, 256), Image.LANCZOS)
    master.save(target, format="ICO", sizes=[(s, s) for s in SIZES])
    return SIZES


if __name__ == "__main__":
    here = Path(__file__).resolve().parent.parent / "src" / "WindowResizer.App" / "Assets"
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "app-icon-source.png"
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else here / "app.ico"
    sizes = build(src, dst)
    print("wrote", dst, "frames:", sizes)
