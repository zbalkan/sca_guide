import zipfile

import pytest
from ruamel.yaml import YAML

from sca.internal.guide import Guide
from sca.internal.loosening import Tailoring, TailoringRemoval
from sca.internal.review import DecisionType, ReviewDecision
from sca.services.export_service import export_policy
from sca.services.sca_service import calculate_stats
from sca.tests.helpers import app_with_session, baseline, write_yaml


def _three_check_baseline():
    data = baseline()
    data['checks'].append({
        'id': 3,
        'title': 'Three',
        'condition': 'all',
        'impact': 'Medium',
        'rules': ['f:/three'],
        'compliance': [{'pci_dss_v4.0': ['2.2.1']}],
    })
    return data


def test_not_applicable_requires_a_meaningful_justification():
    decision = ReviewDecision.create(
        1, 'not_applicable', 'This control does not apply to this server role.')
    assert decision.decision is DecisionType.NOT_APPLICABLE
    assert decision.to_session() == {
        'decision': 'not_applicable',
        'justification': 'This control does not apply to this server role.',
    }

    for justification in ('', 'short', '!!!!!!!!!!!!'):
        with pytest.raises(ValueError):
            ReviewDecision.create(1, 'not_applicable', justification)


def test_stats_distinguish_exception_and_not_applicable(tmp_path):
    path = tmp_path / 'base.yml'
    write_yaml(path, _three_check_baseline())
    guide = Guide(str(path))
    decisions = {
        '1': {'decision': 'exception', 'justification': 'Risk is accepted for this legacy host.'},
        '2': {'decision': 'not_applicable',
              'justification': 'This control does not apply to this server role.'},
        '3': {'decision': 'accepted'},
    }

    assert calculate_stats(guide, decisions) == {
        'total': 3,
        'accepted': 1,
        'exceptions': 1,
        'not_applicable': 1,
        'unreviewed': 0,
        'effective_included': 1,
        'reviewed': 3,
        'review_completion': 100.0,
    }


def test_decision_api_persists_not_applicable(tmp_path):
    client = app_with_session(tmp_path)
    response = client.post('/api/decision', json={
        'check_id': 1,
        'decision': 'not_applicable',
        'justification': 'This control does not apply to this server role.',
    })

    assert response.status_code == 200
    assert response.json['decision'] == {
        'decision': 'not_applicable',
        'justification': 'This control does not apply to this server role.',
    }
    assert response.json['stats']['not_applicable'] == 1
    assert response.json['stats']['effective_included'] == 1
    with client.session_transaction() as sess:
        assert sess['decisions']['1'] == response.json['decision']


def test_not_applicable_survives_draft_recovery(tmp_path):
    client = app_with_session(tmp_path)
    with client.session_transaction() as sess:
        session_id = sess['session_id']

    response = client.post('/api/decision', json={
        'check_id': 1,
        'decision': 'not_applicable',
        'justification': 'This control does not apply to this server role.',
    })
    assert response.status_code == 200

    with client.session_transaction() as sess:
        sess.clear()

    assert client.get(f'/recover/{session_id}').status_code == 302
    with client.session_transaction() as sess:
        assert sess['decisions']['1'] == {
            'decision': 'not_applicable',
            'justification': 'This control does not apply to this server role.',
        }


def test_mixed_removals_cannot_remove_every_check(tmp_path):
    client = app_with_session(tmp_path)
    with client.session_transaction() as sess:
        sess['decisions'] = {
            '1': {
                'decision': 'exception',
                'justification': 'Risk is accepted for this legacy host.',
            },
            '2': {
                'decision': 'not_applicable',
                'justification': 'This control does not apply to this server role.',
            },
        }

    response = client.post('/api/export')
    assert response.status_code == 400
    assert 'remain included' in response.json['error']


def test_export_splits_removed_checks_and_preserves_compliance(tmp_path):
    source = _three_check_baseline()
    path = tmp_path / 'base.yml'
    write_yaml(path, source)
    guide = Guide(str(path))
    tailoring = Tailoring('Tailored Policy', 'tailored', 'Description')
    tailoring.decisions[1] = TailoringRemoval(
        decision=DecisionType.EXCEPTION,
        justification='Risk is accepted for this legacy host.',
        check=guide.sca.checks[0],
    )
    tailoring.decisions[2] = TailoringRemoval(
        decision=DecisionType.NOT_APPLICABLE,
        justification='This control does not apply to this server role.',
        check=guide.sca.checks[1],
    )

    archive = export_policy(guide, tailoring, 'tailored', str(tmp_path / 'exports'))
    with zipfile.ZipFile(archive) as bundle:
        tailored = YAML(typ='safe').load(bundle.read('tailored.yml').decode('utf-8'))
        record = YAML(typ='safe').load(
            bundle.read('tailored_exceptions.yml').decode('utf-8'))
        markdown = bundle.read('tailored_exceptions.md').decode('utf-8')

    assert [check['id'] for check in tailored['checks']] == [3]
    assert record['exceptions']['accepted_risk'] == [{
        'check_id': 1,
        'title': 'One | first',
        'justification': 'Risk is accepted for this legacy host.',
        'compliance': [{'cis': ['1.1']}],
    }]
    assert record['exceptions']['not_applicable'] == [{
        'check_id': 2,
        'title': 'Two',
        'justification': 'This control does not apply to this server role.',
        'compliance': [],
    }]
    assert '## Accepted Risk Exceptions' in markdown
    assert '## Not Applicable' in markdown
    assert r'cis: 1.1' in markdown


def test_review_page_exposes_third_decision_and_filter(tmp_path):
    client = app_with_session(tmp_path)
    response = client.get('/review')
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'value="not_applicable"' in html
    assert 'Not Applicable' in html


def test_approval_page_distinguishes_not_applicable(tmp_path):
    client = app_with_session(tmp_path)
    with client.session_transaction() as sess:
        sess['decisions'] = {
            '1': {
                'decision': 'not_applicable',
                'justification': 'This control does not apply to this server role.',
            },
            '2': {'decision': 'accepted'},
        }

    response = client.get('/approval')
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'Not Applicable' in html
    assert 'This control does not apply to this server role.' in html
