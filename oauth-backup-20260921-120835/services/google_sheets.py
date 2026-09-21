from copy import deepcopy

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
        if not config['GOOGLE_SHEET_ID'] or not config['GOOGLE_APPLICATION_CREDENTIALS']:
            raise ValueError('Set Google spreadsheet ID and service-account credential path')
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        credentials = service_account.Credentials.from_service_account_file(
            config['GOOGLE_APPLICATION_CREDENTIALS'],
            scopes=['https://www.googleapis.com/auth/spreadsheets'],
        )
        self.sheet_id = config['GOOGLE_SHEET_ID']
        self.values = build('sheets', 'v4', credentials=credentials, cache_discovery=False).spreadsheets().values()

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
