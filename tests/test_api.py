import unittest
from app import create_app


class APITest(unittest.TestCase):
    def setUp(self):
        self.client = create_app({'TESTING': True, 'STORAGE_BACKEND': 'mock'}).test_client()

    def test_crud_and_relationships(self):
        intern = dict(name='Jane Doe', email='jane@example.com', program='Mock Training', status='Active')
        response = self.client.post('/api/interns', json=intern)
        self.assertEqual(response.status_code, 201)
        identifier = response.json['intern_id']
        path = '/api/interns/' + identifier
        self.assertEqual(self.client.get(path).json['name'], 'Jane Doe')
        intern['program'] = 'Dummy Program'
        self.assertEqual(self.client.put(path, json=intern).json['program'], 'Dummy Program')
        entry = dict(intern_id=identifier, date='2026-09-01', hours=3, activity='Mock practice')
        response = self.client.post('/api/hours', json=entry)
        self.assertEqual(response.status_code, 201)
        hour_path = '/api/hours/' + response.json['entry_id']
        entry['hours'] = 4
        self.assertEqual(self.client.put(hour_path, json=entry).json['hours'], 4)
        self.assertEqual(self.client.get(hour_path).status_code, 200)
        self.assertEqual(self.client.delete(path).status_code, 409)
        self.assertEqual(self.client.delete(hour_path).status_code, 204)
        self.assertEqual(self.client.delete(path).status_code, 204)
        self.assertEqual(self.client.get(path).status_code, 404)

    def test_validation(self):
        entry = dict(intern_id='INT001', date='2026-09-01', hours=2, activity='Mock practice')
        for change in ({'hours': -1}, {'hours': True}, {'hours': 25}, {'date': '2026-02-30'}, {'intern_id': 'missing'}):
            self.assertEqual(self.client.post('/api/hours', json=entry | change).status_code, 400)
        self.assertEqual(self.client.post('/api/interns', json=dict(name='John Doe', email='test@gmail.com', program='Mock', status='Active')).status_code, 400)
        self.assertEqual(self.client.post('/api/interns', json=[]).status_code, 400)
        self.assertEqual(self.client.post('/api/interns', data='{', content_type='application/json').status_code, 400)
        self.assertEqual(self.client.get('/api/health').json['storage'], 'mock')

    def test_sheets_mode_requires_oauth_paths(self):
        with self.assertRaisesRegex(ValueError, 'GOOGLE_OAUTH_CLIENT_FILE'):
            create_app({
                'STORAGE_BACKEND': 'sheets',
                'MOCK_SHEET_CONFIRMED': 'true',
                'GOOGLE_SHEET_ID': 'dummy-id',
                'GOOGLE_AUTH_MODE': 'oauth',
                'GOOGLE_OAUTH_CLIENT_FILE': '',
                'GOOGLE_OAUTH_TOKEN_FILE': '',
            })


if __name__ == '__main__':
    unittest.main()
