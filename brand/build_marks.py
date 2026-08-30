"""로고 마크를 좌표에서 짓는다 — SVG 와 검증용 PNG 가 같은 표에서 나온다.

시안(래스터)을 눈으로 베끼지 않는다. 이 디자인은 획 두께가 토큰
(`AppRule` 0.7/1.0/2.0/3.0)이라 좌표를 손으로 정해야 규칙을 지킬 수 있고,
16px 에서 뭉개지는지도 좌표로만 증명된다.

## 격자

**48 단위 정사각.** 48 = 16 × 3 이라, 좌표가 3의 배수면 16px 에서 모든
모서리가 정수 픽셀에 떨어진다. 32·48·96px 도 자동으로 맞는다.

    16px 에서   3단위 = 1px,  6단위 = 2px

## 두 벌은 중심선을 공유하고 두께만 다르다

계단은 사각형 목록이 아니라 **중심선**(`STAIR_PATH`)으로 적는다. 큰 판과
작은 판이 같은 중심선을 쓰고 획 두께만 달리 받으므로, 작은 판이 축약이라는
사실이 파일이 아니라 **코드에서** 보장된다. 사각형으로 두 벌을 따로 적으면
한쪽만 고쳐 놓고 같은 도안이라고 부르게 된다.

두께를 달리하는 이유는 광학이다. 작은 판은 굵혀야 16px 에서 살아남고,
큰 판은 가늘어야 판면이 검은 덩어리가 되지 않는다. **처음에 두 벌을 같은
두께(6)로 두었더니 큰 판의 가운데가 뭉쳐 글자처럼 읽혔다** — 굵은 획과
이웃 계선 사이 흰 자리가 3단위밖에 안 남았다.

## 계단은 계선 하나가 굵어진 것이다

리서 세 개의 중심이 계선 자리 15 · 24 · 33 에 정확히 얹혀 있다. '다섯 줄
중 하나가 굵어져 계단으로 오른다'는 말 그대로다 — 굵은 획이 2번 계선에서
3번, 4번으로 건너가고 그 끝이 주묵이다.
"""

import os

# ── 색. theme.dart 의 값이다. 여기서 바꾸지 말 것.
INK = "#14161C"        # AppColors.ink
VERMILION = "#C4392A"  # AppColors.vermilion
PAPER = "#F4F0E6"      # AppColors.canvas

GRID = 48
TOP, BOTTOM = 6, 42    # 판면의 위·아래 기준선

RULES = (6, 15, 24, 33, 42)   # 계선 다섯, 간격 9

# ── 계단의 중심선. 아래에서 올라와 두 번 건너가고, 마지막 구간이 주묵이다.
#    리서 x 는 계선 자리와 같다(15 → 24 → 33). 트레드 y 는 30 → 18.
STAIR_PATH = ((15, 42), (15, 30), (24, 30), (24, 18), (33, 18), (33, TOP))
TIP_FROM = 4   # 중심선의 다섯째 점부터가 주묵 구간

W_FULL_STAIR, W_FULL_RULE = 4, 1   # 큰 판 — 4 : 1
W_COMPACT_STAIR, W_COMPACT_RULE = 6, 3  # 작은 판 — 굵혀서 16px 에서 살린다

