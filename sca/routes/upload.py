"""Upload and draft lifecycle routes."""
import hashlib
import logging
import os
import re
import uuid
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from flask import Blueprint, Response, current_app, jsonify, redirect, render_template, request, session, url_for
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename
from werkzeug.wrappers.response import Response as wResponse

from sca.internal.guide import Guide
from sca.internal.review import normalize_decisions
from sca.services.sca_service import validate_sca_file
from sca.services.session_service import DRAFT_SCHEMA_VERSION, SessionService, contained_path

upload_bp = Blueprint('upload', __name__)
logger = logging.getLogger(__name__)
MAX_ZIP_MEMBERS = 128


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']


def sanitize_policy_name(name: str) -> str:
    sanitized = re.sub(r'[^a-z0-9\s\-_]', '', name.lower())
    sanitized = re.sub(r'[\s\-]+', ' ', sanitized).strip().replace(' ', '_')
    return re.sub(r'^_+|_+$', '', sanitized)


def _read_zip_member(archive: zipfile.ZipFile, member: zipfile.ZipInfo,
                     max_size: int, label: str) -> bytes:
    if member.file_size > max_size:
        raise ValueError(f'{label} in ZIP exceeds the maximum upload size')
    with archive.open(member) as source:
        data = source.read(max_size + 1)
    if len(data) > max_size:
        raise ValueError(f'{label} in ZIP exceeds the maximum upload size')
    return data


def _validate_export_digest(archive: zipfile.ZipFile,
                            yaml_members: list[zipfile.ZipInfo],
                            policy: zipfile.ZipInfo, policy_data: bytes,
                            max_size: int) -> None:
    record_stem = f'{Path(policy.filename).stem.lower()}_exceptions'
    records = [
        item for item in yaml_members
        if Path(item.filename).stem.lower() == record_stem
    ]
    if not records:
        return
    if len(records) != 1:
        raise ValueError('ZIP contains ambiguous exception records')

    record_data = _read_zip_member(archive, records[0], max_size, 'Exception record')
    try:
        record = YAML(typ='safe').load(record_data.decode('utf-8'))
    except (UnicodeDecodeError, YAMLError) as error:
        raise ValueError('Invalid exception record in ZIP') from error
    if not isinstance(record, Mapping):
        raise ValueError('Invalid exception record in ZIP')

    tailored = record.get('tailored_policy')
    if not isinstance(tailored, Mapping):
        raise ValueError('Invalid exception record in ZIP')

    expected_digest = tailored.get('sha256')
    if expected_digest is None:
        return
    if (not isinstance(expected_digest, str)
            or re.fullmatch(r'[0-9a-fA-F]{64}', expected_digest) is None):
        raise ValueError('Invalid tailored policy SHA-256 in exception record')

    recorded_file = tailored.get('file')
    if (not isinstance(recorded_file, str)
            or Path(recorded_file).name != Path(policy.filename).name):
        raise ValueError('ZIP policy does not match exception record')

    actual_digest = hashlib.sha256(policy_data).hexdigest()
    if actual_digest != expected_digest.lower():
        raise ValueError('ZIP policy SHA-256 does not match exception record')


def _save_uploaded_policy(file: FileStorage, session_id: str) -> str:
    filename = secure_filename(file.filename or '')
    upload_root = current_app.config['UPLOAD_FOLDER']
    if not filename.lower().endswith('.zip'):
        path = os.path.join(upload_root, f'{session_id}_{filename}')
        file.save(path)
        return path

    try:
        with zipfile.ZipFile(file.stream) as archive:
            members = archive.infolist()
            if len(members) > MAX_ZIP_MEMBERS:
                raise ValueError('ZIP contains too many files')
            yaml_members = [
                item for item in members
                if not item.is_dir() and Path(item.filename).suffix.lower() in {'.yml', '.yaml'}
            ]
            stems = {Path(item.filename).stem.lower() for item in yaml_members}
            policies = [
                item for item in yaml_members
                if not (
                    Path(item.filename).stem.lower().endswith('_exceptions')
                    and Path(item.filename).stem.lower()[:-11] in stems
                )
            ]
            if len(policies) != 1:
                raise ValueError('ZIP must contain exactly one policy YAML file')

            policy = policies[0]
            max_size = current_app.config['MAX_CONTENT_LENGTH']
            data = _read_zip_member(archive, policy, max_size, 'Policy YAML')
            _validate_export_digest(archive, yaml_members, policy, data, max_size)

            member_name = secure_filename(Path(policy.filename).name)
            path = os.path.join(upload_root, f'{session_id}_{member_name}')
            with open(path, 'wb') as destination:
                destination.write(data)
            return path
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
        raise ValueError('Invalid or unsupported ZIP archive') from error


@upload_bp.route('/')
def index() -> str:
    drafts: list[dict[str, Any]] = SessionService(current_app.config['DRAFT_FOLDER']).list_drafts()
    return render_template('index.html', drafts=drafts)


