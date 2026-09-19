"""수집 출처 확대 시 후기 오인·동명 연결·캐시 판정 회귀 방지."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from edutree import analyze, directory, naver, review_integrity, profiles, source_health

@pytest.mark.parametrize('source', ['naver_web','naver_news','naver_kin'])
def test_information_does_not_become_review(source):
    row = analyze.analyze({'source':source,'snippet':'수학 3개월 수업이 좋았어요','author_hash':'platform'})
    assert row['is_excluded'] and row['author_hash'] is None

@pytest.mark.parametrize('text', ['수강료를 지급받아 작성했습니다','협찬을 받아 작성한 후기입니다','원고료를 제공 받아 작성했습니다'])
def test_disclosures(text):
    assert analyze.analyze({'snippet':text})['exclude_reason'] == 'sponsored'

@pytest.mark.parametrize('text', ['협찬 없이 다녔어요','협찬을 받지 않았습니다','자료를 제공받아 참고했습니다'])
def test_non_disclosures(text):
    assert not analyze.sponsorship_disclosed(text)

@pytest.mark.parametrize('title,body,excluded', [
    ('가나다학원 어떤가요?', '다녀보신 분 추천 부탁해요', True),
    ('가나다학원 어떤가요?', '저는 3개월 다녔어요. 숙제는 많아요', False),
    ('신입생 모집','수학 수강생 모집합니다', True),
    ('수업 후기','3개월 다니고 있어요. 선생님이 잘 봐주세요', False),
])
def test_question_vs_experience(title, body, excluded):
    assert analyze.analyze({'title':title,'snippet':body})['is_excluded'] == excluded


def test_cafe_name_is_not_an_author_even_in_old_cache():
    assert naver._author_hash({'cafename':'대치맘'},'naver_cafe') is None
    rows = [analyze.analyze({'source':'naver_cafe','academy_key':'A',
             'author_hash':'same-cafe','snippet':'다니고 있어요','posted_at':f'2026-09-{i:02d}'}) for i in range(1,5)]
    assert analyze.flag_author_bursts(rows)[1] == 0
    assert all(not r.get('repeat_author_count') for r in analyze.flag_repeat_authors(rows))


def test_duplicate_mobile_and_desktop_blogs():
    urls = ['https://blog.naver.com/parent/123', 'https://m.blog.naver.com/parent/123?ref=x',
            'https://blog.naver.com/PostView.naver?blogId=parent&logNo=123']
    rows = review_integrity.flag_duplicate_urls([{'academy_key':'A','source_url':u} for u in urls])
    assert sum(bool(r.get('is_excluded')) for r in rows) == 2
    assert review_integrity.canonical_document('https://example.org/?id=1') != review_integrity.canonical_document('https://example.org/?id=2')


def test_current_directory_title_requires_address_match():
    page = directory.parse_page('<title>황수비수학학원 대치점 | 강남엄마</title><meta name="description" content="소개, 서울 강남구 삼성로71길 25, 과목 수학">')
    reg = directory.Registry([{'id':'A','name':'황수비수학학원','dong':'대치동','road_address':'서울특별시 강남구 삼성로71길 25'}])
    assert directory.match_academy(page,reg) == 'A'
    assert directory.match_academy(dict(page,address='서울 강남구 삼성로71길 26'),reg) is None
    assert directory.match_academy(dict(page,address=None),reg) is None


def test_removed_evidence_cannot_survive_in_profile_cache(monkeypatch):
    result = {'curriculum': {'note':'수업 소개', 'quotes':[{'kind':'parent','urlHash':'bad'}]}}
    monkeypatch.setattr(profiles,'_load',lambda: {'A':{'result':result}})
    out = profiles.collect([{'id':'A'}], {'A':[{'url_hash':'bad','is_excluded':True}]}, {}, live=False)
    assert out == {}


def test_health_distinguishes_empty_success_and_disabled(monkeypatch,tmp_path):
    monkeypatch.setattr(source_health,'PATH',tmp_path/'health.json')
    source_health.reset()
    source_health.record('blog','available',0)
    source_health.record('web','disabled')
    source_health.save()
    assert source_health.load()['blog']['errors'] == 0
    assert source_health.load()['web']['errors'] == 1


def test_rate_limits_stop_after_three_requests(monkeypatch):
    class Resp:
        status_code=429
    calls=[]
    monkeypatch.setattr(naver,'resolve_mode',lambda:'hub')
    monkeypatch.setattr(naver,'_disabled_sources',set())
    monkeypatch.setattr(naver.requests,'get',lambda *a,**kw: calls.append(1) or Resp())
    monkeypatch.setattr(naver.time,'sleep',lambda *_: None)
    with pytest.raises(naver.NaverError): naver.search('naver_blog','대치')
    assert len(calls)==3
