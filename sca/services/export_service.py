"""Export helpers."""
import os
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from sca.internal.guide import Guide
from sca.internal.loosening import Tailoring


def export_policy(guide: Guide, tailoring: Tailoring,
                  base_filename: str, export_root: str,
                  generated_at: str | None = None) -> str:
    if not re.fullmatch(r'[a-z0-9][a-z0-9_]*', base_filename):
        raise ValueError("Invalid export filename")

    root = Path(export_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    workspace = root / str(uuid.uuid4())
    workspace.mkdir()

    policy = workspace / f'{base_filename}.yml'
    exceptions_yml = workspace / f'{base_filename}_exceptions.yml'
    exceptions_md = workspace / f'{base_filename}_exceptions.md'
    archive = workspace / f'{base_filename}_export.zip'
    record_generated_at = generated_at or datetime.now(timezone.utc).isoformat()

    try:
        guide.export_custom(tailoring, str(policy))
        guide.export_exceptions(
            tailoring, str(policy), str(exceptions_yml), str(exceptions_md),
            record_generated_at)
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
            for path in (policy, exceptions_yml, exceptions_md):
                bundle.write(path, path.name)
        return str(archive)
    except Exception:
        shutil.rmtree(workspace, ignore_errors=True)
        raise


def cleanup_export(zip_path: str) -> None:
    shutil.rmtree(Path(zip_path).parent, ignore_errors=True)
