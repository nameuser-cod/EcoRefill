"""Diagnostic regressions without motor power or Pi hardware."""

from types import SimpleNamespace
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import check_servos


class ServoDiagnosticTests(unittest.TestCase):
    def test_rejects_gpio_that_is_not_routed_to_pwm(self):
        result = SimpleNamespace(returncode=0, stdout="18: ip pd | lo // GPIO18 = input", stderr="")
        with patch.object(check_servos.subprocess, "run", return_value=result), patch("builtins.print"):
            self.assertFalse(check_servos.check_routing(("gate",)))

    def test_recognizes_pi5_channel_mapping(self):
        results = [
            SimpleNamespace(returncode=0, stdout="18: a3 pd | lo // GPIO18 = PWM0_CHAN2", stderr=""),
            SimpleNamespace(returncode=0, stdout="19: a3 pd | lo // GPIO19 = PWM0_CHAN3", stderr=""),
        ]
        with patch.object(check_servos.subprocess, "run", side_effect=results), patch("builtins.print"):
            self.assertTrue(check_servos.check_routing(("gate", "sort")))

    def test_unavailable_pinctrl_does_not_claim_routing_is_valid(self):
        with patch.object(check_servos.subprocess, "run", side_effect=FileNotFoundError("pinctrl")), \
             patch("builtins.print"):
            self.assertFalse(check_servos.check_routing(("gate",)))

    def test_only_selected_servo_moves_and_pwm_stops(self):
        hardware = Mock(servos={"gate": Mock(), "sort": Mock()})
        with patch.object(check_servos.time, "sleep"), patch("builtins.print"):
            check_servos.exercise_servo(hardware, "gate", Mock())
        self.assertEqual([call.args for call in hardware.servo.call_args_list], [
            ("gate", 1450), ("gate", 2200), ("gate", 500), ("gate", 1450),
        ])
        hardware.servos["gate"].close.assert_called_once()
        hardware.servos["sort"].close.assert_not_called()
        hardware.pump.assert_not_called()

    def test_interrupt_stops_servo_pwm(self):
        hardware = Mock(servos={"gate": Mock()})
        with patch.object(check_servos.time, "sleep", side_effect=KeyboardInterrupt), \
             patch("builtins.print"), self.assertRaises(KeyboardInterrupt):
            check_servos.exercise_servo(hardware, "gate", Mock())
        hardware.servos["gate"].close.assert_called_once()

    def test_diagnose_only_never_opens_hardware(self):
        with patch("sys.argv", ["check_servos.py", "--diagnose-only"]), \
             patch.object(check_servos, "check_routing", return_value=True), \
             patch.object(check_servos, "find_pwm_chip", return_value=Path('/sys/class/pwm/pwmchip0')), \
             patch.object(check_servos, "show_pwm_state"), \
             patch.object(check_servos, "PiGPIOHardware") as factory, \
             patch.object(check_servos.signal, "signal"), patch("builtins.print"):
            self.assertEqual(check_servos.main(), 0)
        factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
