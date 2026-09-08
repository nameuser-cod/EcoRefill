"""Point settlement tests with atomic fake commits and no hardware or credentials."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import unittest
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from machine.owner_points import complete_refill, MAX_POINTS
from machine.water_worker import WaterRequestWorker
from test_point_payments import Database


class OwnerPointsTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self.db.records.update({
            'water_refill_sessions/refill': {'machineId': 'machine_001', 'ownerId': 'owner',
                                            'status': 'dispensing', 'pointsUsed': 5},
            'water_refill_requests/request': {'status': 'dispensing'},
            'transactions/refill': {'status': 'dispensing'},
        })

    def complete(self):
        return self.db.run(lambda tx: complete_refill(
            self.db, tx, datetime.now(timezone.utc),
            self.db.collection('water_refill_sessions').document('refill'),
            self.db.collection('water_refill_requests').document('request'),
            self.db.collection('transactions').document('refill'), 'machine_001'))

    def test_completed_refill_credits_owner_and_history_atomically(self):
        self.complete()
        self.assertEqual(self.db.records['users/owner']['points'], 2005)
        self.assertEqual(self.db.records['users/buyer']['points'], 7)
        for key in ('water_refill_sessions/refill', 'water_refill_requests/request', 'transactions/refill'):
            self.assertEqual(self.db.records[key]['status'], 'completed')
        record = self.db.records['transactions/refill']
        self.assertEqual(record['ownerPointsEarned'], 5)
        self.assertEqual((record['ownerPreviousPoints'], record['ownerPointsAfter']), (2000, 2005))

    def test_retries_and_competing_completions_credit_once(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: self.complete(), range(8)))
        self.assertEqual(self.db.records['users/owner']['points'], 2005)

    def test_failed_cancelled_and_unused_sessions_never_credit(self):
        for status in ('failed', 'cancelled', 'expired', 'waiting_for_user'):
            self.db.records['water_refill_sessions/refill']['status'] = status
            with self.assertRaises(ValueError):
                self.complete()
            self.assertEqual(self.db.records['users/owner']['points'], 2000)

    def test_invalid_balances_or_costs_leave_completion_uncommitted(self):
        for balance in (-1, True, '5', MAX_POINTS):
            self.db.records['users/owner']['points'] = balance
            with self.assertRaises(ValueError):
                self.complete()
            self.assertEqual(self.db.records['water_refill_sessions/refill']['status'], 'dispensing')
        self.db.records['users/owner']['points'] = 0
        for points in (None, 0, -1, True, '5', MAX_POINTS + 1):
            self.db.records['water_refill_sessions/refill']['pointsUsed'] = points
            with self.assertRaises(ValueError):
                self.complete()
            self.assertEqual(self.db.records['users/owner']['points'], 0)

    def test_existing_owner_without_balance_starts_at_zero(self):
        del self.db.records['users/owner']['points']
        self.complete()
        self.assertEqual(self.db.records['users/owner']['points'], 5)

    def test_credit_stays_with_owner_at_time_of_refill(self):
        self.db.records['machines/machine_001']['ownerId'] = 'stranger'
        self.complete()
        self.assertEqual(self.db.records['users/owner']['points'], 2005)
        self.assertNotIn('points', self.db.records['users/stranger'])

    def test_unowned_machine_completes_without_crediting_another_account(self):
        self.db.records['water_refill_sessions/refill']['ownerId'] = ''
        self.complete()
        self.assertEqual(self.db.records['users/owner']['points'], 2000)
        self.assertEqual(self.db.records['transactions/refill']['ownerPointsEarned'], 0)

    def test_legacy_active_session_uses_machine_owner(self):
        del self.db.records['water_refill_sessions/refill']['ownerId']
        self.complete()
        self.assertEqual(self.db.records['users/owner']['points'], 2005)

    def test_other_machine_cannot_settle_session(self):
        self.db.records['water_refill_sessions/refill']['machineId'] = 'machine_002'
        with self.assertRaises(ValueError):
            self.complete()
        self.assertEqual(self.db.records['users/owner']['points'], 2000)


class WorkerPointsTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self.db.transaction = lambda: None
        self.db.records['water_refill_sessions/refill'] = {
            'machineId': 'machine_001', 'status': 'waiting_for_user',
        }
        self.db.records['water_refill_requests/request'] = {
            'machineId': 'machine_001', 'sessionId': 'refill', 'userId': 'buyer',
            'waterAmountMl': 500, 'status': 'pending',
        }
        self.machine = WaterRequestWorker()
        self.machine.db = self.db
        self.machine.recycling_paused = Event()
        self.machine.finish_session_event = Event()
        self.machine.reset_state = Mock()
        self.firestore = SimpleNamespace(
            SERVER_TIMESTAMP=datetime.now(timezone.utc),
            transactional=lambda callback: lambda transaction: self.db.run(callback),
        )

    def process(self, success):
        self.machine.run_water_command = Mock(return_value=(success, None if success else 'WATER_TIMEOUT'))
        request = self.db.collection('water_refill_requests').document('request').get()
        with patch.dict('sys.modules', {'firebase_admin': SimpleNamespace(firestore=self.firestore)}):
            self.machine.process_water_refill_request(request)

    def test_success_transfers_spent_refill_points_to_owner_once(self):
        self.process(True)
        self.assertEqual(self.db.records['users/buyer']['points'], 2)
        self.assertEqual(self.db.records['users/owner']['points'], 2005)
        self.assertEqual(self.db.records['water_refill_sessions/refill']['ownerId'], 'owner')
        self.process(True)
        self.machine.run_water_command.assert_not_called()
        self.assertEqual(self.db.records['users/owner']['points'], 2005)

    def test_failure_refunds_buyer_without_crediting_owner(self):
        self.process(False)
        self.assertEqual(self.db.records['users/buyer']['points'], 7)
        self.assertEqual(self.db.records['users/owner']['points'], 2000)
        self.assertEqual(self.db.records['water_refill_sessions/refill']['status'], 'failed')

    def test_insufficient_buyer_balance_never_dispenses_or_credits_owner(self):
        self.db.records['users/buyer']['points'] = 0
        self.process(True)
        self.machine.run_water_command.assert_not_called()
        self.assertEqual(self.db.records['users/owner']['points'], 2000)


if __name__ == '__main__':
    unittest.main()
