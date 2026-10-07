"""Public reward discovery survives startup ordering and connection recovery."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from machine.config import MACHINE_ID
from machine.runtime import MachineRuntime


class RedemptionDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.machine = MachineRuntime()
        self.machine.db = Mock()
        self.machine.redemption_tunnel_url = "https://current.trycloudflare.com"
        firebase = SimpleNamespace(firestore=SimpleNamespace(SERVER_TIMESTAMP="timestamp"))
        mocked = patch.dict("sys.modules", {"firebase_admin": firebase})
        mocked.start()
        self.addCleanup(mocked.stop)

    def test_publishes_machine_scoped_and_legacy_discovery_without_overwriting_machine(self):
        self.machine.publish_redemption_endpoint()
        machines = self.machine.db.collection("machines")
        machines.document.assert_any_call(MACHINE_ID)
        machines.document(MACHINE_ID).set.assert_any_call({
            "redemptionApiUrl": self.machine.redemption_tunnel_url,
            "redemptionApiUpdatedAt": "timestamp",
        }, merge=True, timeout=5, retry=None)
        self.assertEqual(self.machine.redemption_published_url, self.machine.redemption_tunnel_url)
        self.machine.db.reset_mock()
        self.machine.publish_redemption_endpoint()
        self.machine.db.collection.assert_not_called()

    def test_failed_publication_is_retried_and_a_new_tunnel_is_republished(self):
        self.machine.db.collection.return_value.document.return_value.set.side_effect = TimeoutError("offline")
        with self.assertRaises(TimeoutError):
            self.machine.publish_redemption_endpoint()
        self.assertIsNone(self.machine.redemption_published_url)
        self.machine.db.collection.return_value.document.return_value.set.side_effect = None
        self.machine.publish_redemption_endpoint()
        self.machine.redemption_tunnel_url = "https://restarted.trycloudflare.com"
        self.machine.publish_redemption_endpoint()
        self.assertEqual(self.machine.redemption_published_url, self.machine.redemption_tunnel_url)

    def test_tunnel_can_start_before_firebase_and_publish_after_recovery(self):
        database = self.machine.db
        self.machine.db = None
        self.machine.publish_redemption_endpoint()
        self.assertIsNone(self.machine.redemption_published_url)
        self.machine.db = database
        self.machine.publish_redemption_endpoint()
        self.assertEqual(self.machine.redemption_published_url, self.machine.redemption_tunnel_url)


if __name__ == "__main__":
    unittest.main()