# ── 계선의 **보이는 구간**. 굵은 획이 지나는 칸에서는 계선을 그리지 않는다.
#
# 처음에는 계선을 온전히 깔고 그 위에 굵은 획을 얹었다. 화면은 같아 보이지만
# 파일에는 영영 안 보이는 사각형이 남는다 — 나중에 먹빛을 반투명으로 바꾸는
# 순간 유령이 드러난다. 굵은 획은 그 계선을 가로지르는 것이 아니라
# **대신하는** 것이므로 겹치는 구간은 비운다. 그래야 한 칸이 '가늘다가
# 굵어진 한 줄'로 이어져 읽힌다.
#
# 값은 **굵은 쪽(작은 판, w=6)** 기준이다. 큰 판(w=4)에서는 굵은 획이 덜
# 넓어 계선이 몇 단위 더 깔리지만 어차피 획 아래라 안 보인다. 넉넉한 쪽으로
# 틀리는 것이 맞다 — 모자라게 잡으면 획과 계선 사이에 **흰 틈**이 생기고,
# 그건 화면에 그대로 보인다.
RULE_SEGMENTS = {
    6: ((TOP, BOTTOM),),            # 굵은 획이 지나지 않는다
    15: ((TOP, 30),),               # 30~42 는 리서 1
    24: ((TOP, 18), (30, BOTTOM)),  # 18~30 은 리서 2
    33: ((18, BOTTOM),),            # 6~18 은 주묵과 트레드 2
    42: ((TOP, BOTTOM),),
}


def stair_rects(w):
    """중심선을 두께 w 로 살찌워 사각형 목록을 낸다.

    이음매에서만 w/2 만큼 늘린다. 양 끝(맨 아래·맨 위)은 늘리지 않는다 —
    늘리면 기준선을 넘어 판면 밖으로 삐져나간다.

    **주묵 구간만은 이음매에서 반대로 물러선다.** 늘리면 모서리 칸까지
    붉어져 주묵이 트레드를 먹는다. 주묵은 트레드 **윗변에 접하는** 것이지
    트레드의 일부가 아니다 — 여기서 한 번 틀렸다(주묵이 4단위 길어졌다).
    """
    half = w / 2
    out = []
    for i in range(len(STAIR_PATH) - 1):
        (x0, y0), (x1, y1) = STAIR_PATH[i], STAIR_PATH[i + 1]
        first, last = i == 0, i == len(STAIR_PATH) - 2
        tip = i >= TIP_FROM
        if x0 == x1:  # 세로
            lo, hi = min(y0, y1), max(y0, y1)
            # 자유단(첫 구간의 아래, 끝 구간의 위)은 그대로 두고 이음매만 늘린다
            if not last:
                lo -= half
            if not first:
                hi += -half if tip else half
            box = (x0 - half, lo, x0 + half, hi)
        else:  # 가로 — 양 끝이 모두 이음매다
            lo, hi = min(x0, x1), max(x0, x1)
            box = (lo - half, y0 - half, hi + half, y0 + half)
        out.append((box, i >= TIP_FROM))
    return out


def _rect(x0, y0, x1, y1, fill):
    def n(v):
        return int(v) if float(v).is_integer() else v

    return (
        f'  <rect x="{n(x0)}" y="{n(y0)}" width="{n(x1 - x0)}" '
        f'height="{n(y1 - y0)}" fill="{fill}"/>'
    )


def _ink():
    return f"var(--logo-ink, {INK})"


def _stair_body(w):
    return [
        _rect(*box, f"var(--logo-accent, {VERMILION})" if tip else _ink())
        for box, tip in stair_rects(w)
    ]


def _svg(body, desc, background=False):
    # XML 주석 안에는 하이픈 두 개를 넣을 수 없다. 변수 이름을 그대로 적으면
    # (`--logo-ink`) 파일이 비표준 XML 이 된다 — 브라우저는 넘어가지만 엄격한
    # 파서는 거부한다. 여기서 한 번 틀렸고, 검증이 잡았다.
    note = (
        "  <!-- 색은 CSS 변수로 열어 둔다: logo-ink / logo-accent (하이픈 두 개를\n"
        "       앞에 붙여 쓴다). 인라인이면 먹빛 판면에 맞출 수 있고, img 로\n"
        "       불러도 대체값이 그대로 쓰인다. -->"
    )
    bg = _rect(0, 0, GRID, GRID, f"var(--logo-paper, {PAPER})") + "\n" if background else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {GRID} {GRID}" '
        f'width="{GRID}" height="{GRID}" role="img" aria-labelledby="t d">\n'
        f'  <title id="t">학원실록</title>\n'
        f'  <desc id="d">{desc}</desc>\n{note}\n{bg}'
        + "\n".join(body)
        + "\n</svg>\n"
    )


