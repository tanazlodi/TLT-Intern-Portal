import os
from pathlib import Path
from threading import RLock

from dotenv import load_dotenv
from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from routes.interns import interns
from routes.hours import hours
from services.google_sheets import GoogleSheetsStore, MockStore


def create_app(test_config=None):
    load_dotenv(Path(__file__).with_name('.env'))
    app = Flask(__name__)
    app.config.from_mapping(
        STORAGE_BACKEND=os.getenv('STORAGE_BACKEND', 'mock'),
        GOOGLE_SHEET_ID=os.getenv('GOOGLE_SHEET_ID', ''),
        GOOGLE_AUTH_MODE=os.getenv('GOOGLE_AUTH_MODE', 'oauth'),
        GOOGLE_OAUTH_CLIENT_FILE=os.getenv('GOOGLE_OAUTH_CLIENT_FILE', ''),
        GOOGLE_OAUTH_TOKEN_FILE=os.getenv('GOOGLE_OAUTH_TOKEN_FILE', ''),
        GOOGLE_APPLICATION_CREDENTIALS=os.getenv('GOOGLE_APPLICATION_CREDENTIALS', ''),
        MOCK_SHEET_CONFIRMED=os.getenv('MOCK_SHEET_CONFIRMED', 'false'),
        MAX_CONTENT_LENGTH=16 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    backend = app.config['STORAGE_BACKEND']
    if backend not in ('mock', 'sheets'):
        raise ValueError('STORAGE_BACKEND must be mock or sheets')
    app.extensions['store'] = MockStore() if backend == 'mock' else GoogleSheetsStore(app.config)
    app.extensions['store_lock'] = RLock()
    app.register_blueprint(interns, url_prefix='/api/interns')
    app.register_blueprint(hours, url_prefix='/api/hours')

    @app.get('/api/health')
    def health():
        return jsonify(status='ok', storage=backend, data_policy='mock-only')

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(Exception)
    def unexpected_error(error):
        app.logger.error('Backend request failed (%s)', type(error).__name__)
        return jsonify(error='Backend operation failed. Check configuration and service availability.'), 500

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=5000)
