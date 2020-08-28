import requests
from requests.auth import HTTPBasicAuth


def wrap_req(req):
    return {
        'using': ['urn:ietf:params:jmap:core', 'urn:ietf:params:jmap:mail'],
        'methodCalls': req
    }


class JmapClient:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.api_url = None
        self.account_id = None
        self.cache_folders = None
        self.cache_messages = None

    def call(self, payload):
        r = requests.post(
            self.api_url,
            json=wrap_req(payload),
            auth=HTTPBasicAuth(self.username, self.password)
        )
        data = r.json()
        return data

    def new_session(self):
        r = requests.get(
            'https://jmap.fastmail.com/.well-known/jmap',
            auth=HTTPBasicAuth(self.username, self.password)
        )
        data = r.json()
        self.api_url = data['apiUrl']
        accounts = data['accounts']
        for account_id, obj in accounts.items():
            if obj['name'] == self.username:
                self.account_id = account_id
                break

    def first_call(self):
        if self.account_id is None:
            raise ValueError('Cannot request anything without an account_id')

        payload = wrap_req([['Mailbox/get', {
            'accountId': self.account_id,
            'ids': None
        }, '0']])

        r = requests.post(
            self.api_url,
            json=payload,
            auth=HTTPBasicAuth(self.username, self.password)
        )

        data = r.json()

        method_responses = data['methodResponses']
        for mr in method_responses:
            method, other, status = mr
            if method == 'Mailbox/get':
                for k, v in other.items():
                    if k == 'list':
                        self.cache_folders = v
                        break

    def fetch_messages(self):
        inbox_uid = 'dc032506-cdae-44f1-9f7f-0c9e9f16686d'
        payload = wrap_req([
            ['Email/query', {
                'accountId': self.account_id,
                'filter': {'inMailbox': inbox_uid},
                'limit': 20,
            }, '0'
            ],
            ['Email/get', {
                'accountId': self.account_id,
                '#ids': {
                    'name': 'Email/query',
                    'path': '/ids',
                    'resultOf': '0',
                },
            }, '0'
            ]
        ])

        r = requests.post(
            self.api_url,
            json=payload,
            auth=HTTPBasicAuth(self.username, self.password)
        )

        data = r.json()

        method_responses = data['methodResponses']
        for mr in method_responses:
            method, other, status = mr
            if method == 'Email/get':
                for k, v in other.items():
                    if k == 'list':
                        self.cache_messages = v
                        break


class Handler:
    def __init__(self, username, password):
        client = JmapClient(username, password)
        client.new_session()
        client.first_call()
        client.fetch_messages()
        self.client = client
        self.account_id = client.account_id
        self.batch = []

    def apply_batch(self):
        r = self.client.call(self.batch)
        self.batch = []
        return r

    def mark_unseen(self, message):
        method = [
            'Email/set', {
                'accountId': self.account_id,
                'update': {
                    message['id']: {
                        'keywords/$seen': None
                    }
                }
            },
            '0'
        ]
        self.batch.append(method)
        return method

    def mark_seen(self, message):
        method = [
            'Email/set', {
                'accountId': self.account_id,
                'update': {
                    message['id']: {
                        'keywords/$seen': True
                    }
                }
            },
            '0'
        ]
        self.batch.append(method)
        return method

    def flag(self, message):
        method = [
            'Email/set', {
                'accountId': self.account_id,
                'update': {
                    message['id']: {
                        'keywords/$flagged': True
                    }
                }
            },
            '0'
        ]
        self.batch.append(method)
        return method

    def unflag(self, message):
        method = [
            'Email/set', {
                'accountId': self.account_id,
                'update': {
                    message['id']: {
                        'keywords/$flagged': None
                    }
                }
            },
            '0'
        ]
        self.batch.append(method)
        return method

    def move_to_trash(self, message):
        trash_mailbox_uid = [
            m for m in self.client.cache_folders
            if m['role'] == 'trash'
        ][0]['id']

        method = [
            'Email/set', {
                'accountId': self.account_id,
                'update': {
                    message['id']: {
                        'mailboxIds': {trash_mailbox_uid: True}
                    }
                }
            },
            '0'
        ]
        self.batch.append(method)
        return method

    def move_to_mailboxes(self, message, *mailbox_ids):
        method = [
            'Email/set', {
                'accountId': self.account_id,
                'update': {
                    message['id']: {
                        'mailboxIds': {m_id: True for m_id in mailbox_ids}
                    }
                }
            },
            '0'
        ]
        self.batch.append(method)
        return method
