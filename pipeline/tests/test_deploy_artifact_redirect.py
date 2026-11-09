"""Exercise the actual release redirect handler without credentials or network."""
import ast
from pathlib import Path
import urllib.request
from urllib.parse import urlsplit
import yaml


def handler():
    root = Path(__file__).resolve().parents[2]
    workflow = yaml.safe_load((root / '.github/workflows/deploy.yml').read_text())
    step = next(s for s in workflow['jobs']['build']['steps']
                if s.get('name') == '캐시 누락 시 성공 배포 artifact 복원')
    code = step['run'].split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]
    tree = ast.parse(code)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == 'SafeArtifactRedirect')
    scope = {'urllib': urllib, 'urlsplit': urlsplit}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), '<release redirect>', 'exec'), scope)
    return scope['SafeArtifactRedirect']()


def test_storage_redirect_drops_github_authorization():
    request = urllib.request.Request('https://api.github.com/repos/example/site/actions/artifacts/1/zip',
                                     headers={'Authorization': 'Bearer synthetic-test-only'})
    redirected = handler().redirect_request(request, None, 302, 'Found', {},
                                            'https://artifact.example.test/file.zip?signature=test')
    assert not redirected.has_header('Authorization')
    assert redirected.full_url.endswith('?signature=test')
    assert request.get_header('Authorization') == 'Bearer synthetic-test-only'


def test_same_origin_api_redirect_preserves_authentication():
    request = urllib.request.Request('https://api.github.com/old',
                                     headers={'Authorization': 'Bearer synthetic-test-only'})
    redirected = handler().redirect_request(request, None, 302, 'Found', {},
                                            'https://api.github.com/new')
    assert redirected.get_header('Authorization') == 'Bearer synthetic-test-only'