@upload_bp.route('/upload', methods=['POST'])
def upload_file() -> tuple[Response, Literal[400]] | Response | tuple[Response, Literal[500]]:
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file: FileStorage = request.files['file']
        if not file.filename:
            return jsonify({'error': 'No file selected'}), 400
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Use .yml, .yaml, or an exported .zip file'}), 400

        custom_name = request.form.get('custom_name', '').strip()
        custom_description = request.form.get('custom_description', '').strip()
        if not 15 <= len(custom_name) <= 100:
            return jsonify({'error': 'Policy name must be between 15 and 100 characters'}), 400
        if not 50 <= len(custom_description) <= 500:
            return jsonify({'error': 'Policy description must be between 50 and 500 characters'}), 400

        session_id = str(uuid.uuid4())
        try:
            filepath = _save_uploaded_policy(file, session_id)
        except ValueError as error:
            return jsonify({'error': str(error)}), 400

        try:
            is_valid, error_msg = validate_sca_file(filepath)
            if not is_valid:
                os.remove(filepath)
                return jsonify({'error': f'Invalid SCA file: {error_msg}'}), 400

            sanitized_name = sanitize_policy_name(custom_name)
            if not sanitized_name:
                os.remove(filepath)
                return jsonify({'error': 'Policy name contains no valid characters for filename'}), 400

            baseline_filename = os.path.basename(filepath)
            draft_data = SessionService.serialize_session_data(
                baseline_filename, custom_name, sanitized_name, custom_description, {}
            )
            if not SessionService(current_app.config['DRAFT_FOLDER']).save_draft(
                    session_id, draft_data):
                os.remove(filepath)
                return jsonify({'error': 'Unable to persist review draft.'}), 500

            session.update(
                session_id=session_id,
                baseline_filename=baseline_filename,
                custom_name=custom_name,
                sanitized_name=sanitized_name,
                custom_description=custom_description,
                decisions={},
            )
            session.permanent = True
            return jsonify({
                'success': True,
                'redirect': url_for('review.review_page'),
                'recovery_url': url_for('upload.recover_draft', session_id=session_id),
            })
        except Exception:
            if os.path.exists(filepath):
                os.remove(filepath)
            raise
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unable to upload SCA file")
        return jsonify({'error': 'Unable to process SCA file.'}), 500


@upload_bp.route('/recover/<session_id>')
def recover_draft(session_id: str) -> tuple[Response, Literal[404]] | tuple[Response, Literal[410]] | wResponse | tuple[Response, Literal[400]]:
    service = SessionService(current_app.config['DRAFT_FOLDER'])
    try:
        data = service.load_draft(session_id, strict=True)
    except ValueError:
        logger.warning("Invalid draft data for %s", session_id, exc_info=True)
        return jsonify({'error': 'Draft is invalid'}), 400
    if data is None:
        return jsonify({'error': 'Draft not found'}), 404

    try:
        schema_version = data.get('schema_version', DRAFT_SCHEMA_VERSION)
        if type(schema_version) is not int or schema_version != DRAFT_SCHEMA_VERSION:
            raise ValueError("Unsupported draft schema version")

        filename = data['baseline_filename']
        if not isinstance(filename, str) or not filename:
            raise ValueError("Invalid baseline filename")
        path = contained_path(current_app.config['UPLOAD_FOLDER'], filename)
        if not path.is_file():
            return jsonify({'error': 'Draft baseline is no longer available'}), 410

        for field in ('custom_name', 'sanitized_name', 'custom_description'):
            if not isinstance(data.get(field), str) or not data[field].strip():
                raise ValueError(f"Invalid draft field: {field}")

        guide = Guide(str(path))
        baseline_ids = {check.id for check in guide.sca.checks}
        normalized = normalize_decisions(
            data.get('decisions', {}), baseline_ids, strict=True)
        decisions = {
            str(check_id): decision.to_session()
            for check_id, decision in normalized.items()
        }

        session.clear()
        session.update(
            session_id=session_id,
            baseline_filename=filename,
            custom_name=data['custom_name'],
            sanitized_name=data['sanitized_name'],
            custom_description=data['custom_description'],
            decisions=decisions,
        )
        session.permanent = True
        return redirect(url_for('review.review_page'))
    except (KeyError, TypeError, ValueError):
        logger.warning("Invalid draft data for %s", session_id, exc_info=True)
        return jsonify({'error': 'Draft is invalid'}), 400


@upload_bp.route('/api/drafts/<session_id>', methods=['DELETE'])
def delete_draft(session_id: str) -> Response | tuple[Response, Literal[400]] | tuple[Response, Literal[404]] | tuple[Response, Literal[500]]:
    service = SessionService(current_app.config['DRAFT_FOLDER'])
    try:
        session_id = service.validate_session_id(session_id)
    except ValueError:
        return jsonify({'error': 'Invalid draft identifier'}), 400

    data = service.load_draft(session_id)
    if data is None:
        return jsonify({'error': 'Draft not found'}), 404

    try:
        baseline_path = None
        baseline_filename = data.get('baseline_filename')
        if isinstance(baseline_filename, str):
            baseline_path = contained_path(current_app.config['UPLOAD_FOLDER'], baseline_filename)

        if not service.delete_draft(session_id):
            return jsonify({'error': 'Unable to delete draft'}), 500

        if baseline_path is not None:
            try:
                baseline_path.unlink(missing_ok=True)
            except OSError:
                logger.warning('Unable to remove baseline for deleted draft %s', session_id, exc_info=True)

        if session.get('session_id') == session_id:
            session.clear()
        return jsonify({'success': True, 'session_id': session_id})
    except (TypeError, ValueError):
        logger.warning('Invalid persisted path for draft %s', session_id, exc_info=True)
        return jsonify({'error': 'Draft is invalid'}), 400
    except Exception:
        logger.exception('Unable to delete draft %s', session_id)
        return jsonify({'error': 'Unable to delete draft'}), 500
