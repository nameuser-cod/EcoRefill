"""Local kiosk state and recycling controls."""




class MachineAPI:
    """Methods composed into MachineRuntime; shared resources live on that instance."""

    def api_machine_state(self):
        from flask import jsonify

        return jsonify(self.get_state())

    def api_machine_start(self):
        """Compatibility endpoint. Automatic camera watching is already on."""
        from flask import jsonify

        self.recycling_paused.clear()

        current_state = self.get_state()
        if current_state["phase"] in {"rejected", "error"}:
            self.reset_state()

        return jsonify({
            "ok": True,
            "automatic": True,
            "message": "Automatic camera detection is active.",
            "state": self.get_state(),
        })

    def api_machine_reset(self):
        """Clear the current result and immediately re-arm auto detection."""
        from flask import jsonify

        self.recycling_paused.clear()
        self.reset_state()

        return jsonify({
            "ok": True,
            "automatic": True,
            "state": self.get_state(),
        })

    def api_machine_finish_recycling(self):
        """
        Test/maintenance equivalent of pressing the physical green button.
        The real kiosk flow should use the GPIO button.
        """
        from flask import jsonify

        self.request_finish_recycling_session()

        return jsonify({
            "ok": True,
            "finishRequested": self.finish_session_event.is_set(),
            "state": self.get_state(),
        })

    def api_machine_pause_recycling(self):
        """Optional helper for screens such as water refill/maintenance."""
        from flask import jsonify

        self.recycling_paused.set()

        if self.get_state()["phase"] not in {"accepted", "sorting"}:
            self.reset_state()

        return jsonify({
            "ok": True,
            "automatic": False,
            "message": "Automatic recycling detection paused.",
            "state": self.get_state(),
        })

    def api_machine_resume_recycling(self):
        from flask import jsonify

        self.recycling_paused.clear()

        if self.get_state()["phase"] not in {"accepted", "sorting"}:
            self.reset_state()

        return jsonify({
            "ok": True,
            "automatic": True,
            "message": "Automatic recycling detection resumed.",
            "state": self.get_state(),
        })
