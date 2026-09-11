"""Controller regressions using fake hardware and Firebase; no Pi required."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from machine.diagnostics import log
from machine.routes import create_apps
from machine.runtime import MachineRuntime
from machine.config import MACHINE_ID


class StateTests(unittest.TestCase):
    def setUp(self):
        self.machine = MachineRuntime()

    def test_import_and_construction_do_not_load_hardware_or_start_threads(self):
        result = subprocess.run(
            [sys.executable, "-B", "-c", """
import sys
import threading
before = set(threading.enumerate())
from machine_flow import MachineRuntime
machine = MachineRuntime()
assert set(threading.enumerate()) == before
assert not {'picamera2', 'gpiozero', 'ultralytics', 'serial', 'cv2',
            'firebase_admin', 'flask', 'lgpio'} & sys.modules.keys()
assert machine.db is None and machine.app is None
machine.close()
"""],
            cwd=Path(__file__).parent, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_instances_and_state_snapshots_are_independent(self):
        self.machine.update_state(itemCount=3, pointsEarned=3)
        snapshot = self.machine.get_state()
        snapshot["itemCount"] = 99
        self.assertEqual(self.machine.get_state()["itemCount"], 3)
        self.assertEqual(MachineRuntime().get_state()["itemCount"], 0)

    def test_rearm_keeps_customer_totals_but_reset_clears_them(self):
        self.machine.update_state(
            phase="accepted", itemCount=3, pointsEarned=3,
            bottleCount=2, canCount=1, batchSessionId="batch-1",
            sessionId="reward-1", qrCode="reward-qr",
        )
        self.machine.rearm_for_next_item()
        state = self.machine.get_state()
        self.assertEqual(state["phase"], "idle")
        self.assertEqual((state["itemCount"], state["pointsEarned"]), (3, 3))
        self.assertEqual(state["batchSessionId"], "batch-1")
        self.assertIsNone(state["qrCode"])
        self.machine.finish_session_event.set()
        self.machine.reset_state()
        state = self.machine.get_state()
        self.assertEqual((state["itemCount"], state["pointsEarned"]), (0, 0))
        self.assertIsNone(state["batchSessionId"])
        self.assertFalse(self.machine.finish_session_event.is_set())

    def test_green_button_queues_finish_only_for_a_nonempty_batch(self):
        self.machine.request_finish_recycling_session()
        self.assertFalse(self.machine.finish_session_event.is_set())
        self.machine.update_state(itemCount=2)
        self.machine.request_finish_recycling_session()
        self.assertTrue(self.machine.finish_session_event.is_set())
        self.assertEqual(self.machine.get_state()["phase"], "idle")

    def test_blue_button_preserves_recycling_batch_and_busy_phases(self):
        self.machine.update_state(itemCount=1)
        self.machine.request_water_refill()
        self.assertFalse(self.machine.recycling_paused.is_set())
        self.assertEqual(self.machine.get_state()["itemCount"], 1)
        for phase in ("sorting", "accepted", "reward_ready", "motion_detected"):
            self.machine.update_state(itemCount=0, phase=phase)
            self.machine.request_water_refill()
            self.assertEqual(self.machine.get_state()["phase"], phase)
        self.machine.reset_state()
        self.machine.request_water_refill()
        self.assertEqual(self.machine.get_state()["phase"], "water_refill_requested")
        self.assertTrue(self.machine.recycling_paused.is_set())

    def test_second_blue_press_requests_back_without_resuming_early(self):
        self.machine.request_water_refill()
        self.machine.request_water_refill()
        state = self.machine.get_state()
        self.assertIsNotNone(state["waterReturnRequestedAt"])
        self.assertEqual(state["phase"], "water_refill_requested")
        self.assertTrue(self.machine.recycling_paused.is_set())
        self.machine.reset_state()
        self.assertIsNone(self.machine.get_state()["waterReturnRequestedAt"])


class WaterPollingTests(unittest.TestCase):
    def setUp(self):
        self.machine = MachineRuntime()
        self.machine.db = Mock()
        self.machine.process_water_refill_request = Mock()
        self.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        self.request = self.machine.db.collection.return_value.document.return_value.get.return_value
        self.request.exists = True
        self.request.to_dict.return_value = {
            "status": "pending", "machineId": MACHINE_ID, "sessionId": "refill-1",
        }

    def run_worker(self, cycles=2):
        # Exercise complete loop iterations without sleeping or real hardware.
        with patch.object(self.machine.shutdown_event, "is_set", side_effect=[False] * cycles + [True]), \
             patch.object(self.machine.shutdown_event, "wait"):
            self.machine.water_request_worker()

    def test_idle_and_blue_button_without_qr_do_not_read_firestore(self):
        self.run_worker()
        self.machine.request_water_refill()
        self.run_worker()
        self.machine.db.collection.assert_not_called()

    def test_active_qr_reads_only_its_request_and_stops_after_processing(self):
        self.machine.start_water_request_polling("refill-1", self.expires_at)
        self.run_worker()
        self.machine.db.collection.assert_called_once_with("water_refill_requests")
        self.machine.db.collection.return_value.document.assert_called_once_with("refill-1")
        self.machine.process_water_refill_request.assert_called_once_with(self.request)
        self.assertIsNone(self.machine.get_water_request_session())

    def test_missing_request_keeps_waiting_for_phone(self):
        self.machine.start_water_request_polling("refill-1", self.expires_at)
        self.request.exists = False
        self.run_worker()
        self.assertEqual(self.machine.db.collection.call_count, 2)
        self.machine.process_water_refill_request.assert_not_called()
        self.assertEqual(self.machine.get_water_request_session(), "refill-1")

    def test_expired_or_reset_session_does_not_read_firestore(self):
        self.machine.start_water_request_polling(
            "refill-1", datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        self.run_worker()
        self.machine.start_water_request_polling("refill-1", self.expires_at)
        self.machine.reset_state()
        self.run_worker()
        self.machine.db.collection.assert_not_called()

    def test_terminal_request_stops_polling_without_dispensing(self):
        for status in ("completed", "cancelled", "expired", "failed"):
            with self.subTest(status=status):
                self.machine.start_water_request_polling("refill-1", self.expires_at)
                self.request.to_dict.return_value["status"] = status
                self.run_worker()
                self.assertIsNone(self.machine.get_water_request_session())
        self.machine.process_water_refill_request.assert_not_called()

    def test_other_machine_or_session_cannot_dispense(self):
        self.machine.start_water_request_polling("refill-1", self.expires_at)
        for field in ("machineId", "sessionId"):
            original = self.request.to_dict.return_value[field]
            self.request.to_dict.return_value[field] = "other"
            self.run_worker()
            self.request.to_dict.return_value[field] = original
        self.machine.process_water_refill_request.assert_not_called()

    def test_reset_during_read_prevents_processing(self):
        self.machine.start_water_request_polling("refill-1", self.expires_at)
        def reset_during_read():
            self.machine.reset_state()
            return self.request
        self.machine.db.collection.return_value.document.return_value.get.side_effect = reset_during_read
        self.run_worker()
        self.machine.process_water_refill_request.assert_not_called()

    def test_old_session_cannot_stop_new_session_polling(self):
        self.machine.start_water_request_polling("refill-2", self.expires_at)
        self.machine.stop_water_request_polling("refill-1")
        self.assertEqual(self.machine.get_water_request_session(), "refill-2")

    def test_transient_read_error_retries_active_session(self):
        self.machine.start_water_request_polling("refill-1", self.expires_at)
        self.machine.db.collection.return_value.document.return_value.get.side_effect = [
            RuntimeError("temporarily unavailable"), self.request,
        ]
        with self.assertLogs("ecorefill.machine", level="ERROR"):
            self.run_worker()
        self.machine.process_water_refill_request.assert_called_once_with(self.request)


class ButtonTests(unittest.TestCase):
    def test_gpio_callbacks_reach_the_machine_state(self):
        machine = MachineRuntime()
        green, blue = Mock(), Mock()
        factory = Mock(side_effect=[green, blue])
        with patch.dict(sys.modules, {"gpiozero": SimpleNamespace(Button=factory)}):
            machine.initialize_buttons()
        self.addCleanup(machine.close)
        machine.update_state(itemCount=1)
        green.when_pressed()
        self.assertTrue(machine.finish_session_event.is_set())
        machine.reset_state()
        blue.when_pressed()
        self.assertEqual(machine.get_state()["phase"], "water_refill_requested")

    def test_callback_setup_failure_releases_pin_and_still_initializes_other_button(self):
        class BrokenButton:
            close = Mock()

            @property
            def when_pressed(self):
                return None

            @when_pressed.setter
            def when_pressed(self, callback):
                raise RuntimeError("edge detection unavailable")

        for broken_index in (0, 1):
            with self.subTest(broken_index=broken_index):
                machine = MachineRuntime()
                broken = BrokenButton()
                broken.close = Mock()
                buttons = [Mock(), Mock()]
                buttons[broken_index] = broken
                with patch.dict(sys.modules, {
                    "gpiozero": SimpleNamespace(Button=Mock(side_effect=buttons)),
                }), self.assertLogs("ecorefill.machine", level="ERROR"):
                    machine.initialize_buttons()
                broken.close.assert_called_once_with()
                actual = [machine.green_button, machine.blue_button]
                self.assertIsNone(actual[broken_index])
                self.assertIs(actual[1 - broken_index], buttons[1 - broken_index])
                machine.close()

    def test_standalone_check_reports_presses_without_initializing_other_hardware(self):
        import check_buttons

        machine = MachineRuntime()
        green, blue = Mock(is_pressed=False), Mock(is_pressed=False)
        green.pin.state = blue.pin.state = 1

        def press_buttons(_delay):
            green.when_pressed()
            blue.when_pressed()
            raise KeyboardInterrupt

        with patch.object(check_buttons, "MachineRuntime", return_value=machine), \
             patch.object(check_buttons, "configure_logging"), \
             patch.dict(sys.modules, {"gpiozero": SimpleNamespace(
                 Button=Mock(side_effect=[green, blue]),
             )}), \
             patch.object(check_buttons.time, "sleep", side_effect=press_buttons), \
             patch("builtins.print") as output:
            self.assertEqual(check_buttons.main(), 0)
        output.assert_any_call("GREEN pressed", flush=True)
        output.assert_any_call("BLUE pressed", flush=True)
        green.close.assert_called_once_with()
        blue.close.assert_called_once_with()
        self.assertIsNone(machine.db)
        self.assertIsNone(machine.picam2)
        self.assertIsNone(machine.esp32)

    def test_diagnostic_reads_changes_even_when_callbacks_do_not_fire(self):
        import check_buttons

        green, blue = Mock(), Mock()
        green.pin.state = blue.pin.state = 1

        def press_green(_delay):
            green.pin.state = 0

        def release_green_press_blue(_delay):
            green.pin.state = 1
            blue.pin.state = 0

        changes = iter([press_green, release_green_press_blue])

        def advance(delay):
            action = next(changes, None)
            if action is None:
                raise KeyboardInterrupt
            action(delay)

        with patch.object(check_buttons.time, "sleep", side_effect=advance), \
             patch("builtins.print") as output, self.assertRaises(KeyboardInterrupt):
            check_buttons.monitor_inputs([("GREEN", green), ("BLUE", blue)])
        output.assert_any_call(
            "PIN LEVELS: GREEN=1 (released) | BLUE=1 (released)", flush=True,
        )
        output.assert_any_call(
            "PIN LEVELS: GREEN=0 (PRESSED) | BLUE=1 (released)", flush=True,
        )
        output.assert_any_call(
            "PIN LEVELS: GREEN=1 (released) | BLUE=0 (PRESSED)", flush=True,
        )


class SerialTests(unittest.TestCase):
    def setUp(self):
        self.machine = MachineRuntime()
        self.serial_patch = patch.dict(
            sys.modules, {"serial": SimpleNamespace(SerialException=OSError)},
        )
        self.serial_patch.start()
        self.addCleanup(self.serial_patch.stop)

    def connection(self, responses):
        connection = Mock(is_open=True)
        connection.readline.side_effect = responses
        return connection

    def test_sorting_normalizes_commands_and_blocks_unknown_commands(self):
        connection = self.connection([])
        self.machine.esp32 = connection
        self.assertFalse(self.machine.send_to_esp32("open_valve"))
        connection.write.assert_not_called()
        self.assertTrue(self.machine.send_to_esp32(" bottle "))
        connection.write.assert_called_once_with(b"BOTTLE\n")
        connection.readline.assert_not_called()

    def test_water_completion_notifies_dispensing_once(self):
        self.machine.esp32 = self.connection([
            b"DISPENSING WATER_500\n", b"DISPENSING WATER_500\n", b"OK WATER_500\n",
        ])
        on_dispensing = Mock()
        self.assertEqual(self.machine.run_water_command("water_500", on_dispensing), (True, None))
        on_dispensing.assert_called_once_with()
        self.machine.esp32.write.assert_called_once_with(b"WATER_500\n")

    def test_disconnect_after_dispensing_never_resends(self):
        connection = self.connection([b"DISPENSING WATER_500\n", OSError("USB lost")])
        self.machine.esp32 = connection
        with self.assertLogs("ecorefill.machine", level="ERROR"):
            result = self.machine.run_water_command("WATER_500")
        self.assertEqual(result, (False, "ESP32_DISCONNECTED_DURING_DISPENSING"))
        connection.write.assert_called_once_with(b"WATER_500\n")
        connection.close.assert_called_once_with()
        self.assertIsNone(self.machine.esp32)

    def test_disconnect_before_dispensing_reconnects_once(self):
        broken = self.connection([OSError("USB lost")])
        recovered = self.connection([b"OK WATER_250\n"])
        self.machine.get_esp32_connection = Mock(side_effect=[broken, recovered, recovered])
        with patch("machine.serial_controller.time.sleep"), self.assertLogs("ecorefill.machine", level="ERROR"):
            result = self.machine.run_water_command("WATER_250")
        self.assertEqual(result, (True, None))
        broken.write.assert_called_once_with(b"WATER_250\n")
        recovered.write.assert_called_once_with(b"WATER_250\n")

    def test_firmware_error_and_invalid_water_command_are_preserved(self):
        connection = self.connection([b"ERROR WATER_1000 NO_BOTTLE\n"])
        self.machine.esp32 = connection
        self.assertEqual(self.machine.run_water_command("BOTTLE"), (False, "INVALID_COMMAND: BOTTLE"))
        connection.write.assert_not_called()
        self.assertEqual(self.machine.run_water_command("WATER_1000"), (False, "ERROR WATER_1000 NO_BOTTLE"))


class APITests(unittest.TestCase):
    def setUp(self):
        self.machine = MachineRuntime()
        self.firebase_patch = patch.dict(sys.modules, {
            "firebase_admin": SimpleNamespace(firestore=SimpleNamespace(
                transactional=lambda callback: callback,
                SERVER_TIMESTAMP="server-timestamp",
            ), auth=Mock()),
        })
        self.firebase_patch.start()
        self.addCleanup(self.firebase_patch.stop)
        create_apps(self.machine)
        self.local = self.machine.app.test_client()
        self.public = self.machine.public_redeem_app.test_client()

    def test_local_api_operates_on_the_same_runtime_state_as_buttons(self):
        self.machine.update_state(itemCount=2, pointsEarned=2)
        self.assertEqual(self.local.get("/api/machine/state").json["itemCount"], 2)
        response = self.local.post("/api/machine/finish-recycling")
        self.assertTrue(response.json["finishRequested"])
        self.assertTrue(self.machine.finish_session_event.is_set())
        response = self.local.post("/api/machine/reset")
        self.assertEqual(response.json["state"]["itemCount"], 0)
        self.assertFalse(self.machine.finish_session_event.is_set())

    def test_public_server_exposes_only_rewards_and_payments(self):
        public_routes = {rule.rule for rule in self.machine.public_redeem_app.url_map.iter_rules()
                         if rule.endpoint != "static"}
        self.assertEqual(public_routes, {"/api/recycling/redeem", "/api/points/<action>"})
        for rule in self.machine.app.url_map.iter_rules():
            if rule.rule.startswith(("/api/machine/", "/api/water-refill/")):
                path = rule.rule.replace("<session_id>", "test-session")
                for method in rule.methods - {"OPTIONS", "HEAD"}:
                    with self.subTest(path=path, method=method):
                        self.assertEqual(self.public.open(path, method=method).status_code, 404)

    def test_missing_firebase_returns_service_unavailable(self):
        self.assertEqual(self.local.post("/api/water-refill/session").status_code, 503)
        self.assertEqual(self.public.post("/api/recycling/redeem").status_code, 503)

    def test_blue_press_after_touchscreen_entry_requests_back(self):
        self.local.post("/api/machine/pause-recycling")
        self.machine.request_water_refill()
        state = self.local.get("/api/machine/state").json
        self.assertIsNotNone(state["waterReturnRequestedAt"])
        self.assertTrue(self.machine.recycling_paused.is_set())

    def test_created_qr_starts_polling_and_expiry_stops_it(self):
        self.machine.db = Mock()
        response = self.local.post("/api/water-refill/session")
        self.assertEqual(response.status_code, 201)
        session_id = response.json["session"]["sessionId"]
        self.assertEqual(self.machine.get_water_request_session(), session_id)
        session_ref = self.machine.db.collection.return_value.document.return_value
        session_ref.get.return_value.to_dict.return_value = {
            "status": "waiting_for_user",
            "expiresAt": datetime.now(timezone.utc) - timedelta(seconds=1),
        }
        response = self.local.get(f"/api/water-refill/session/{session_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["session"]["status"], "expired")
        self.assertIsNone(self.machine.get_water_request_session())

    def test_failed_qr_creation_does_not_start_polling(self):
        self.machine.db = Mock()
        self.machine.db.collection.return_value.document.return_value.set.side_effect = RuntimeError("offline")
        with self.assertLogs("ecorefill.machine", level="ERROR"):
            response = self.local.post("/api/water-refill/session")
        self.assertEqual(response.status_code, 500)
        self.assertIsNone(self.machine.get_water_request_session())

    def test_cancel_unused_refill_restores_recycling_and_invalidates_qr(self):
        self.machine.db = Mock()
        session_ref = self.machine.db.collection.return_value.document.return_value
        session_ref.get.return_value.to_dict.return_value = {"status": "waiting_for_user"}
        self.machine.request_water_refill()
        self.machine.request_water_refill()
        self.machine.start_water_request_polling(
            "refill-1", datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        response = self.local.post("/api/water-refill/session/refill-1/cancel")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["session"]["status"], "cancelled")
        self.assertFalse(self.machine.recycling_paused.is_set())
        self.assertEqual(self.machine.get_state()["phase"], "idle")
        self.assertIsNone(self.machine.get_state()["waterReturnRequestedAt"])
        self.assertIsNone(self.machine.get_water_request_session())
        transaction = self.machine.db.transaction.return_value
        session_ref.get.assert_called_once_with(transaction=transaction)
        self.assertEqual(transaction.update.call_args.args[1]["status"], "cancelled")

    def test_cancel_started_refill_keeps_recycling_paused(self):
        for status in ("processing", "dispensing", "completed"):
            with self.subTest(status=status):
                self.machine.db = Mock()
                session_ref = self.machine.db.collection.return_value.document.return_value
                session_ref.get.return_value.to_dict.return_value = {"status": status}
                self.machine.recycling_paused.set()
                response = self.local.post("/api/water-refill/session/refill-1/cancel")
                self.assertEqual(response.status_code, 409)
                self.assertTrue(self.machine.recycling_paused.is_set())
                self.machine.db.transaction.return_value.update.assert_not_called()

    def test_cancel_failure_keeps_recycling_paused(self):
        self.machine.db = Mock()
        self.machine.db.transaction.side_effect = RuntimeError("Firebase unavailable")
        self.machine.recycling_paused.set()
        with self.assertLogs("ecorefill.machine", level="ERROR"):
            response = self.local.post("/api/water-refill/session/refill-1/cancel")
        self.assertEqual(response.status_code, 500)
        self.assertTrue(self.machine.recycling_paused.is_set())

    def test_redemption_requires_authentication_when_firebase_is_available(self):
        self.machine.db = Mock()
        with self.assertLogs("ecorefill.machine", level="ERROR"):
            response = self.public.post("/api/recycling/redeem", json={"code": "ecorefill://claim/test"})
        self.assertEqual(response.status_code, 401)
        self.machine.db.collection.assert_not_called()


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        for target in ("machine.runtime.WEIGHT_SENSOR_ENABLED", "machine.detection.WEIGHT_SENSOR_ENABLED"):
            enabled = patch(target, True)
            enabled.start()
            self.addCleanup(enabled.stop)

    def test_disabled_weight_sensor_does_not_open_gpio(self):
        machine = MachineRuntime()
        with patch("machine.runtime.WEIGHT_SENSOR_ENABLED", False), \
             patch("weight_sensor.CalibratedScale") as factory:
            machine.initialize_weight_sensor()
            factory.assert_not_called()
        self.assertIsNone(machine.weight_scale)
        machine.close()

    def test_weight_initialization_and_shutdown_use_saved_calibration(self):
        machine = MachineRuntime()
        with patch("weight_sensor.CalibratedScale") as factory:
            machine.initialize_weight_sensor()
            self.assertIs(machine.weight_scale, factory.return_value)
            factory.return_value.open.assert_called_once_with()
            machine.close()
            machine.close()
            factory.return_value.close.assert_called_once_with()

    def test_weight_initialization_failure_keeps_sensor_unavailable(self):
        machine = MachineRuntime()
        with patch("weight_sensor.CalibratedScale") as factory, \
             self.assertLogs("ecorefill.machine", level="ERROR"):
            factory.return_value.open.side_effect = OSError("GPIO busy")
            machine.initialize_weight_sensor()
        self.assertIsNone(machine.weight_scale)
        with self.assertLogs("ecorefill.machine", level="ERROR"):
            result = machine.apply_weight_check({"accepted": True, "category": "can", "points": 1})
        self.assertFalse(result["accepted"])
        self.assertEqual(result["points"], 0)
        machine.close()

    def test_partial_startup_failure_closes_initialized_resources(self):
        machine = MachineRuntime()
        camera = Mock()
        with patch.dict(sys.modules, {"ultralytics": SimpleNamespace(YOLO=Mock())}), \
             patch("machine.runtime.os.path.exists", return_value=True), \
             patch.object(machine, "initialize_firebase", return_value=None), \
             patch.object(machine, "initialize_camera", return_value=camera), \
             patch.object(machine, "connect_to_esp32", side_effect=RuntimeError("USB setup failed")):
            with self.assertRaisesRegex(RuntimeError, "USB setup failed"):
                machine.start()
        camera.stop.assert_called_once_with()
        camera.close.assert_called_once_with()
        self.assertTrue(machine.shutdown_event.is_set())
        self.assertIsNone(machine.worker_thread)
        machine.close()
        camera.close.assert_called_once_with()

    def test_start_initializes_before_workers_and_is_idempotent(self):
        machine = MachineRuntime()
        with patch.dict(sys.modules, {"ultralytics": SimpleNamespace(YOLO=Mock())}), \
             patch("machine.runtime.os.path.exists", return_value=True), \
             patch.object(machine, "initialize_firebase", return_value=None), \
             patch.object(machine, "initialize_camera", return_value=Mock()), \
             patch.object(machine, "connect_to_esp32", return_value=None), \
             patch.object(machine, "initialize_weight_sensor") as weight, \
             patch.object(machine, "initialize_buttons") as buttons, \
             patch.object(machine, "start_redemption_tunnel") as tunnel, \
             patch("machine.upload_queue.RecyclingUploadQueue"), \
             patch("machine.runtime.create_apps") as apps, \
             patch("machine.runtime.threading.Thread") as thread:
            def check_ready():
                buttons.assert_called_once_with()
                weight.assert_called_once_with()
                apps.assert_called_once_with(machine)
                self.assertIsNotNone(machine.picam2)
            thread.return_value.start.side_effect = check_ready
            machine.start()
            machine.start()
            self.assertEqual(thread.call_count, 3)
            self.assertEqual(thread.return_value.start.call_count, 3)
            tunnel.assert_called_once_with()
            machine.close()

    def test_error_logs_include_original_traceback_and_call_site(self):
        with self.assertLogs("ecorefill.machine", level="ERROR") as captured:
            try:
                raise ValueError("camera failure")
            except ValueError as error:
                log("Capture failed:", error)
        record = captured.records[0]
        self.assertEqual(record.filename, Path(__file__).name)
        self.assertIs(record.exc_info[0], ValueError)
        self.assertIn("camera failure", record.getMessage())


class RecyclingWeightTests(unittest.TestCase):
    def setUp(self):
        enabled = patch("machine.detection.WEIGHT_SENSOR_ENABLED", True)
        enabled.start()
        self.addCleanup(enabled.stop)

    def test_overweight_item_is_recorded_and_rejected_without_changing_batch_totals(self):
        for category, item, grams in (("bottle", "plastic_bottle", 301),
                                      ("can", "aluminum_can", 301)):
            with self.subTest(category=category):
                machine = MachineRuntime()
                machine.update_state(itemCount=2, pointsEarned=2, bottleCount=1,
                                     canCount=1, batchSessionId="existing-batch")
                machine.weight_scale = Mock()
                machine.weight_scale.read_weight.return_value = {"grams": grams}
                result = machine.apply_weight_check({
                    "accepted": True, "category": category, "item": item,
                    "points": 1, "confidence": 0.99,
                })
                machine.wait_for_item_motion = Mock(return_value=object())
                machine.verify_item = Mock(return_value=result)
                machine.frame_to_base64_data_url = Mock(return_value="test-image")
                machine.send_to_esp32 = Mock()
                machine.save_local_session = Mock()

                def save(*args):
                    machine.shutdown_event.set()
                    return True

                machine.queue_recycling_upload = Mock(side_effect=save)
                machine.recycling_upload_queue = Mock()
                machine.recycling_upload_queue.contains.return_value = True
                with patch.dict(sys.modules, {
                    "firebase_admin": SimpleNamespace(firestore=Mock()),
                    "cv2": SimpleNamespace(imwrite=Mock(return_value=True)),
                }):
                    machine.machine_worker()
                state = machine.get_state()
                self.assertEqual(state["phase"], "rejected")
                self.assertEqual((state["itemCount"], state["pointsEarned"]), (2, 2))
                self.assertEqual((state["bottleCount"], state["canCount"]), (1, 1))
                self.assertEqual(state["batchSessionId"], "existing-batch")
                self.assertIn("weight limit", state["message"])
                machine.send_to_esp32.assert_called_once_with("REJECT")
                saved = machine.queue_recycling_upload.call_args.args[1]
                self.assertEqual(saved["inspection"]["weight"]["grams"], grams)
                self.assertEqual(saved["points"], 0)
                machine.close()


if __name__ == "__main__":
    unittest.main()
