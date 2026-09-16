"""Half-point batch rewards must survive finalization and authenticated claims."""

from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from flask import Flask
from machine.runtime import MachineRuntime
from machine.points import read_points
from test_point_payments import Database


class FractionalRewardTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self.db.transaction = lambda: None
        self.db.records['users/buyer']['points'] = 0.5
        self.machine = MachineRuntime()
        self.addCleanup(self.machine.close)
        self.machine.db = self.db
        self.machine.get_redemption_tunnel_url = Mock(return_value='https://example.test')
        self.machine.require_firebase_user = lambda: {'uid': 'buyer'}
        self.firestore = SimpleNamespace(
            SERVER_TIMESTAMP=datetime.now(timezone.utc),
            transactional=lambda callback: lambda transaction: self.db.run(callback),
        )
        self.app = Flask(__name__)

        def batch():
            writes = []
            return SimpleNamespace(
                set=lambda ref, data, merge=False: writes.append((ref, data)),
                commit=lambda: self.db.run(lambda tx: [tx.set(ref, data) for ref, data in writes]),
            )

        self.db.batch = batch

    def claim(self, session_id):
        with self.app.test_request_context(json={'code': f'ecorefill://claim/{session_id}'}):
            return self.app.make_response(self.machine.api_redeem_recycling_reward())

    def test_single_even_odd_and_mixed_batches_credit_exactly_once(self):
        with patch.dict('sys.modules', {'firebase_admin': SimpleNamespace(firestore=self.firestore)}):
            balance = 0.5
            for bottles, cans, points in ((1, 0, 0.5), (2, 0, 1), (3, 0, 1.5), (3, 2, 3.5)):
                with self.subTest(bottles=bottles, cans=cans):
                    session_id = f'batch-{bottles}-{cans}'
                    self.machine.update_state(
                        batchSessionId=session_id, itemCount=bottles + cans,
                        bottleCount=bottles, canCount=cans, pointsEarned=points,
                    )
                    self.assertTrue(self.machine.finalize_recycling_session())
                    self.assertEqual(self.db.records[f'redeem_qr_codes/{session_id}']['pointsEarned'], points)
                    response = self.claim(session_id)
                    balance += points
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.get_json()['pointsEarned'], points)
                    self.assertEqual(response.get_json()['totalPoints'], balance)
                    self.assertEqual(self.db.records['users/buyer']['points'], balance)
                    transaction = next(value for key, value in self.db.records.items()
                                       if key.startswith('transactions/') and value['sessionId'] == session_id)
                    self.assertEqual(transaction['pointsAfter'], balance)
                    self.assertEqual(transaction['pointsEarned'], points)
                    with self.assertLogs('ecorefill.machine', level='ERROR'):
                        self.assertEqual(self.claim(session_id).status_code, 400)
                    self.assertEqual(self.db.records['users/buyer']['points'], balance)

    def test_invalid_point_values_are_rejected(self):
        for value in (True, False, '0.5', None, -0.5, 0.25, float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                read_points(value)


if __name__ == '__main__':
    unittest.main()
