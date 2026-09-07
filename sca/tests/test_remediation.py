import copy
import hashlib
import os
import time
import zipfile

import pytest
from ruamel.yaml import YAML

from sca.internal.guide import Guide, escape_markdown_cell
from sca.internal.loosening import Tailoring, TailoringException
from sca.internal.review import ReviewDecision, normalize_decisions
from sca.internal.sca import Check
from sca.services.export_service import export_policy
from sca.services.sca_service import get_checks, validate_sca_file
from sca.services.session_service import SessionService, contained_path
from sca.tests.helpers import app_with_session, baseline, write_yaml


def _load_zip_yaml(bundle, name):
    return YAML(typ='safe').load(bundle.read(name).decode('utf-8'))


def test_rationale_populated_empty_and_absent(tmp_path):
    data = baseline()
    data['checks'][1]['rationale'] = ''
    path = tmp_path / 'base.yml'
    write_yaml(path, data)
    guide = Guide(str(path))
    parsed = [Check.from_dict(item) for item in guide.__sca_yml__['checks']]
    assert parsed[0].rationale == 'A real rationale'
    assert parsed[1].rationale is None
    del data['checks'][1]['rationale']
    assert Check.from_dict(data['checks'][1]).rationale is None
    assert get_checks(guide)[1]['rationale'] == ''


def test_validation_rejects_incomplete_and_duplicate_checks(tmp_path):
    path = tmp_path / 'base.yml'
    data = baseline()
    data['checks'][1]['id'] = 1
    write_yaml(path, data)
    assert validate_sca_file(str(path)) == (False, 'Duplicate check ID: 1')
    data = baseline()
    data['checks'][0]['id'] = '1'
    write_yaml(path, data)
    valid, message = validate_sca_file(str(path))
    assert not valid and 'integer' in message


def test_validation_accepts_dotted_compliance_keys(tmp_path):
    data = baseline()
    data['checks'][0]['compliance'] = [
        {'cmmc_v2.0': ['AC.L1-3.1.1']},
        {'pci_dss_v3.2.1': ['7.1']},
        {'pci_dss_v4.0': ['7.1']},
    ]
    path = tmp_path / 'base.yml'
    write_yaml(path, data)
    assert validate_sca_file(str(path)) == (True, None)
    assert get_checks(Guide(str(path)))[0]['compliance'] == data['checks'][0]['compliance']


def test_decision_api_validation_and_normalized_stats(tmp_path):
    client = app_with_session(tmp_path)
    invalid = [None, {}, {'check_id': 1, 'decision': 'invalid'},
               {'check_id': 1, 'decision': 'exception', 'justification': 'short'}]
    for body in invalid:
        response = client.post('/api/decision', json=body)
        assert 400 <= response.status_code < 500
        with client.session_transaction() as sess:
            assert sess['decisions'] == {}
    assert client.post('/api/decision', data='{', content_type='application/json').status_code == 400
    assert client.post('/api/decision', json={'check_id': -1, 'decision': 'accepted'}).status_code == 404
    response = client.post('/api/decision', json={'check_id': '1', 'decision': 'accepted'})
    assert response.status_code == 200
    with client.session_transaction() as sess:
        assert sess['decisions']['1'] == {'decision': 'accepted'}
    response = client.post('/api/decision', json={
        'check_id': 1, 'decision': 'exception',
        'justification': 'Needed | for\nlegacy \\ app'})
    assert response.json['stats'] == {
        'total': 2, 'accepted': 0, 'exceptions': 1, 'not_applicable': 0,
        'unreviewed': 1, 'effective_included': 1, 'reviewed': 1,
        'review_completion': 50.0}


def test_decision_api_rejects_all_invalid_justification_types(tmp_path):
    client = app_with_session(tmp_path)
    for value in (None, 1, [], {}, 'x' * 1001):
        assert client.post('/api/decision', json={
            'check_id': 1, 'decision': 'exception', 'justification': value}).status_code == 400


