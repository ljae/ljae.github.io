"""정보 출처와 독립 수강 경험을 분리한다. 원자료는 저장소에 보존한다."""
import re
from urllib.parse import urlsplit, parse_qs

INFORMATION = {"naver_news": "news", "naver_web": "web_information",
               "naver_kin": "question_answer"}
QUESTION = re.compile(r"어떤가요|어때요|다녀보신|다니시는\s*분|추천\s*부탁|추천해\s*주세요|궁금합니다|궁금하네요|아시는\s*분|계실까요|계신가요|가능할까요|보려는데")
EXPERIENCE = re.compile(
    r"다녔|다녀봤|다녀왔|다녀온|참석했|참석한\s*후기|들어봤|다니고|다니는\s*중|수강했|수강\s*중|보냈|보내고|"
    r"상담받|상담\s*받|테스트\s*봤|테스트를\s*봤|그만뒀|퇴원했|옮겼|"
    r"우리\s*(?:아이|애|딸|아들).{0,40}(?:만족|숙제|선생|수업)")
SELF = re.compile(r"안녕하세요[.!\s]*.{0,25}(?:학원|어학원)입니다|저희\s*(?:학원|어학원)에서\s*안내|"
                  r"신입생\s*모집|수강생\s*모집|원생\s*모집|상담\s*예약\s*문의")

# 거래·센터 공지는 본문에 수업/만족 같은 단어가 있어도 독립 수강 후기가 아니다.
MARKETPLACES = ('/joonggonara/', '/joonggonara2/', 'bunjang.co.kr', 'daangn.com')
RESALE = re.compile(r'(?:교재|책|도서|문제집).{0,25}(?:팝니다|판매|양도|드림|나눔)|(?:팝니다|판매|양도).{0,20}(?:교재|책|도서)|카페 상품 게시글|책상태\s*깨끗')
ANNOUNCEMENT = re.compile(r'설명회|개원\s*확정|시간표\s*안내|개강\s*안내|신규반\s*모집|감사\s*인사')
EVENT_REVIEW = re.compile(r'후기|다녀|참석|듣고|들었|느낀')
DIRECTORY_TITLE = re.compile(r'학원\s*명단|학원정보|학원\s*정보|학원\s*위치\s*안내')
DIRECTORY_AUTHOR = re.compile(r'스터디홀릭\s*운영자|오늘\s*소개해드릴\s*학원|후기\s*중\s*내용\s*일부|학원비.{0,12}수업방식.{0,12}교재|교습학원.{0,3}교습소')
OWNER = re.compile(r'(?:저희|우리)\s*(?:학원|센터|문해원)|브레인컨설팅그룹입니다|신규반\s*모집')


def evidence_kind(row):
    source = row.get("source", "")
    if source in INFORMATION:
        return INFORMATION[source]
    title = row.get('title') or ''
    text = f"{title} {row.get('snippet') or ''}"
    url = (row.get('source_url') or row.get('url') or '').lower()
    if any(host in url for host in MARKETPLACES) or RESALE.search(text):
        return 'marketplace'
    if DIRECTORY_TITLE.search(title) or DIRECTORY_AUTHOR.search(text):
        return 'directory_information'
    if ANNOUNCEMENT.search(title) and (OWNER.search(text) or not EVENT_REVIEW.search(title)):
        return 'self_promotion'
    if re.search(r'기적을 경험하게 되실|우리는 지금 대한민국의 미래를 만들', text):
        return 'self_promotion'
    if SELF.search(text) and not EXPERIENCE.search(text):
        return "self_promotion"
    if QUESTION.search(text) and not EXPERIENCE.search(text):
        return "question_only"
    return "community_mention"


def exclusion_reason(row):
    kind = evidence_kind(row)
    return None if kind == "community_mention" else kind


def canonical_document(url):
    """확인된 네이버 URL 형태만 합친다. 알 수 없는 쿼리는 보존한다."""
    try:
        p = urlsplit(url or "")
    except ValueError:
        return url
    host = (p.hostname or "").lower()
    if host in {"blog.naver.com", "m.blog.naver.com"}:
        match = re.fullmatch(r"/([A-Za-z0-9_-]+)/(\d+)/?", p.path)
        if match:
            return f"naver-blog:{match[1]}:{match[2]}"
        if p.path.lower() == "/postview.naver":
            q = parse_qs(p.query)
            if q.get("blogId") and q.get("logNo"):
                return f"naver-blog:{q['blogId'][0]}:{q['logNo'][0]}"
    return url


def flag_duplicate_urls(rows):
    seen = set()
    for row in rows:
        if row.get("is_excluded") or not row.get("source_url"):
            continue
        key = (row.get("academy_key"), canonical_document(row["source_url"]))
        if key in seen:
            row["is_excluded"] = True
            row["exclude_reason"] = "duplicate_url"
        else:
            seen.add(key)
    return rows
