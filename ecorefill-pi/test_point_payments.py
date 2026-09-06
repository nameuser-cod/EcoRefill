import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from point_payments import PointPayments, PaymentError, register_payment_routes


class Snapshot:
    def __init__(self, key, value):
        self.id = key.split('/')[1]
        self.value = copy.deepcopy(value)
        self.exists = value is not None

    def to_dict(self):
        return copy.deepcopy(self.value)


class Database:
    def __init__(self):
        self.lock = Lock()
        self.records = {
            'users/buyer': {'role': 'user', 'points': 7, 'fullName': 'Buyer'},
            'users/other': {'role': 'user', 'points': 0},
            'users/owner': {'role': 'device_owner', 'fullName': 'Owner'},
            'users/stranger': {'role': 'device_owner'},
            'machines/machine_001': {'ownerId': 'owner', 'machineName': 'Machine One'},
            'gcashAccounts/owner': {'enabled': True, 'accountName': 'Owner GCash', 'mobileNumber': '09123456789'},
        }

    def collection(self, name):
        database = self

        class Ref:
            def __init__(self, key):
                self.key, self.id = f'{name}/{key}', key

            def get(self, transaction=None):
                if transaction and transaction.writes:
                    raise AssertionError('Reads must precede writes')
                return Snapshot(self.key, database.records.get(self.key))

            def set(self, data):
                database.records[self.key] = copy.deepcopy(data)

        class Collection:
            def document(self, key):
                return Ref(key)

            def stream(self):
                return [Snapshot(key, value) for key, value in database.records.items() if key.startswith(name + '/')]

            def where(self, field, operator, value):
                assert operator == '=='
                return SimpleNamespace(stream=lambda: [s for s in self.stream() if s.to_dict().get(field) == value])

        return Collection()

    def run(self, callback):
        # Firebase supplies real conflict retries. This fake serializes commits,
        # stages writes, and enforces read-before-write ordering.
        class Transaction:
            def __init__(self):
                self.writes = []

            def set(self, ref, data):
                self.writes.append((ref.key, data, False))

            def update(self, ref, data):
                self.writes.append((ref.key, data, True))

        with self.lock:
            tx = Transaction()
            result = callback(tx)
            staged = copy.deepcopy(self.records)
            for key, value, update in tx.writes:
                if update:
                    staged[key].update(value)
                else:
                    staged[key] = value
            self.records = staged
            return result


class PaymentTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self.api = PointPayments(self.db, datetime.now(timezone.utc), self.db.run)

    def call(self, action, uid='buyer', **data):
        return self.api.handle(action, uid, data)

    def create(self, order='order1', uid='buyer', **extra):
        return self.call('createPointPurchase', uid, **{'purchaseId': order, 'machineId': 'machine_001', 'packageId': 1, **extra})

    def submit(self, order='order1', uid='buyer', reference='1234567890123'):
        return self.call('submitGcashPayment', uid, purchaseId=order, referenceNumber=reference, senderName='Buyer')

    def review(self, decision='approved', uid='owner', note=''):
        return self.call('reviewGcashPayment', uid, purchaseId='order1', decision=decision, reviewNote=note)

    def assert_code(self, code, callback):
        with self.assertRaises(PaymentError) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_all_actions_require_login(self):
        for action in self.api.ACTIONS:
            with self.subTest(action=action):
                self.assert_code('unauthenticated', lambda: self.call(action, uid=None))

    def test_server_controls_price_and_owner_and_submission_does_not_credit(self):
        purchase = self.create(points=999999, price=0, ownerId='stranger')['purchase']
        self.assertEqual((purchase['points'], purchase['price'], purchase['ownerId']), (100, 20, 'owner'))
        self.submit()
        self.assertEqual(self.db.records['users/buyer']['points'], 7)
        self.assertEqual(self.db.records['pointPurchases/order1']['status'], 'pending')
        self.assertNotIn('transactions/gcash_order1', self.db.records)

    def test_concurrent_approval_credits_once(self):
        self.create(); self.submit()
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda _: self.review(), range(3)))
        self.assertEqual(self.db.records['users/buyer']['points'], 107)
        self.assertEqual(self.db.records['transactions/gcash_order1']['pointsAfter'], 107)
        self.assertEqual(len([k for k in self.db.records if k.startswith('transactions/')]), 1)

    def test_only_receiving_owner_can_review(self):
        self.create(); self.submit()
        for uid in ('buyer', 'other', 'stranger'):
            self.assert_code('permission-denied', lambda: self.review(uid=uid))
        self.assertEqual(self.db.records['users/buyer']['points'], 7)

    def test_only_buyer_can_submit(self):
        self.create()
        self.assert_code('permission-denied', lambda: self.submit(uid='other'))

    def test_reference_reuse_blocked_and_same_request_idempotent(self):
        self.create(); self.submit(); self.submit()
        self.create('order2', 'other')
        self.assert_code('already-exists', lambda: self.submit('order2', 'other', '123 456 789 0123'))
        self.assertEqual(self.db.records['pointPurchases/order2']['status'], 'awaiting_payment')

    def test_creation_retry_and_conflicting_request(self):
        self.create(); self.create()
        self.assertEqual(len([k for k in self.db.records if k.startswith('pointPurchases/')]), 1)
        self.assert_code('already-exists', lambda: self.create(uid='other'))
        self.assert_code('already-exists', lambda: self.create(packageId=2))

    def test_rejection_requires_note_and_cannot_later_credit(self):
        self.create(); self.submit()
        self.assert_code('invalid-argument', lambda: self.review('rejected'))
        self.review('rejected', note='Amount does not match')
        self.assert_code('failed-precondition', self.review)
        self.assertEqual(self.db.records['users/buyer']['points'], 7)

    def test_cannot_approve_without_submission(self):
        self.create()
        self.assert_code('failed-precondition', self.review)

    def test_invalid_balance_rolls_back_review(self):
        self.create(); self.submit()
        for balance in ('invalid', True, -1, 9007199254740991):
            self.db.records['users/buyer']['points'] = balance
            self.assert_code('failed-precondition', self.review)
            self.assertEqual(self.db.records['pointPurchases/order1']['status'], 'pending')
            self.assertNotIn('transactions/gcash_order1', self.db.records)

    def test_disabled_seller_and_frozen_recipient(self):
        self.create()
        self.call('saveGcashAccount', 'owner', accountName='New GCash', mobileNumber='+639876543210', enabled=False)
        self.assert_code('failed-precondition', lambda: self.create('order2'))
        self.submit(); self.review()
        self.assertEqual(self.db.records['pointPurchases/order1']['recipientNumber'], '09123456789')
        self.assertEqual(self.call('getGcashOptions')['sellers'], [])

    def test_history_is_private(self):
        self.create()
        for uid in ('buyer', 'owner'):
            self.assertEqual(len(self.call('listPointPurchases', uid)['purchases']), 1)
        for uid in ('other', 'stranger'):
            self.assertEqual(self.call('listPointPurchases', uid)['purchases'], [])

    def test_invalid_input_rejected(self):
        for package in (True, 99, '1'):
            self.assert_code('invalid-argument', lambda: self.create(packageId=package))
        self.assert_code('invalid-argument', lambda: self.create('../order'))
        self.create()
        self.assert_code('invalid-argument', lambda: self.submit(reference='ABC'))
        self.assert_code('permission-denied', lambda: self.call('saveGcashAccount'))
        self.assert_code('invalid-argument', lambda: self.call('saveGcashAccount', 'owner', accountName='Owner', mobileNumber='123'))
        self.assert_code('not-found', lambda: self.call('__init__'))


