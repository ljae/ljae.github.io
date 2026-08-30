"""공유 카드(og-image.png)를 「實錄」 언어로 짠다. 1200 × 630.

옛 카드는 남색 그라데이션 위에 3D 책 아이콘을 얹은 것이라, 로고를 바꾼
뒤로는 이것만 옛 브랜드로 남아 있었다. **링크를 공유할 때 가장 먼저
보이는 자리**라 화면과 말투가 다르면 그게 곧 첫인상이 된다.

## 결정

    바탕   한지 + 옅은 계선. 화면의 PaperGround 와 같은 무늬다.
    배치   가운데 정렬을 쓰지 않는다. 왼쪽에 색인 여백(rail)을 비우고
           본문을 그 오른쪽에 세운다 — IndexRail 과 같은 규칙.
    표장   오른쪽에 **큰 판 마크**를 크게 앉힌다. 옛 카드가 3D 책을 두던
           자리이고, 새 마크는 그 자리에서 판면으로 읽힌다.
    주묵   두 곳. 마크의 도착점(마크의 일부다)과 인용 왼쪽의 짧은 획.
           화면 히어로가 쓰는 것과 같다.
    한자   **쓰지 않는다.** Paperlogy 에 한자 글자가 없어서(實測: 學院實錄
           네 자 모두 없음) 다른 서체를 섞어야 하는데, 넉 자 때문에 조판이
           어긋난다. 화면은 브라우저 대체 글꼴이 받아 주지만 그림은 못 받는다.

## 숫자를 넣지 않는다

히어로에는 등록 학원·채점 대상·분석한 글 수가 있다. 카드에는 **안 넣는다** —
정적 파일이라 야간 수집이 돌아도 안 바뀌고, 며칠 뒤면 화면과 다른 수를
말하게 된다. 이 서비스에서 틀린 숫자는 장식이 아니라 오류다.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from build_marks import (  # noqa: E402
    GRID,
    INK,
    PAPER,
    RULES,
    RULE_SEGMENTS,
    TOP,
    BOTTOM,
    VERMILION,
    W_FULL_RULE,
    W_FULL_STAIR,
    stair_rects,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "app/assets/fonts")

W, H = 1200, 630
MARGIN = 72
RAIL = 116  # AppSpace.rail — 화면과 같은 색인 여백

SLATE = "#6B675E"  # AppColors.slate
LINE = "#DDD5C4"  # AppColors.line

# 문구는 앱과 같은 출처를 쓴다. 손으로 옮겨 적으면 한쪽만 바뀐다.
HEADLINE = ["우리 아이는 지금 어디에 있고,", "다음엔 어디로 가야 하나요?"]
NAME = "학원실록"
BY = "by Open Edu"
EYEBROW = "대치 · 목동 · 반포 · 잠실 학원 테크트리"
LEAD = "학원실록은 학원 목록이 아니라 학원 사이의 길을 적습니다."
ORIGIN = "조선왕조실록이 사실을 있는 그대로 남겼듯, 학원 정보를 검증된 기록으로"
DOMAIN = "openedu4u.com"
OPERATOR = "운영 · Open Edu"


def font(weight, size):
    return ImageFont.truetype(f"{FONTS}/Paperlogy-{weight}.ttf", size)


def spaced(d, xy, text, f, fill, tracking):
    """자간을 벌려 찍는다. Pillow 에는 자간이 없어 글자마다 그린다.

    벌린 자간은 이 디자인에서 **작은 라벨의 표지**다(화면의 `spaced()`).
    """
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + tracking
    return x


def draw_mark(im, box, unit):
    """큰 판 마크. `logo-mark.svg` 와 같은 좌표다."""
    d = ImageDraw.Draw(im)
    x0, y0 = box

    def rect(a, b, c, e, fill):
        d.rectangle([x0 + a * unit, y0 + b * unit, x0 + c * unit, y0 + e * unit], fill=fill)

    r = W_FULL_RULE
    for x in RULES:
        for a, b in RULE_SEGMENTS[x]:
            rect(x - r / 2, a, x + r / 2, b, INK)
            if a == TOP:
                rect(x - 2, TOP, x + 2, TOP + r, INK)
            if b == BOTTOM:
                rect(x - 2, BOTTOM - r, x + 2, BOTTOM, INK)
    for bx, tip in stair_rects(W_FULL_STAIR):
        rect(bx[0], bx[1], bx[2], bx[3], VERMILION if tip else INK)


def main():
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)

    # ── 바탕 계선. 화면과 같은 84px 간격, 아주 옅게.
    for x in range(84, W, 84):
        d.line([(x, 0), (x, H)], fill="#E9E2D3", width=1)

    left = MARGIN + RAIL - 44

    # ── 이름. 공유 카드에서 **가장 먼저 답해야 하는 것은 '누구인가'** 다.
    #    앞선 판에서는 이름이 본문 속 한 번뿐이라 피드에서 못 읽혔다.
    #    표장(마크)은 오른쪽이 맡으므로 여기서는 글자만 세운다.
    f_name = font("8ExtraBold", 34)
    d.text((left, 74), NAME, font=f_name, fill=INK)
    nw = d.textlength(NAME, font=f_name)
    d.text((left + nw + 14, 86), BY, font=font("4Regular", 17), fill=SLATE)

    # ── 색인 여백의 표지. 굵은 획 하나 — SectionOpener 와 같은 말투.
    d.rectangle([MARGIN, 86, MARGIN + 38, 89], fill=INK)

    # ── 표제 위 라벨
    spaced(d, (left, 168), EYEBROW, font("5Medium", 17), SLATE, 3.2)

    # ── 표제
    y = 214
    f_head = font("8ExtraBold", 54)
    for line in HEADLINE:
        d.text((left, y), line, font=f_head, fill=INK)
        y += 70

    # ── 본문
    y += 26
    d.text((left, y), LEAD, font=font("4Regular", 20), fill="#2A2E38")

    # ── 이름의 유래. 왼쪽에 주묵 짧은 획 — 화면의 인용과 같다.
    y += 54
    d.rectangle([left, y + 3, left + 3, y + 27], fill=VERMILION)
    d.text((left + 16, y), ORIGIN, font=font("4Regular", 17), fill=SLATE)

    # ── 마크. 옛 카드가 3D 책을 두던 자리다.
    unit = 6.0  # 48단위 × 6 = 288px
    draw_mark(im, (836, (H - GRID * unit) / 2 - 10), unit)

    # ── 바닥. 계선 한 줄로 가르고 좌우로 벌린다.
    fy = H - 96
    d.line([(MARGIN, fy), (W - MARGIN, fy)], fill=LINE, width=1)
    f_foot = font("5Medium", 18)
    d.text((MARGIN, fy + 26), DOMAIN, font=f_foot, fill=INK)
    tw = d.textlength(OPERATOR, font=f_foot)
    d.text((W - MARGIN - tw, fy + 26), OPERATOR, font=f_foot, fill=SLATE)

    out = os.path.join(ROOT, "app/web/og-image.png")
    im.save(out)
    print("wrote app/web/og-image.png", im.size)


if __name__ == "__main__":
    main()
