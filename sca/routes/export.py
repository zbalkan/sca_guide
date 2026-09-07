"""Export routes."""
import logging
import os
from datetime import datetime, timezone
from typing import Literal

from flask import Blueprint, current_app, jsonify, redirect, render_template, send_file, session, url_for
from flask.wrappers import Response
from werkzeug import Response as wResponse

from sca.internal.guide import Guide
from sca.internal.loosening import Tailoring, TailoringRemoval
from sca.internal.review import DecisionType, ReviewDecision, normalize_decisions
from sca.routes.upload import sanitize_policy_name
from sca.services.export_service import cleanup_export, export_policy
from sca.services.sca_service import calculate_stats, get_checks
from sca.services.session_service import SessionService, contained_path

export_bp = Blueprint('export', __name__)
logger = logging.getLogger(__name__)


def _baseline_path() -> str:
    return str(contained_path(current_app.config['UPLOAD_FOLDER'], session['baseline_filename']))


@export_bp.route('/approval')
def approval_page() -> wResponse | str:
    if 'session_id' not in session or 'baseline_filename' not in session:
        return redirect(url_for('upload.index'))
    try:
        guide = Guide(_baseline_path())
        checks = get_checks(guide)
        decisions = session.get('decisions', {})
        baseline_ids = {check['id'] for check in checks}
        try:
            normalized = normalize_decisions(decisions, baseline_ids, strict=True)
        except ValueError:
            return redirect(url_for('review.review_page'))
        if set(normalized) != baseline_ids:
            return redirect(url_for('review.review_page'))

        def removed_checks(kind: DecisionType) -> list[dict[str, object]]:
            return [
                {
                    'id': check['id'],
                    'title': check['title'],
                    'justification': normalized[check['id']].justification or '',
                    'compliance': check['compliance'],
                }
                for check in checks
                if normalized[check['id']].decision is kind
            ]

        return render_template(
            'approval.html',
            custom_name=session.get('custom_name'),
            custom_description=session.get('custom_description'),
            stats=calculate_stats(guide, decisions),
            exception_checks=removed_checks(DecisionType.EXCEPTION),
            not_applicable_checks=removed_checks(DecisionType.NOT_APPLICABLE),
        )
    except Exception:
        logger.exception("Unable to load approval page")
        raise


@export_bp.route('/api/export', methods=['POST'])
def export_files() -> tuple[Response, Literal[400]] | Response | tuple[Response, Literal[500]]:
    if 'session_id' not in session or 'baseline_filename' not in session:
        return jsonify({'error': 'No active session'}), 400

    try:
        guide = Guide(_baseline_path())
        decisions = session.get('decisions', {})
        baseline_ids = {check.id for check in guide.sca.checks}
        try:
            normalized: dict[int, ReviewDecision] = normalize_decisions(
                decisions, baseline_ids, strict=True)
        except ValueError:
            return jsonify({'error': 'Review state is invalid; review the affected checks again.'}), 400

        if set(normalized) != baseline_ids:
            return jsonify({'error': 'All checks must be reviewed before export.'}), 400

        removed_ids = {
            check_id for check_id, value in normalized.items()
            if value.decision.removes_check
        }
        if removed_ids == baseline_ids:
            return jsonify({'error': 'At least one check must remain included'}), 400

        custom_name = session.get('custom_name')
        custom_description = session.get('custom_description')
        sanitized_name = session.get('sanitized_name')
        if not isinstance(custom_name, str) or not custom_name.strip():
            return jsonify({'error': 'Review session is invalid; start a new review.'}), 400
        if not isinstance(custom_description, str) or not custom_description.strip():
            return jsonify({'error': 'Review session is invalid; start a new review.'}), 400
        if (not isinstance(sanitized_name, str) or not sanitized_name or
                sanitize_policy_name(sanitized_name) != sanitized_name):
            sanitized_name = sanitize_policy_name(custom_name)
        if not sanitized_name:
            return jsonify({'error': 'Review session has no valid export filename; start a new review.'}), 400

        tailoring = Tailoring(
            name=custom_name,
            id=sanitized_name,
            description=f"{custom_description} (Based on {guide.sca.policy.name})",
        )
        for check in guide.sca.checks:
            if check.id in removed_ids:
                decision = normalized[check.id]
                tailoring.decisions[check.id] = TailoringRemoval(
                    decision=decision.decision,
                    justification=decision.justification or '',
                    check=check,
                )

        record_generated_at = session.get('record_generated_at')
        if not isinstance(record_generated_at, str) or not record_generated_at:
            record_generated_at = datetime.now(timezone.utc).isoformat()

        draft_data = SessionService.serialize_session_data(
            session['baseline_filename'], custom_name, sanitized_name,
            custom_description, decisions, record_generated_at)
        if not SessionService(current_app.config['DRAFT_FOLDER']).save_draft(
                session['session_id'], draft_data):
            return jsonify({'error': 'Unable to persist review state.'}), 500
        session['record_generated_at'] = record_generated_at

        previous_path = None
        previous = session.get('export_zip_path')
        if isinstance(previous, str):
            try:
                previous_path = str(contained_path(
                    current_app.config['EXPORT_FOLDER'], previous))
            except ValueError:
                pass

        zip_path = export_policy(
            guide, tailoring, sanitized_name, current_app.config['EXPORT_FOLDER'],
            record_generated_at)
        session['export_zip_path'] = zip_path
        session['export_zip_filename'] = f'{sanitized_name}_export.zip'
        session.modified = True

        if previous_path is not None:
            cleanup_export(previous_path)

        return jsonify({'success': True, 'download_url': '/download'})
    except Exception:
        logger.exception("Unable to generate export")
        return jsonify({'error': 'Unable to generate export.'}), 500


@export_bp.route('/download')
def download_file() -> tuple[Response, Literal[400]] | tuple[Response, Literal[404]] | Response:
    if 'export_zip_path' not in session:
        return jsonify({'error': 'No file to download'}), 400
    try:
        zip_path = str(contained_path(
            current_app.config['EXPORT_FOLDER'], session['export_zip_path']))
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid download path'}), 400
    if not os.path.exists(zip_path):
        return jsonify({'error': 'File not found'}), 404
    return send_file(
        zip_path,
        as_attachment=True,
        download_name=session.get('export_zip_filename', 'export.zip'),
    )


@export_bp.route('/api/cleanup', methods=['POST'])
def cleanup_session() -> Response | tuple[Response, Literal[500]]:
    session_id = session.get('session_id')
    if isinstance(session_id, str):
        if not SessionService(current_app.config['DRAFT_FOLDER']).delete_draft(session_id):
            return jsonify({'error': 'Unable to clean up session.'}), 500

    baseline_filename = session.get('baseline_filename')
    if isinstance(baseline_filename, str):
        try:
            contained_path(current_app.config['UPLOAD_FOLDER'], baseline_filename).unlink(missing_ok=True)
        except (OSError, ValueError):
            logger.warning('Unable to remove session baseline', exc_info=True)

    export_zip_path = session.get('export_zip_path')
    if isinstance(export_zip_path, str):
        try:
            cleanup_export(str(contained_path(
                current_app.config['EXPORT_FOLDER'], export_zip_path)))
        except ValueError:
            logger.warning('Invalid session export path', exc_info=True)

    session.clear()
    return jsonify({'success': True})
