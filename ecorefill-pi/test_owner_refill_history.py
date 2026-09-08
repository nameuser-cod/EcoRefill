"""Historical point reconciliation using synthetic Firestore records."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import unittest

from owner_refill_history import SYNC_BATCH_SIZE
from point_payments import PaymentError, PointPayments
from test_point_payments import Database


class RefillHistoryTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self.db.records['users/owner']['points'] = 0
        self.api = PointPayments(self.db, datetime.now(timezone.utc), self.db.run)

    def refill(self, key='old', points=2, status='completed', **extra):
        data = {'machineId': 'machine_001', 'userId': 'buyer', 'pointsUsed': points,
                'waterAmountMl': 250, 'status': status, 'createdAt': 'original-date', **extra}
        self.db.records[f'water_refill_sessions/{key}'] = dict(data)
        self.db.records[f'transactions/{key}-payment'] = {**data, 'type': 'water_refill', 'sessionId': key}

    def sync(self, uid='owner', **data):
        return self.api.handle('syncOwnerRefillPoints', uid, data)

    def test_old_completed_refills_credit_actual_cost_without_changing_customer_or_dates(self):
        self.refill('aug31', points=2)
        self.refill('aug29', points=2)
        self.refill('large', points=10)
        result = self.sync()
        self.assertEqual((result['pointsAdded'], result['refillsCredited']), (14, 3))
        self.assertEqual(self.db.records['users/owner']['points'], 14)
        self.assertEqual(self.db.records['users/buyer']['points'], 7)
        self.assertEqual(self.db.records['transactions/aug31-payment']['createdAt'], 'original-date')
        self.assertEqual(self.db.records['water_refill_sessions/aug31']['status'], 'completed')

    def test_failed_and_unfinished_refills_do_not_earn_points(self):
        for status in ('failed', 'cancelled', 'expired', 'processing', 'dispensing', 'waiting_for_user'):
            self.refill(status, status=status)
        self.assertEqual(self.sync()['pointsAdded'], 0)
        self.assertEqual(self.db.records['users/owner']['points'], 0)

    def test_duplicate_records_and_repeated_concurrent_syncs_credit_once(self):
        self.refill()
        self.db.records['transactions/duplicate'] = dict(self.db.records['transactions/old-payment'])
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.sync(), range(8)))
        self.assertEqual(sum(result['pointsAdded'] for result in results), 2)
        self.assertEqual(self.db.records['users/owner']['points'], 2)
        self.assertTrue(self.db.records['transactions/duplicate']['ownerPointsSettled'])
        self.assertEqual(self.sync()['pointsAdded'], 0)

    def test_modern_settled_refill_is_not_credited_again(self):
        self.refill(ownerId='owner', ownerPointsSettled=True, ownerPointsEarned=2)
        self.db.records['users/owner']['points'] = 2
        self.assertEqual(self.sync()['pointsAdded'], 0)
        self.assertEqual(self.db.records['users/owner']['points'], 2)

    def test_transaction_only_and_session_only_history_are_supported(self):
        self.refill('transaction-only', points=5)
        del self.db.records['water_refill_sessions/transaction-only']
        self.refill('session-only')
        del self.db.records['transactions/session-only-payment']
        self.refill('no-link')
        del self.db.records['water_refill_sessions/no-link']
        del self.db.records['transactions/no-link-payment']['sessionId']
        self.assertEqual(self.sync()['pointsAdded'], 9)
        self.assertEqual(self.sync()['pointsAdded'], 0)

    def test_late_duplicate_transaction_cannot_recredit_a_missing_session(self):
        self.refill()
        del self.db.records['water_refill_sessions/old']
        original = dict(self.db.records['transactions/old-payment'])
        self.sync()
        del self.db.records['transactions/old-payment']
        self.db.records['transactions/late-copy'] = original
        self.assertEqual(self.sync()['pointsAdded'], 0)
        self.assertEqual(self.db.records['users/owner']['points'], 2)

    def test_conflicting_status_cost_or_owner_is_skipped(self):
        for changed in ({'status': 'failed'}, {'pointsUsed': 5}, {'ownerId': 'stranger'},
                        {'ownerId': ''}, {'ownerPointsSettled': True}):
            with self.subTest(changed=changed):
                self.setUp()
                self.refill()
                self.db.records['transactions/old-payment'].update(changed)
                self.assertEqual(self.sync()['pointsAdded'], 0)

    def test_invalid_cost_is_never_inferred_from_volume(self):
        for points in (None, 0, -2, True, '2', 9007199254740992):
            self.refill(points=points)
            self.assertEqual(self.sync()['pointsAdded'], 0)

    def test_account_and_machine_ownership_cannot_be_supplied_by_client(self):
        self.refill()
        with self.assertRaises(PaymentError) as caught:
            self.sync(uid='buyer', ownerId='owner')
        self.assertEqual(caught.exception.code, 'permission-denied')
        self.assertEqual(self.sync(uid='stranger', ownerId='owner', machineId='machine_001')['pointsAdded'], 0)
        self.db.records['machines/machine_001']['ownerId'] = 'stranger'
        self.assertEqual(self.sync()['pointsAdded'], 0)

    def test_all_owned_machines_are_included_but_other_machines_are_not(self):
        self.db.records['machines/machine_002'] = {'ownerId': 'owner'}
        self.db.records['machines/machine_003'] = {'ownerId': 'stranger'}
        self.refill('one')
        self.refill('two', machineId='machine_002')
        self.refill('three', machineId='machine_003')
        self.assertEqual(self.sync()['pointsAdded'], 4)

    def test_large_history_can_be_synced_in_bounded_batches(self):
        for index in range(SYNC_BATCH_SIZE + 3):
            self.refill(f'refill-{index:03d}')
        first = self.sync()
        self.assertEqual(first['refillsCredited'], SYNC_BATCH_SIZE)
        self.assertTrue(first['hasMore'])
        second = self.sync(cursor=first['nextCursor'])
        self.assertEqual(second['refillsCredited'], 3)
        self.assertFalse(second['hasMore'])
        self.assertEqual(self.db.records['users/owner']['points'], (SYNC_BATCH_SIZE + 3) * 2)
        self.assertEqual(self.sync()['pointsAdded'], 0)

    def test_bad_cursor_and_balance_do_not_mutate_history(self):
        self.refill()
        for cursor in ('forged', [1, 2, 3], ['missing']):
            with self.assertRaises(PaymentError):
                self.sync(cursor=cursor)
        for balance in (-1, True, '0', 9007199254740991):
            self.db.records['users/owner']['points'] = balance
            with self.assertRaises(PaymentError):
                self.sync()
            self.assertNotIn('ownerPointsSettled', self.db.records['water_refill_sessions/old'])

    def test_concurrent_new_refill_settlement_wins_over_stale_history_scan(self):
        self.refill()
        def interleaved(callback):
            self.db.records['users/owner']['points'] = 2
            self.db.records['water_refill_sessions/old'].update(ownerPointsSettled=True)
            return self.db.run(callback)
        self.api.run_transaction = interleaved
        self.assertEqual(self.sync()['pointsAdded'], 0)
        self.assertEqual(self.db.records['users/owner']['points'], 2)

    def test_recheck_machine_ownership_before_committing(self):
        self.refill()
        def interleaved(callback):
            self.db.records['machines/machine_001']['ownerId'] = 'stranger'
            return self.db.run(callback)
        self.api.run_transaction = interleaved
        self.assertEqual(self.sync()['pointsAdded'], 0)

    def test_synced_points_can_be_sold_and_sync_does_not_restore_spent_points(self):
        self.refill(points=5)
        self.sync()
        self.api.handle('createPointPurchase', 'buyer', {'purchaseId': 'order', 'machineId': 'machine_001', 'points': 5})
        self.api.handle('submitGcashPayment', 'buyer', {'purchaseId': 'order', 'senderName': 'Buyer', 'referenceNumber': '1234567890123'})
        self.api.handle('reviewGcashPayment', 'owner', {'purchaseId': 'order', 'decision': 'approved'})
        self.assertEqual(self.db.records['users/owner']['points'], 0)
        self.assertEqual(self.db.records['users/buyer']['points'], 12)
        self.assertEqual(self.sync()['pointsAdded'], 0)
        self.assertEqual(self.db.records['users/owner']['points'], 0)


if __name__ == '__main__':
    unittest.main()
