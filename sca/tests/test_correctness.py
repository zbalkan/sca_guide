import io
import os
import time
import uuid

from sca.app import create_app
from sca.services.sca_service import validate_sca_file
from sca.services.session_service import SessionService
from sca.tests.helpers import baseline, write_yaml


def _validate(tmp_path, data):
    path = tmp_path / 'policy.yml'
    write_yaml(path, data)
    return validate_sca_file(str(path))


def test_requirements_condition_rejects_values_wazuh_cannot_evaluate(tmp_path):
    data = baseline()
    data['requirements']['condition'] = 'sometimes'

    valid, message = _validate(tmp_path, data)

    assert valid is False
    assert message == "requirements.condition must be 'all', 'any', or 'none'"


def test_variables_require_wazuh_variable_names(tmp_path):
    data = baseline()
    data['variables'] = {'sshd_file': '/etc/ssh/sshd_config'}

    valid, message = _validate(tmp_path, data)

    assert valid is False
    assert message == "variables keys must start with '$'"


def test_variables_reject_nested_values(tmp_path):
    data = baseline()
    data['variables'] = {'$sshd_file': {'path': '/etc/ssh/sshd_config'}}

    valid, message = _validate(tmp_path, data)

    assert valid is False
    assert message == 'variables values must be scalar or null'


def test_variables_allow_null_values_used_by_official_policies(tmp_path):
    data = baseline()
    data['variables'] = {'$User': None}

    assert _validate(tmp_path, data) == (True, None)


def test_startup_cleanup_keeps_baseline_for_recent_draft(tmp_path):
    uploads = tmp_path / 'uploads'
    drafts = tmp_path / 'drafts'
    exports = tmp_path / 'exports'
    sessions = tmp_path / 'sessions'
    for path in (uploads, drafts, exports, sessions):
        path.mkdir()

    session_id = str(uuid.uuid4())
    baseline_filename = f'{session_id}_base.yml'
    baseline_path = uploads / baseline_filename
    write_yaml(baseline_path, baseline())

    service = SessionService(str(drafts))
    assert service.save_draft(session_id, SessionService.serialize_session_data(
        baseline_filename,
        'Tailored Policy Name',
        'tailored_policy_name',
        'A tailored policy description that is long enough for validation.',
        {},
    ))

    expired = time.time() - 7200
    os.utime(baseline_path, (expired, expired))

    class TestConfig:
        TESTING = True
        SECRET_KEY = 'test'
        UPLOAD_FOLDER = str(uploads)
        DRAFT_FOLDER = str(drafts)
        EXPORT_FOLDER = str(exports)
        SESSION_FILE_DIR = str(sessions)
        FILE_TTL_HOURS = 1
        SESSION_TYPE = 'filesystem'
        SESSION_PERMANENT = True
        MAX_CONTENT_LENGTH = 16 * 1024 * 1024
        ALLOWED_EXTENSIONS = {'yml', 'yaml', 'zip'}

    create_app(TestConfig)

    assert baseline_path.exists()
    assert service.load_draft(session_id) is not None


def test_oversized_upload_returns_413_json(tmp_path):
    class TestConfig:
        TESTING = True
        SECRET_KEY = 'test'
        UPLOAD_FOLDER = str(tmp_path / 'uploads')
        DRAFT_FOLDER = str(tmp_path / 'drafts')
        EXPORT_FOLDER = str(tmp_path / 'exports')
        SESSION_FILE_DIR = str(tmp_path / 'sessions')
        FILE_TTL_HOURS = 48
        SESSION_TYPE = 'filesystem'
        SESSION_PERMANENT = True
        MAX_CONTENT_LENGTH = 512
        ALLOWED_EXTENSIONS = {'yml', 'yaml', 'zip'}

    client = create_app(TestConfig).test_client()
    response = client.post('/upload', data={
        'file': (io.BytesIO(b'x' * 2048), 'oversized.yml'),
        'custom_name': 'Oversized Policy Name',
        'custom_description': 'A policy description long enough to satisfy the form requirements.',
    }, content_type='multipart/form-data')

    assert response.status_code == 413
    assert response.json == {'error': 'File too large. Maximum size is 512 bytes.'}
