"""Contained draft persistence and lifecycle cleanup."""
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

logger: logging.Logger = logging.getLogger(__name__)
SESSION_ID: re.Pattern[str] = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)
DRAFT_SCHEMA_VERSION = 1


def contained_path(root: str, name: str) -> Path:
    base: Path = Path(root).resolve()
    candidate: Path = (base / name).resolve()
    if candidate == base or base not in candidate.parents:
        raise ValueError("Path is outside the configured application directory")
    return candidate


class SessionService:
    def __init__(self, draft_folder: str) -> None:
        self.draft_folder = str(Path(draft_folder).resolve())
        os.makedirs(self.draft_folder, exist_ok=True)

    @staticmethod
    def validate_session_id(session_id: object) -> str:
        if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
            raise ValueError("Invalid session identifier")
        return session_id

    def _get_draft_path(self, session_id: str) -> Path:
        return contained_path(self.draft_folder,
                              f"{self.validate_session_id(session_id)}.json")

    def save_draft(self, session_id: str, data: dict[str, Any]) -> bool:
        temp_name: str | None = None
        try:
            payload: dict[str, Any] = dict(data)
            payload['last_saved'] = time.time()
            destination = self._get_draft_path(session_id)
            with tempfile.NamedTemporaryFile(
                    mode='w', encoding='utf-8', dir=destination.parent,
                    prefix=f'.{destination.name}.', suffix='.tmp', delete=False) as stream:
                temp_name = stream.name
                json.dump(payload, stream, indent=2, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, destination)
            temp_name = None
            return True
        except Exception:
            logger.exception("Unable to save draft %s", session_id)
            return False
        finally:
            if temp_name:
                try:
                    Path(temp_name).unlink(missing_ok=True)
                except OSError:
                    logger.warning("Unable to remove temporary draft %s", temp_name,
                                   exc_info=True)

    def load_draft(self, session_id: str, *, strict: bool = False
                   ) -> dict[str, Any] | None:
        try:
            path: Path = self._get_draft_path(session_id)
            if not path.is_file():
                return None
            with path.open(encoding='utf-8') as stream:
                data = json.load(stream)
            if not isinstance(data, dict):
                raise ValueError("Draft root must be an object")
            return data
        except Exception as error:
            logger.exception("Unable to load draft %s", session_id)
            if strict:
                raise ValueError("Invalid draft data") from error
            return None

    def delete_draft(self, session_id: str) -> bool:
        try:
            self._get_draft_path(session_id).unlink(missing_ok=True)
            return True
        except Exception:
            logger.exception("Unable to delete draft %s", session_id)
            return False

    def list_drafts(self) -> list[dict[str, Any]]:
        drafts: list[dict[str, Any]] = []
        for path in Path(self.draft_folder).glob('*.json'):
            session_id = path.stem
            if not SESSION_ID.fullmatch(session_id):
                continue
            data: dict[str, Any] | None = self.load_draft(session_id)
            if data and isinstance(data.get('custom_name'), str):
                saved = data.get('last_saved', 0)
                if not isinstance(saved, (int, float)):
                    saved = 0
                drafts.append({'session_id': session_id,
                               'custom_name': data['custom_name'],
                               'last_saved': saved})
        return sorted(drafts, key=lambda item: item['last_saved'], reverse=True)

    @staticmethod
    def serialize_session_data(baseline_filename: str, custom_name: str,
                               sanitized_name: str, custom_description: str,
                               decisions: dict[str, Any]) -> dict[str, Any]:
        return {'schema_version': DRAFT_SCHEMA_VERSION,
                'baseline_filename': baseline_filename, 'custom_name': custom_name,
                'sanitized_name': sanitized_name,
                'custom_description': custom_description, 'decisions': decisions}

    def cleanup_review_files(self, upload_folder: str, ttl_hours: int) -> set[Path]:
        """Expire draft/baseline pairs and return baselines owned by active drafts."""
        cutoff = time.time() - max(ttl_hours, 1) * 3600
        protected: set[Path] = set()

        for draft_path in Path(self.draft_folder).glob('*.json'):
            session_id = draft_path.stem
            if draft_path.is_symlink() or not SESSION_ID.fullmatch(session_id):
                continue
            try:
                data = self.load_draft(session_id)
                baseline_path: Path | None = None
                if data and isinstance(data.get('baseline_filename'), str):
                    try:
                        baseline_path = contained_path(
                            upload_folder, data['baseline_filename'])
                    except ValueError:
                        logger.warning("Invalid baseline path in draft %s", session_id)

                if draft_path.stat().st_mtime >= cutoff:
                    if baseline_path is not None:
                        protected.add(baseline_path)
                    continue

                draft_path.unlink(missing_ok=True)
                if baseline_path is not None:
                    baseline_path.unlink(missing_ok=True)
            except Exception:
                logger.warning("Unable to clean review draft %s", draft_path,
                               exc_info=True)

        return protected

    @staticmethod
    def cleanup_expired(roots: list[str], ttl_hours: int,
                        protected_paths: set[Path] | None = None) -> None:
        cutoff: float = time.time() - max(ttl_hours, 1) * 3600
        protected = {path.resolve() for path in (protected_paths or set())}
        for root_name in roots:
            root: Path = Path(root_name).resolve()
            if not root.is_dir():
                continue
            for path in root.iterdir():
                try:
                    if (path.is_symlink() or path.resolve() in protected
                            or path.stat().st_mtime >= cutoff):
                        continue
                    if path.is_file():
                        path.unlink()
                    elif path.is_dir():
                        import shutil
                        shutil.rmtree(path)
                except Exception:
                    logger.warning("Unable to remove expired path %s", path,
                                   exc_info=True)
