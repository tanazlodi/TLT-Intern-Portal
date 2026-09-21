from copy import deepcopy
from pathlib import Path


SHEETS_SCOPE = ['https://www.googleapis.com/auth/spreadsheets']

HEADERS = {
    'Interns': ['intern_id', 'name', 'email', 'program', 'status'],
    'Hours': ['entry_id', 'intern_id', 'date', 'hours', 'activity'],
}
SEED = {
    'Interns': [{'intern_id': 'INT001', 'name': 'John Doe', 'email': 'test@example.com',
                 'program': 'App Development', 'status': 'Active'}],
    'Hours': [{'entry_id': 'HRS001', 'intern_id': 'INT001', 'date': '2026-09-01',
               'hours': 2.0, 'activity': 'Mock training exercise'}],
}


class MockStore:
    def __init__(self):
        self.data = deepcopy(SEED)

    def list(self, table):
        return deepcopy(self.data[table])

    def create(self, table, record):
        self.data[table].append(deepcopy(record))

    def replace(self, table, identifier, record):
        key = HEADERS[table][0]
        for index, row in enumerate(self.data[table]):
            if row[key] == identifier:
                if record is None:
                    del self.data[table][index]
                else:
                    self.data[table][index] = deepcopy(record)
                return
        raise LookupError('Record disappeared')


class GoogleSheetsStore:
    """Small, single-process prototype; existing tabs must have exact headers."""

    def __init__(self, config):
        if str(config['MOCK_SHEET_CONFIRMED']).lower() != 'true':
            raise ValueError('Confirm a dedicated dummy-data sheet with MOCK_SHEET_CONFIRMED=true')
        if not config['GOOGLE_SHEET_ID']:
            raise ValueError('Set GOOGLE_SHEET_ID')
        credentials = self._credentials(config)
        from googleapiclient.discovery import build
        self.sheet_id = config['GOOGLE_SHEET_ID']
        self.values = build('sheets', 'v4', credentials=credentials, cache_discovery=False).spreadsheets().values()

    @staticmethod
    def _credentials(config):
        mode = config.get('GOOGLE_AUTH_MODE', 'oauth')
        if mode == 'service_account':
            path = config.get('GOOGLE_APPLICATION_CREDENTIALS', '')
            if not path:
                raise ValueError('Set GOOGLE_APPLICATION_CREDENTIALS')
            from google.oauth2 import service_account
            return service_account.Credentials.from_service_account_file(path, scopes=SHEETS_SCOPE)
        if mode != 'oauth':
            raise ValueError('GOOGLE_AUTH_MODE must be oauth or service_account')

        client_setting = config.get('GOOGLE_OAUTH_CLIENT_FILE', '')
        token_setting = config.get('GOOGLE_OAUTH_TOKEN_FILE', '')
        if not client_setting or not token_setting:
            raise ValueError('Set GOOGLE_OAUTH_CLIENT_FILE and GOOGLE_OAUTH_TOKEN_FILE')
        client_path = Path(client_setting)
        token_path = Path(token_setting)
        if not client_path.is_file():
            raise ValueError(f'OAuth client file not found: {client_path}')

        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        credentials = None
        if token_path.is_file():
            credentials = Credentials.from_authorized_user_file(token_path, SHEETS_SCOPE)
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        elif not credentials or not credentials.valid:
            flow = InstalledAppFlow.from_client_secrets_file(client_path, SHEETS_SCOPE)
            credentials = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(credentials.to_json(), encoding='utf-8')
        return credentials

    def _rows(self, table):
        rows = self.values.get(spreadsheetId=self.sheet_id, range=f"'{table}'!A:E").execute().get('values', [])
        if not rows or rows[0] != HEADERS[table]:
            raise ValueError(f'{table} must have the documented header row')
        return rows

    def list(self, table):
        records = []
        for row in self._rows(table)[1:]:
            if not row or not row[0]:
                continue
            record = dict(zip(HEADERS[table], row + [''] * (5 - len(row))))
            if table == 'Hours':
                record['hours'] = float(record['hours'])
            records.append(record)
        return records

    def create(self, table, record):
        self._rows(table)
        self.values.append(
            spreadsheetId=self.sheet_id, range=f"'{table}'!A:E",
            valueInputOption='RAW', insertDataOption='INSERT_ROWS',
            body={'values': [[record[field] for field in HEADERS[table]]]},
        ).execute()

    def replace(self, table, identifier, record):
        for number, row in enumerate(self._rows(table)[1:], start=2):
            if row and row[0] == identifier:
                target = f"'{table}'!A{number}:E{number}"
                if record is None:
                    self.values.clear(spreadsheetId=self.sheet_id, range=target, body={}).execute()
                else:
                    self.values.update(
                        spreadsheetId=self.sheet_id, range=target, valueInputOption='RAW',
                        body={'values': [[record[field] for field in HEADERS[table]]]},
                    ).execute()
                return
        raise LookupError('Record disappeared')
