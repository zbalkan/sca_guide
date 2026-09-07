import uuid

import pytest

from sca.internal.sca import SCA
from sca.services.sca_service import validate_sca_file
from sca.services.session_service import SessionService
from sca.tests.helpers import app_with_session, baseline, write_yaml


def _draft_from_session(client):
    with client.session_transaction() as sess:
        session_id = sess['session_id']
        data = SessionService.serialize_session_data(
            sess['baseline_filename'],
            sess['custom_name'],
            sess['sanitized_name'],
            sess['custom_description'],
            sess['decisions'],
        )
    return session_id, data


def _store_and_clear(client, tmp_path, session_id, data):
    service = SessionService(str(tmp_path / 'drafts'))
    assert service.save_draft(session_id, data)
    with client.session_transaction() as sess:
        sess.clear()
    return service


def test_serialized_drafts_include_schema_version():
    data = SessionService.serialize_session_data(
        'base.yml', 'Tailored Policy', 'tailored_policy', 'Description', {})

    assert data['schema_version'] == 1


def test_recovery_rejects_unsupported_draft_schema(tmp_path):
    client = app_with_session(tmp_path)
    session_id, data = _draft_from_session(client)
    data['schema_version'] = 999
    _store_and_clear(client, tmp_path, session_id, data)

    response = client.get(f'/recover/{session_id}')

    assert response.status_code == 400
    assert response.json == {'error': 'Draft is invalid'}


def test_recovery_rejects_unknown_review_state(tmp_path):
    client = app_with_session(tmp_path)
    session_id, data = _draft_from_session(client)
    data['decisions'] = {'999': {'decision': 'accepted'}}
    _store_and_clear(client, tmp_path, session_id, data)

    response = client.get(f'/recover/{session_id}')

    assert response.status_code == 400
    assert response.json == {'error': 'Draft is invalid'}


def test_recovery_normalizes_valid_review_state(tmp_path):
    client = app_with_session(tmp_path)
    session_id, data = _draft_from_session(client)
    data['decisions'] = {
        '1': {'decision': 'accepted', 'justification': 'discarded text'},
    }
    _store_and_clear(client, tmp_path, session_id, data)

    response = client.get(f'/recover/{session_id}')

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess['decisions'] == {'1': {'decision': 'accepted'}}


def test_corrupt_draft_is_invalid_not_missing(tmp_path):
    client = app_with_session(tmp_path)
    with client.session_transaction() as sess:
        session_id = sess['session_id']
        sess.clear()

    draft_path = tmp_path / 'drafts' / f'{session_id}.json'
    draft_path.write_text('{not-json', encoding='utf-8')

    response = client.get(f'/recover/{session_id}')

    assert response.status_code == 400
    assert response.json == {'error': 'Draft is invalid'}


def test_missing_draft_remains_not_found(tmp_path):
    client = app_with_session(tmp_path)
    with client.session_transaction() as sess:
        sess.clear()

    response = client.get(f'/recover/{uuid.uuid4()}')

    assert response.status_code == 404
    assert response.json == {'error': 'Draft not found'}


def test_internal_projection_error_is_not_reported_as_bad_yaml(tmp_path, monkeypatch):
    path = tmp_path / 'policy.yml'
    write_yaml(path, baseline())

    def fail_projection(data):
        raise RuntimeError('projection failed')

    monkeypatch.setattr(SCA, 'from_dict', staticmethod(fail_projection))

    with pytest.raises(RuntimeError, match='projection failed'):
        validate_sca_file(str(path))
