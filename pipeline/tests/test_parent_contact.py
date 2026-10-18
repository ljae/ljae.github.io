from pipeline.edutree.public_page_model import safe_url, safe_phone


def test_public_contact_policy_handles_real_number_shapes_without_inference():
    for value in ['02-1234-0000', '1588-1234', '+82 (2) 1234-5678']:
        assert safe_phone(value) == value
    for value in ['00000000', '전화 02-1234-5678', '02-1234-5678;123', '12345']:
        assert safe_phone(value) is None


def test_public_contact_urls_reject_unsafe_or_malformed_navigation():
    for value in ['javascript:alert(1)', 'data:text/plain,x', 'https://u:p@example.com',
                  'https://', 'https://exa mple.com', 'https://good.com\\@evil.com',
                  'https://example.com:abc', 'https://[bad']:
        assert safe_url(value) is None
    assert safe_url('https://example.com/a') == 'https://example.com/a'