def test_export_preserves_source_and_writes_provenance(tmp_path):
    source = baseline()
    original = copy.deepcopy(source)
    path = tmp_path / 'base.yml'
    write_yaml(path, source)
    guide = Guide(str(path))
    check = Check.from_dict(source['checks'][0])
    tailoring = Tailoring('Tâiloréd policy', 'tailored', 'Unicode – açıklama')
    tailoring.decisions[check.id] = TailoringException(
        justification='Needed | because\nlegacy \\ app',
        exception_check=check,
    )

    archive = export_policy(guide, tailoring, 'tailored', str(tmp_path / 'exports'))
    with zipfile.ZipFile(archive) as bundle:
        assert set(bundle.namelist()) == {
            'tailored.yml', 'tailored_exceptions.yml', 'tailored_exceptions.md'}
        tailored_bytes = bundle.read('tailored.yml')
        tailored = YAML(typ='safe').load(tailored_bytes.decode('utf-8'))
        record = _load_zip_yaml(bundle, 'tailored_exceptions.yml')
        markdown = bundle.read('tailored_exceptions.md').decode('utf-8')

    assert [check['id'] for check in tailored['checks']] == [2]
    assert tailored['checks'][0] == original['checks'][1]
    assert record['exceptions']['accepted_risk'][0]['check_id'] == 1
    assert record['exceptions']['accepted_risk'][0]['compliance'] == [{'cis': ['1.1']}]
    assert record['exceptions']['not_applicable'] == []
    assert len(record['baseline']['sha256']) == 64
    assert record['tailored_policy']['id'] == 'tailored'
    assert record['tailored_policy']['file'] == 'tailored.yml'
    assert record['tailored_policy']['sha256'] == hashlib.sha256(tailored_bytes).hexdigest()
    assert r'Needed \| because<br>legacy \\ app' in markdown
    assert YAML(typ='safe').load(path.read_text(encoding='utf-8')) == original


def test_markdown_escape():
    assert escape_markdown_cell('a|b\r\nc\\d') == r'a\|b<br>c\\d'


def test_markdown_export_neutralizes_uploaded_markup(tmp_path):
    source = baseline()
    source['policy']['name'] = '<img src=x onerror=alert(1)>'
    source['checks'][0]['title'] = '<script>alert(1)</script> [click](javascript:alert(1)) | row'
    path = tmp_path / 'base.yml'
    write_yaml(path, source)
    guide = Guide(str(path))
    check = Check.from_dict(source['checks'][0])
    tailoring = Tailoring('Safe [name](javascript:x)', 'safe', '<b>description</b>')
    tailoring.decisions[check.id] = TailoringException(
        justification='Needed because <img src=x onerror=alert(1)> [link](javascript:x)',
        exception_check=check,
    )

    archive = export_policy(guide, tailoring, 'safe', str(tmp_path / 'exports'))
    with zipfile.ZipFile(archive) as bundle:
        markdown = bundle.read('safe_exceptions.md').decode('utf-8')

    assert '<script>' not in markdown
    assert '<img ' not in markdown
    assert '<b>' not in markdown
    assert '](javascript:' not in markdown
    assert '&lt;script&gt;' in markdown
    assert r'\[click\]\(javascript:alert\(1\)\)' in markdown


@pytest.mark.parametrize('decision,justification,expected', [
    ('accepted', 'discarded text', {'decision': 'accepted'}),
    ('exception', 'A valid reason', {'decision': 'exception', 'justification': 'A valid reason'}),
])
def test_typed_decision_normalization(decision, justification, expected):
    value = ReviewDecision.create(1, decision, justification)
    assert value.to_session() == expected
    assert normalize_decisions({'1': expected, '999': expected}, {1}) == {1: value}


@pytest.mark.parametrize('decision,justification', [
    ('other', ''), ('exception', ''), ('exception', 'short'), ('exception', 12),
    ('accepted', 'x' * 1001), ('exception', '!' * 20),
    ('exception', 'aaaaaaaaaaaa'), ('exception', '..........'),
])
def test_typed_decision_rejects_invalid_values(decision, justification):
    with pytest.raises(ValueError):
        ReviewDecision.create(1, decision, justification)


def test_decision_api_rejects_meaningless_exception_justification(tmp_path):
    client = app_with_session(tmp_path)
    response = client.post('/api/decision', json={
        'check_id': 1, 'decision': 'exception', 'justification': '!' * 20})
    assert response.status_code == 400
    with client.session_transaction() as sess:
        assert sess['decisions'] == {}


