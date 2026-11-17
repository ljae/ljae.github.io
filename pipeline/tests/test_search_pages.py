"""Search landing pages must retain useful facts and stable identities."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pipeline.edutree.public_page_model import academy_model, validate_aliases
from pipeline.growth.inventory import inventory
from pipeline import seo


def academy(aid='100'):
    return dict(id=aid, name='테스트학원', displayName='테스트학원', regionId='banpo',
                address='서초구 예시로 10', subjects=['english'], capacity=50,
                registrationStatus='개원', registrationIds=[], gradeBands=['high'])


def test_registry_detail_keeps_unknown_facts_and_matches_metadata(tmp_path):
    a = academy()
    model = academy_model(a, evaluated=False)
    assert model['grades'] == []  # gradeBands with no evidence is insufficient.
    assert model['tuition']['amount'] is None
    assert model['contact']['phone'] is None
    urls = seo.academy_pages(tmp_path, [], [a], [{'id': 'banpo', 'name_ko': '반포'}])
    html = (tmp_path/'a/100.html').read_text()
    assert '대상 학년 미확인' in html
    assert '교습비, 정원' not in html
    assert 'tel:' not in html and 'aggregateRating' not in html
    assert '/#/academy/100?region=banpo' in html
    assert '트리스코어 0' not in html
    assert '<nav class="breadcrumb"' in html
    assert urls == ['https://openedu4u.com/a/100.html']


def test_basis_is_subject_specific_and_raw_codes_are_not_user_labels(tmp_path):
    a = academy()
    a['subjects'] = ['arts', 'general']
    a['gradeTarget'] = {'bandBasis': {'english': {'high': 'official'}}}
    assert academy_model(a, evaluated=True)['grades'] == []
    seo.academy_pages(tmp_path, [a], [], [{'id': 'banpo', 'name_ko': '반포'}])
    html = (tmp_path/'a/100.html').read_text()
    assert '예체능' in html and '과목 미확인' in html
    assert ' · arts' not in html and ' · general' not in html


def test_only_verified_aliases_generate_compatibility_pages(tmp_path):
    a = academy()
    a['registrationIds'] = ['99']
    row = dict(oldId='99', canonicalId='100', status='candidate')
    assert validate_aliases([row], {'100': a}) == {}
    row.update(status='verified', evidence={'address': 'same verified address'}, reviewedAt='2026-10-17')
    aliases = validate_aliases([row], {'100': a})
    urls = seo.academy_pages(tmp_path, [], [a], [{'id': 'banpo', 'name_ko': '반포'}], aliases=aliases)
    old = (tmp_path/'a/99.html').read_text()
    assert 'href="https://openedu4u.com/a/100.html"' in old
    assert '통합되었습니다' in old
    assert 'https://openedu4u.com/a/99.html' not in urls
    with pytest.raises(ValueError):
        validate_aliases([row, row], {'100': a})
    row['canonicalId'] = 'missing'
    with pytest.raises(ValueError):
        validate_aliases([row], {'100': a})


def test_semantic_lastmod_changes_only_with_substantive_content(tmp_path):
    url = 'https://openedu4u.com/'
    html = '<link rel="canonical" href="https://openedu4u.com/"><main>내용</main><p data-generated-at="true">2026-10-17</p>'
    file = tmp_path/'index.html'
    file.write_text(html)
    first = inventory(tmp_path, [url], today='2026-10-17')
    assert first['pages'][url]['semanticUpdatedAt'] is None
    file.write_text(html.replace('2026-10-17', '2026-10-18'))
    second = inventory(tmp_path, [url], previous=first, today='2026-10-18')
    assert second['pages'][url]['semanticUpdatedAt'] is None
    file.write_text(html.replace('내용', '새 주요 내용'))
    third = inventory(tmp_path, [url], previous=second, today='2026-10-19')
    assert third['pages'][url]['semanticUpdatedAt'] == '2026-10-19'
    fourth = inventory(tmp_path, [url], previous=third, today='2026-10-20')
    assert fourth['pages'][url]['semanticUpdatedAt'] == '2026-10-19'
    seo.write_sitemap(tmp_path, [url], fourth)
    assert '<lastmod>2026-10-19</lastmod>' in (tmp_path/'sitemap.xml').read_text()


def test_inventory_fails_on_removed_urls_and_broken_app_routes(tmp_path):
    (tmp_path/'index.html').write_text('<link rel="canonical" href="https://openedu4u.com/">')
    previous = {'pages': {'https://openedu4u.com/a/99.html': {}}}
    with pytest.raises(ValueError, match='UNEXPECTED_URL_REMOVAL'):
        inventory(tmp_path, ['https://openedu4u.com/'], previous=previous)
    (tmp_path/'index.html').write_text('<link rel="canonical" href="https://openedu4u.com/"><a href="/#/academy/99">상세</a>')
    with pytest.raises(ValueError, match='BROKEN_INTERNAL_LINKS'):
        inventory(tmp_path, ['https://openedu4u.com/'])


def test_inventory_preserves_compatibility_urls_between_deployments(tmp_path):
    (tmp_path/'a').mkdir()
    url = 'https://openedu4u.com/a/100.html'
    html = f'<link rel="canonical" href="{url}">'
    (tmp_path/'a/100.html').write_text(html)
    (tmp_path/'a/99.html').write_text(html)
    first = inventory(tmp_path, [url], aliases={'99': '100'})
    (tmp_path/'a/99.html').unlink()
    with pytest.raises(ValueError, match='UNEXPECTED_URL_REMOVAL'):
        inventory(tmp_path, [url], previous=first)
    with pytest.raises(ValueError, match='INVALID_COMPATIBILITY_PAGE'):
        inventory(tmp_path, [url], previous=first, aliases={'99': '100'})


def test_reviewed_unavailable_page_preserves_url_without_stale_claims(tmp_path):
    url = 'https://openedu4u.com/'
    old = 'https://openedu4u.com/a/99.html'
    (tmp_path/'index.html').write_text(f'<link rel="canonical" href="{url}">')
    row = dict(id='99', name='이전 학원', status='reviewed', reviewedAt='2026-10-18', evidence={'prior': 'deployed snapshot'})
    notices = seo.unavailable_academy_pages(tmp_path, [row], {}, {})
    html = (tmp_path/'a/99.html').read_text()
    assert 'noindex, follow' in html
    assert '폐원이나 이전을 확인한 것은 아닙니다' in html
    assert 'tel:' not in html and 'aggregateRating' not in html
    first = inventory(tmp_path, [url], previous={'pages': {old: {}}}, notices=notices)
    assert first['unavailableUrls'] == {old: '2026-10-18'}
    assert old not in first['pages']
    with pytest.raises(ValueError, match='UNEXPECTED_URL_REMOVAL'):
        inventory(tmp_path, [url], previous=first)
    (tmp_path/'a/99.html').write_text(html.replace('noindex, follow', 'index, follow'))
    with pytest.raises(ValueError, match='INVALID_UNAVAILABLE_PAGE'):
        inventory(tmp_path, [url], notices=notices)
    assert seo.unavailable_academy_pages(tmp_path, [row], {'99': academy('99')}, {}) == {}
    with pytest.raises(ValueError, match='UNREVIEWED_MERGED_ID'):
        seo.unavailable_academy_pages(tmp_path, [row], {'100': {**academy(), 'registrationIds': ['99']}}, {})


def test_search_snippet_pilot_uses_recorded_facts_and_keeps_controls():
    a=academy('100');a['address']='서울특별시 서초구 예시로 10'
    a['gradeTarget']={'bandBasis':{'english':{'high':'official'}}}
    m=academy_model(a,evaluated=False)
    title,desc=seo.search_metadata(a,m,'반포',{'100'})
    assert '영어' in title and a['address'] in desc
    assert '공식 안내' in desc
    assert '후기' not in title+desc and '추천' not in title+desc
    old_title,old_desc=seo.search_metadata(a,m,'반포',set())
    assert old_title=='테스트학원 · 반포 학원 정보 | 학원실록'
    assert old_desc=='반포 테스트학원의 주소와 공시 등록 정보를 살펴보세요. 대상: 영어 고등.'
    a['gradeTarget']={};a['subjects']=['general'];a['tel']=None
    title,desc=seo.search_metadata(a,academy_model(a,evaluated=False),'반포',{'100'})
    assert '대상:' not in desc and '영어' not in desc and '전화:' not in desc


def test_analytics_instrumentation_does_not_fake_article_freshness():
    from pipeline.growth.inventory import semantic_hash
    old='<head></head><main>Academy facts</main>'
    new=old.replace('</head>', '\n<!-- analytics:non-content:start --><script defer src="/analytics.js"></script><!-- analytics:non-content:end --></head>')
    assert semantic_hash(old)==semantic_hash(new)
    assert semantic_hash(new.replace('Academy facts','New verified academy facts'))!=semantic_hash(old)


def test_current_pilot_and_recovered_identity_inputs_have_public_evidence():
    root=Path(__file__).resolve().parents[2]
    entities={str(a['id']):a for f in ['academies','registry'] for a in json.loads((root/'app/assets/data'/f'{f}.json').read_text())}
    pilot=json.loads((root/'pipeline/data/search_content_pilot.json').read_text())
    assert len(pilot['treatmentIds'])==4 and not set(pilot['treatmentIds'])&set(pilot['controlIds'])
    # The experiment keeps its original assignments when a registration drops
    # out of a later NEIS snapshot. Only current entities receive snippets;
    # URL continuity is checked separately against the deployed manifest.
    for aid in set(pilot['treatmentIds']) & entities.keys():
        assert entities[aid]['address'] and set(entities[aid]['subjects'])-{'general'}
    mappings=json.loads((root/'pipeline/data/url_aliases.json').read_text())['entries']
    reviewed=validate_aliases(mappings,entities)
    assert reviewed['3000052565']=='3000030824'
    assert reviewed['3000052139']=='3000052110'


def test_missing_pilot_registration_does_not_block_or_create_a_phantom_page(tmp_path):
    pilot_path = seo.ROOT / 'pipeline/data/search_content_pilot.json'
    before = pilot_path.read_bytes()
    pilot = json.loads(before)
    present, absent = pilot['treatmentIds'][:2]
    urls = seo.academy_pages(tmp_path, [], [academy(present)],
                             [{'id': 'banpo', 'name_ko': '반포'}])
    assert urls == [f'{seo.SITE}/a/{present}.html']
    assert not (tmp_path / 'a' / f'{absent}.html').exists()
    assert pilot_path.read_bytes() == before  # Do not silently reassign the cohort.


def test_subject_directories_link_every_academy_including_unknown_subjects(tmp_path):
    from pipeline.growth.inventory import PageParser
    regions = [{'id': 'banpo', 'name_ko': '반포'}]
    rows = [academy(str(i)) for i in range(100, 112)]
    rows[0]['subjects'] = ['english', 'math']
    rows[1]['subjects'] = []
    rows[2]['subjects'] = ['general']
    rows[3]['subjects'] = ['unrecognized']
    rows[-1]['name'] = rows[-1]['displayName'] = '학원 <안내> & 상담'
    urls = seo.subject_pages(tmp_path, regions, rows[:5], rows[5:])
    assert set(urls) == {f'{seo.SITE}/g/banpo/{s}.html' for s in ('english', 'math', 'general')}
    linked = set()
    for url in urls:
        document = (tmp_path / url.removeprefix(seo.SITE + '/')).read_text()
        parser = PageParser()
        parser.feed(document)
        assert parser.canonical == url and not parser.noindex
        links = [link for link in parser.links if link.startswith('/a/')]
        assert len(links) == len(set(links))
        linked.update(links)
        assert 'aggregateRating' not in document
        assert 'ItemListUnordered' in document
        import re
        data = [json.loads(block) for block in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', document, re.S)]
        listing = next(block['mainEntity'] for block in data if block.get('@type') == 'CollectionPage')
        assert listing['numberOfItems'] == len(links)
        assert [item['url'] for item in listing['itemListElement']] == [seo.SITE + link for link in links]
    assert linked == {f'/a/{a["id"]}.html' for a in rows}
    english = (tmp_path / 'g/banpo/english.html').read_text()
    assert '학원 &lt;안내&gt; &amp; 상담' in english
    unknown = (tmp_path / 'g/banpo/general.html').read_text()
    assert '과목 미확인' in unknown and 'unrecognized' not in unknown


def test_region_hubs_offer_static_subject_links_and_keep_app_action(tmp_path):
    regions = [{'id': 'banpo', 'name_ko': '반포', 'dong_list': ['반포동']}]
    rows = [academy(), {**academy('101'), 'subjects': ['general']}]
    seo.region_pages(tmp_path, regions, [], rows, [], {})
    document = (tmp_path / 'g/banpo.html').read_text()
    assert 'href="/g/banpo/english.html"' in document
    assert 'href="/g/banpo/general.html"' in document
    assert 'href="/#/rank?region=banpo"' in document
    assert '</li><ul>' not in document


def test_browse_page_connects_regions_subjects_and_learning_tracks(tmp_path):
    from pipeline.growth.inventory import PageParser
    regions = [{'id': 'banpo', 'name_ko': '반포', 'dong_list': ['반포동']}]
    tracks = [{'id': 'english_middle', 'title': '중등 영어', 'grade_band': 'middle'}]
    urls = seo.browse_page(tmp_path, regions, [], [academy()], tracks)
    parser = PageParser()
    parser.feed((tmp_path / 'browse/index.html').read_text())
    assert urls == [f'{seo.SITE}/browse/'] and parser.canonical == urls[0]
    assert {'/g/banpo.html', '/g/banpo/english.html', '/t/english_middle.html'} <= set(parser.links)
    assert '/g/banpo/math.html' not in parser.links


def test_search_metadata_includes_consistent_accessible_share_cards():
    from html.parser import HTMLParser
    class Metadata(HTMLParser):
        def __init__(self):
            super().__init__()
            self.values = {}
        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == 'meta':
                self.values[a.get('name') or a.get('property')] = a.get('content')
    title, desc = '학원 <안내> & 비교', '주소와 "등록 정보"'
    document = seo.page(title, desc, f'{seo.SITE}/g/banpo.html', '<h1>반포</h1>')
    parser = Metadata()
    parser.feed(document)
    assert parser.values['twitter:title'] == parser.values['og:title'] == title
    assert parser.values['twitter:description'] == parser.values['description'] == desc
    assert parser.values['twitter:image'] == parser.values['og:image']
    assert parser.values['twitter:image:alt'] == parser.values['og:image:alt']
    assert parser.values['og:image:width'] == '1200'
    assert parser.values['og:image:height'] == '630'


def test_homepage_has_useful_html_navigation_before_flutter_loads():
    from pipeline.growth.inventory import PageParser
    document = (seo.ROOT / 'app/web/index.html').read_text()
    parser = PageParser()
    parser.feed(document)
    assert '/browse/' in parser.links
    assert all(f'/g/{region}.html' in parser.links for region in ('daechi', 'mokdong', 'banpo', 'jamsil'))
    assert '학원 정보를<br>불러오고 있어요</h1>' not in document


def test_reachability_gate_does_not_treat_app_hash_links_as_directory_links(tmp_path):
    home, detail = f'{seo.SITE}/', f'{seo.SITE}/a/100.html'
    (tmp_path / 'a').mkdir()
    (tmp_path / 'a/100.html').write_text(f'<link rel="canonical" href="{detail}">')
    template = f'<link rel="canonical" href="{home}"><a href="{{}}">학원 정보</a>'
    (tmp_path / 'index.html').write_text(template.format('/#/academy/100'))
    with pytest.raises(ValueError, match='UNREACHABLE_SEARCH_PAGES'):
        inventory(tmp_path, [home, detail], require_reachable=True)
    (tmp_path / 'index.html').write_text(template.format('/a/100.html'))
    result = inventory(tmp_path, [home, detail], require_reachable=True)
    assert not result['issues']
