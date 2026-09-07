#!/usr/bin/env python3

"""Flask application entry point for wazuhscatune."""
import logging
import os
import webbrowser
from pathlib import Path
from threading import Timer
from typing import Literal

from flask import Flask, render_template
from flask_session import Session

from sca.config import Config
from sca.routes.export import export_bp
from sca.routes.review import review_bp
from sca.routes.upload import upload_bp
from sca.services.session_service import SessionService

HOST = '127.0.0.1'
PORT = 5000


def create_app(config_class=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    folders = [
        app.config['UPLOAD_FOLDER'],
        app.config['DRAFT_FOLDER'],
        app.config['EXPORT_FOLDER'],
        app.config['SESSION_FILE_DIR'],
    ]
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
    Session(app)

    draft_service = SessionService(app.config['DRAFT_FOLDER'])
    protected_baselines = draft_service.cleanup_review_files(
        app.config['UPLOAD_FOLDER'], app.config['FILE_TTL_HOURS'])
    SessionService.cleanup_expired(
        folders, app.config['FILE_TTL_HOURS'], protected_baselines)

    app.register_blueprint(upload_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(export_bp)

    @app.errorhandler(404)
    def not_found_error(error) -> tuple[str, Literal[404]]:
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error) -> tuple[str, Literal[500]]:
        return render_template('errors/500.html'), 500

    @app.errorhandler(413)
    def request_entity_too_large(error) -> tuple[dict[str, str], Literal[413]]:
        limit = app.config['MAX_CONTENT_LENGTH']
        return {'error': f'File too large. Maximum size is {limit} bytes.'}, 413

    return app


def _open_browser(url: str) -> None:
    try:
        if webbrowser.get().name != 'gio':
            webbrowser.open_new(url)
    except webbrowser.Error:
        pass
    print(f"Access the app over {url}")


def _configure_logging() -> None:
    log_dir = Path(Config.LOG_FOLDER)
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_dir / f'{Config.APP_NAME}.log', encoding='utf-8')
    handler.setFormatter(logging.Formatter(
        fmt='%(asctime)s:%(name)s:%(levelname)s:%(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S%z',
    ))
    logging.basicConfig(handlers=[handler], level=logging.INFO, force=True)
    logging.getLogger('werkzeug').disabled = True


def main() -> None:
    logging_ready = False
    try:
        _configure_logging()
        logging_ready = True
        logging.info('Starting')

        app = create_app()
        Timer(1, _open_browser, args=(f'http://{HOST}:{PORT}/',)).start()
        app.run(debug=False, use_reloader=False, host=HOST, port=PORT)
        logging.info('Exiting.')
    except KeyboardInterrupt:
        print('Cancelled by user.')
        if logging_ready:
            logging.info('Cancelled by user.')
    except Exception as error:
        print(f'ERROR: {error}')
        if logging_ready:
            logging.error(str(error), exc_info=True)
        raise SystemExit(1) from error


if __name__ == '__main__':
    main()
