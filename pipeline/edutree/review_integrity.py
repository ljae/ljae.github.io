"""정보 출처와 독립 수강 경험을 분리한다. 원자료는 저장소에 보존한다."""
import re
from urllib.parse import urlsplit, parse_qs

INFORMATION = {"naver_news": "news", "naver_web": "web_information",
               "naver_kin": "question_answer"}
QUESTION = re.compile(r"어떤가요|어때요|다녀보신|다니시는\s*분|추천\s*부탁|추천해\s*주세요|궁금합니다")
EXPERIENCE = re.compile(
    r"다녔|다녀봤|다니고|다니는\s*중|수강했|수강\s*중|보냈|보내고|"
    r"상담받|상담\s*받|테스트\s*봤|테스트를\s*봤|그만뒀|퇴원했|옮겼|"
    r"우리\s*(?:아이|애|딸|아들).{0,40}(?:만족|숙제|선생|수업)")
SELF = re.compile(r"안녕하세요[.!\s]*.{0,25}(?:학원|어학원)입니다|저희\s*(?:학원|어학원)에서\s*안내|"
                  r"신입생\s*모집|수강생\s*모집|원생\s*모집|상담\s*예약\s*문의")


def evidence_kind(row):
    source = row.get("source", "")
    if source in INFORMATION:
        return INFORMATION[source]
    text = f"{row.get('title') or ''} {row.get('snippet') or ''}"
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
