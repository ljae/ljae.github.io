"""파비콘·앱아이콘을 로고 좌표에서 낸다. `build_marks.py` 와 같은 표를 쓴다.

이미지를 손으로 오려 만들지 않는다. 규격이 스무 가지가 넘어서, 한 번
손으로 맞추면 다음에 로고를 조금만 고쳐도 전부 어긋난다.

## 크기마다 그리는 법이 다르다

48단위 격자가 정수 픽셀에 떨어지는 것은 **16의 배수 크기**뿐이다
(3단위 × size/48 이 정수 ⟺ size % 16 == 0). 그런 크기는 사각형을 그대로
찍어 **칼같이** 나오고, 아닌 크기(180·120·167 …)는 4배로 그린 뒤 줄여
안티에일리어싱에 맡긴다. 안 그러면 획마다 1픽셀씩 들쭉날쭉해진다.

## 마스커블은 따로 만든다

안드로이드는 아이콘을 제 마음대로 잘라내므로(원·둥근사각·물방울) 안전
영역은 **가운데 지름 80% 원**뿐이다. 마크의 대각선이 그 원에 들어가야
해서 0.68 로 줄여 앉힌다. 같은 그림을 그냥 쓰면 계선이 잘려 나간다.

## iOS 아이콘에는 알파를 넣지 않는다

투명이 있으면 App Store 심사에서 걸린다. 한지 바탕을 깔고 RGB 로 낸다.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw  # noqa: E402

from build_marks import (  # noqa: E402
    GRID,
    INK,
    PAPER,
    TOP,
    BOTTOM,
    VERMILION,
    W_COMPACT_RULE,
    W_COMPACT_STAIR,
    stair_rects,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _draw(size, ground, scale=1.0):
    """작은 판을 size × size 로 그린다. ground 가 None 이면 투명."""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0) if ground is None else ground)
    d = ImageDraw.Draw(im)
    k = size / GRID * scale
    off = (size - GRID * k) / 2  # 줄였을 때 가운데로

    def box(x0, y0, x1, y1, fill):
        d.rectangle(
            [off + x0 * k, off + y0 * k, off + x1 * k - 1, off + y1 * k - 1], fill=fill
        )

    r = W_COMPACT_RULE
    box(3, TOP, 3 + r, BOTTOM, INK)
    box(GRID - 3 - r, TOP, GRID - 3, BOTTOM, INK)
    for bx, tip in stair_rects(W_COMPACT_STAIR):
        box(*bx, VERMILION if tip else INK)
    return im


def icon(size, ground=PAPER, scale=1.0, rgb=False):
    """격자에 안 떨어지는 크기는 4배로 그려 줄인다."""
    snaps = size % 16 == 0 and scale == 1.0
    im = _draw(size if snaps else size * 4, ground, scale)
    if not snaps:
        im = im.resize((size, size), Image.LANCZOS)
    return im.convert("RGB") if rgb else im


# (경로, 크기, 바탕, 배율, RGB 여부)
TARGETS = [
    ("app/web/favicon.png", 64, PAPER, 1.0, False),
    ("app/web/icons/icon-32.png", 32, PAPER, 1.0, False),
    ("app/web/icons/icon-180.png", 180, PAPER, 1.0, False),
    ("app/web/icons/Icon-192.png", 192, PAPER, 1.0, False),
    ("app/web/icons/Icon-512.png", 512, PAPER, 1.0, False),
    # 마스커블 — 안전 영역(지름 80% 원) 안으로 줄인다
    ("app/web/icons/Icon-maskable-192.png", 192, PAPER, 0.68, False),
    ("app/web/icons/Icon-maskable-512.png", 512, PAPER, 0.68, False),
    # 앱 헤더가 읽는 자산
    ("app/assets/brand/mark.png", 512, PAPER, 1.0, False),
]

IOS = "app/ios/Runner/Assets.xcassets/AppIcon.appiconset"
IOS_SIZES = {
    "Icon-App-20x20@1x.png": 20,
    "Icon-App-20x20@2x.png": 40,
    "Icon-App-20x20@3x.png": 60,
    "Icon-App-29x29@1x.png": 29,
    "Icon-App-29x29@2x.png": 58,
    "Icon-App-29x29@3x.png": 87,
    "Icon-App-40x40@1x.png": 40,
    "Icon-App-40x40@2x.png": 80,
    "Icon-App-40x40@3x.png": 120,
    "Icon-App-60x60@2x.png": 120,
    "Icon-App-60x60@3x.png": 180,
    "Icon-App-76x76@1x.png": 76,
    "Icon-App-76x76@2x.png": 152,
    "Icon-App-83.5x83.5@2x.png": 167,
    "Icon-App-1024x1024@1x.png": 1024,
}


def main():
    for rel, size, ground, scale, rgb in TARGETS:
        path = os.path.join(ROOT, rel)
        icon(size, ground, scale, rgb).save(path)
        print("wrote", rel)

    for name, size in IOS_SIZES.items():
        path = os.path.join(ROOT, IOS, name)
        icon(size, PAPER, 1.0, rgb=True).save(path)
    print("wrote", len(IOS_SIZES), "iOS icons")

    # .ico 는 여러 크기를 한 파일에 담는다. 브라우저·윈도우가 필요한 것을 고른다.
    ico = os.path.join(ROOT, "app/web/favicon.ico")
    icon(64).save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    print("wrote app/web/favicon.ico")


if __name__ == "__main__":
    main()
