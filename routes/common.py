import math
import re
from datetime import date
from uuid import uuid4

from flask import Blueprint, abort, current_app, jsonify, request
from services.google_sheets import HEADERS


def validate(table):
    body = request.get_json()
    fields = HEADERS[table][1:]
    if not isinstance(body, dict) or set(body) != set(fields):
        abort(400, description='Provide exactly these fields: ' + ', '.join(fields))
    for field in fields:
        if field == 'hours':
            continue
        if not isinstance(body[field], str) or not body[field].strip() or len(body[field]) > 500:
            abort(400, description=f'{field} must be nonempty text, at most 500 characters')
        body[field] = body[field].strip()
    if table == 'Interns':
        if not re.fullmatch(r'[^\s@]+@example\.(com|org|net)', body['email']):
            abort(400, description='Use a fake email at example.com, example.org, or example.net')
        if body['status'] not in ('Active', 'Inactive'):
            abort(400, description='status must be Active or Inactive')
    else:
        try:
            if date.fromisoformat(body['date']).isoformat() != body['date']:
                raise ValueError()
        except ValueError:
            abort(400, description='date must be a valid YYYY-MM-DD date')
        value = body['hours']
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= 24:
            abort(400, description='hours must be a number greater than 0 and at most 24')
        body['hours'] = float(value)
        if not any(row['intern_id'] == body['intern_id'] for row in current_app.extensions['store'].list('Interns')):
            abort(400, description='intern_id must reference an existing mock intern')
    return body


def crud_blueprint(name, table, prefix):
    blueprint = Blueprint(name, __name__)
    key = HEADERS[table][0]

    @blueprint.route('', methods=['GET', 'POST'])
    def collection():
        with current_app.extensions['store_lock']:
            store = current_app.extensions['store']
            if request.method == 'GET':
                return jsonify(store.list(table))
            record = validate(table)
            record[key] = prefix + uuid4().hex
            store.create(table, record)
            return jsonify(record), 201

    @blueprint.route('/<identifier>', methods=['GET', 'PUT', 'DELETE'])
    def item(identifier):
        with current_app.extensions['store_lock']:
            store = current_app.extensions['store']
            record = next((row for row in store.list(table) if row[key] == identifier), None)
            if record is None:
                abort(404, description='Record not found')
            if request.method == 'GET':
                return jsonify(record)
            if request.method == 'DELETE':
                if table == 'Interns' and any(row['intern_id'] == identifier for row in store.list('Hours')):
                    abort(409, description='Delete this intern’s hours first')
                store.replace(table, identifier, None)
                return '', 204
            record = validate(table)
            record[key] = identifier
            store.replace(table, identifier, record)
            return jsonify(record)

    return blueprint