class RouteTests(unittest.TestCase):
    def setUp(self):
        from flask import Flask
        self.app = Flask(__name__)
        def verify():
            raise ValueError('Invalid Firebase ID token')
        # Avoid needing live Admin credentials to check HTTP admission behavior.
        with patch.dict('sys.modules', {'firebase_admin': SimpleNamespace(firestore=SimpleNamespace())}):
            register_payment_routes(self.app, lambda: None, verify)
        self.client = self.app.test_client()

    def test_invalid_token_rejected_before_database_access(self):
        response = self.client.post('/api/points/createPointPurchase', json={'userId': 'buyer'})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json['error']['code'], 'unauthenticated')

    def test_unknown_action_and_machine_control_not_exposed(self):
        self.assertEqual(self.client.post('/api/points/deleteUser', json={}).status_code, 404)
        self.assertEqual(self.client.post('/api/machine/reset', json={}).status_code, 404)

    def test_authenticated_http_purchase_and_approval(self):
        from flask import Flask, request
        db = Database()
        db.transaction = lambda: None
        firestore = SimpleNamespace(
            SERVER_TIMESTAMP=datetime.now(timezone.utc),
            transactional=lambda callback: lambda transaction: db.run(callback),
        )
        app = Flask('payment-roundtrip')
        with patch.dict('sys.modules', {'firebase_admin': SimpleNamespace(firestore=firestore)}):
            register_payment_routes(app, lambda: db, lambda: {'uid': request.headers.get('Test-User')})
        client = app.test_client()
        response = client.post('/api/points/createPointPurchase', headers={'Test-User': 'buyer'}, json={
            'purchaseId': 'order1', 'machineId': 'machine_001', 'packageId': 1, 'userId': 'other',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['data']['purchase']['userId'], 'buyer')
        response = client.post('/api/points/submitGcashPayment', headers={'Test-User': 'buyer'}, json={
            'purchaseId': 'order1', 'senderName': 'Buyer', 'referenceNumber': '1234567890123',
        })
        self.assertEqual(response.status_code, 200)
        for uid, status in [('stranger', 403), ('owner', 200), ('owner', 200)]:
            response = client.post('/api/points/reviewGcashPayment', headers={'Test-User': uid}, json={
                'purchaseId': 'order1', 'decision': 'approved',
            })
            self.assertEqual(response.status_code, status)
        self.assertEqual(db.records['users/buyer']['points'], 107)
        response = client.post('/api/points/createPointPurchase', headers={'Test-User': 'buyer'}, json=['invalid'])
        self.assertEqual(response.status_code, 400)

    def test_large_request_rejected(self):
        response = self.client.post('/api/points/createPointPurchase', json={'padding': 'a' * 9000})
        self.assertEqual(response.status_code, 413)


if __name__ == '__main__':
    unittest.main()