def test_validation_rejects_nested_optional_types(tmp_path):
    path = tmp_path / 'base.yml'
    for field, value in [
        ('description', []), ('rationale', {}), ('rules', []),
        ('compliance', ['not-a-mapping']), ('compliance', [{'cis': '1.1'}]),
    ]:
        data = baseline()
        data['checks'][0][field] = value
        write_yaml(path, data)
        assert validate_sca_file(str(path))[0] is False


def test_multiple_exports_preserve_source(tmp_path):
    source = baseline([
        {'id': number, 'title': f'Check {number}', 'condition': 'all',
         'impact': 'Low', 'rules': [f'f:/{number}']}
        for number in range(1, 5)])
    path = tmp_path / 'base.yml'
    write_yaml(path, source)
    guide = Guide(str(path))
    tailoring = Tailoring('Tailored Policy', 'tailored', 'Description')
    for check_id in (1, 4):
        check = Check.from_dict(source['checks'][check_id - 1])
        tailoring.decisions[check_id] = TailoringException(
            justification=f'Valid reason for {check_id}',
            exception_check=check,
        )

    first = export_policy(guide, tailoring, 'first', str(tmp_path / 'exports'))
    second = export_policy(
        guide, Tailoring('Second Policy', 'second', 'Description'),
        'second', str(tmp_path / 'exports'))
    with zipfile.ZipFile(first) as bundle:
        assert [c['id'] for c in _load_zip_yaml(bundle, 'first.yml')['checks']] == [2, 3]
    with zipfile.ZipFile(second) as bundle:
        assert [c['id'] for c in _load_zip_yaml(bundle, 'second.yml')['checks']] == [1, 2, 3, 4]


def test_containment_and_expiry(tmp_path):
    root = tmp_path / 'owned'
    root.mkdir()
    assert contained_path(str(root), 'safe.yml').parent == root
    with pytest.raises(ValueError):
        contained_path(str(root), '../outside')
    with pytest.raises(ValueError):
        contained_path(str(root), str(tmp_path / 'outside'))
    expired = root / 'expired'
    active = root / 'active'
    expired.write_text('old', encoding='utf-8')
    active.write_text('new', encoding='utf-8')
    os.utime(expired, (time.time() - 7200, time.time() - 7200))
    SessionService.cleanup_expired([str(root)], 1)
    assert not expired.exists() and active.exists()


def test_export_route_rejects_corrupt_state_and_all_exceptions(tmp_path):
    client = app_with_session(tmp_path)
    with client.session_transaction() as sess:
        sess['decisions'] = {'1': {'decision': 'exception', 'justification': 'too short'}}
    assert client.post('/api/export').status_code == 400
    with client.session_transaction() as sess:
        sess['decisions'] = {
            '1': {'decision': 'exception', 'justification': 'A valid first reason'},
            '2': {'decision': 'exception', 'justification': 'A valid second reason'}}
    response = client.post('/api/export')
    assert response.status_code == 400
    assert 'remain included' in response.json['error']


def test_draft_round_trip_and_recovery(tmp_path):
    client = app_with_session(tmp_path)
    with client.session_transaction() as sess:
        session_id = sess['session_id']
    assert client.post('/api/decision', json={
        'check_id': 1, 'decision': 'accepted'}).status_code == 200
    with client.session_transaction() as sess:
        sess.clear()
    assert client.get(f'/recover/{session_id}').status_code == 302
    with client.session_transaction() as sess:
        assert sess['baseline_filename'] == 'base.yml'
        assert sess['sanitized_name'] == 'a_tailored_policy'
        assert sess['decisions']['1'] == {'decision': 'accepted'}


def test_parser_supported_fields_and_missing_optionals():
    parsed = Check.from_dict(baseline()['checks'][0])
    assert parsed.description is None
    assert parsed.rationale == 'A real rationale'
    assert parsed.remediation == 'Fix'
    assert parsed.references == ['ref']
    assert parsed.rules == ['f:/one']
    assert parsed.regex_type == 'pcre2'
    assert parsed.compliance[0]['cis'] == ['1.1']