def full_mark():
    """큰 판 — 판면이 온전히 읽히는 쪽. 소개·OG·인쇄용."""
    w, r = W_FULL_STAIR, W_FULL_RULE
    body = []
    for x in RULES:
        for y0, y1 in RULE_SEGMENTS[x]:
            body.append(_rect(x - r / 2, y0, x + r / 2, y1, _ink()))
            # 마감 획은 **가는 계선의 끝**을 맺는 것이다. 끝이 굵은 획인
            # 칸에는 찍지 않는다 — 찍으면 그 자리만 부푼다.
            if y0 == TOP:
                body.append(_rect(x - 2, TOP, x + 2, TOP + r, _ink()))
            if y1 == BOTTOM:
                body.append(_rect(x - 2, BOTTOM - r, x + 2, BOTTOM, _ink()))
    body.extend(_stair_body(w))
    return _svg(
        body,
        "실록 판면의 계선 다섯 줄 중 하나가 굵어져 계단으로 오르고, "
        "그 끝에 주묵이 찍힌다.",
    )


def compact_mark(background=False):
    """작은 판 — 큰 판의 축약. 계선 둘만 남기고 굵힌다. 마감 획은 뗀다."""
    r = W_COMPACT_RULE
    body = [
        _rect(3, TOP, 3 + r, BOTTOM, _ink()),
        _rect(GRID - 3 - r, TOP, GRID - 3, BOTTOM, _ink()),
    ]
    body.extend(_stair_body(W_COMPACT_STAIR))
    return _svg(
        body,
        "큰 판의 축약. 계선을 둘로 줄이고 굵혔다. 계단은 같은 중심선이다.",
        background=background,
    )


def render_png(path, size, compact, background):
    """같은 좌표표로 PNG 를 그린다.

    래스터라이저를 안 쓰는 이유: 이 도형이 전부 축에 나란한 사각형이라
    직접 그리면 격자에 맞는지가 렌더러의 안티에일리어싱에 가려지지 않고
    그대로 드러난다.
    """
    from PIL import Image, ImageDraw

    k = size / GRID
    im = Image.new("RGB", (size, size), PAPER if background else "#FFFFFF")
    d = ImageDraw.Draw(im)

    def box(x0, y0, x1, y1, fill):
        d.rectangle([x0 * k, y0 * k, x1 * k - 1, y1 * k - 1], fill=fill)

    if compact:
        r = W_COMPACT_RULE
        box(3, TOP, 3 + r, BOTTOM, INK)
        box(GRID - 3 - r, TOP, GRID - 3, BOTTOM, INK)
        w = W_COMPACT_STAIR
    else:
        r = W_FULL_RULE
        for x in RULES:
            for y0, y1 in RULE_SEGMENTS[x]:
                box(x - r / 2, y0, x + r / 2, y1, INK)
                if y0 == TOP:
                    box(x - 2, TOP, x + 2, TOP + r, INK)
                if y1 == BOTTOM:
                    box(x - 2, BOTTOM - r, x + 2, BOTTOM, INK)
        w = W_FULL_STAIR
    for bx, tip in stair_rects(w):
        box(*bx, VERMILION if tip else INK)
    im.save(path)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    for name, text in {
        "logo-mark.svg": full_mark(),
        "logo-mark-compact.svg": compact_mark(),
        "logo-icon.svg": compact_mark(background=True),
    }.items():
        with open(os.path.join(here, name), "w") as f:
            f.write(text)
        print("wrote", name)

    prev = os.path.join(here, "preview")
    os.makedirs(prev, exist_ok=True)
    for size in (16, 32, 64, 256):
        render_png(f"{prev}/compact-{size}.png", size, True, False)
    for size in (64, 256, 512):
        render_png(f"{prev}/full-{size}.png", size, False, False)
    print("wrote preview/")


if __name__ == "__main__":
    main()
