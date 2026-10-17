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
