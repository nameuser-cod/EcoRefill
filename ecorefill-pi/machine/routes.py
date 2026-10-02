"""Register HTTP routes without starting a server or hardware."""


def create_apps(runtime):
    import os
    from pathlib import Path
    from flask import Flask, send_from_directory
    from flask_cors import CORS
    from machine.point_payments import register_payment_routes
    from .push_notifications import register_notification_routes

    runtime.app = Flask("ecorefill.machine")
    kiosk_dir = Path(os.getenv("ECOREFILL_KIOSK_DIR", str(
        Path(__file__).resolve().parents[1] / "kiosk-dist"
    )))

    def kiosk_page(path=""):
        return send_from_directory(kiosk_dir, "kiosk.html")

    runtime.app.add_url_rule('/machine', 'kiosk_home', kiosk_page)
    runtime.app.add_url_rule('/machine/<path:path>', 'kiosk_page', kiosk_page)
    runtime.app.add_url_rule('/assets/<path:path>', 'kiosk_asset',
                             lambda path: send_from_directory(kiosk_dir / 'assets', path))
    CORS(runtime.app)
    # The public server exposes authenticated redemption, payments, and phone
    # registration. Machine controls remain on the local server.
    runtime.public_redeem_app = Flask("ecorefill.machine.public_redeem")
    CORS(runtime.public_redeem_app)
    for app in (runtime.app, runtime.public_redeem_app):
        register_payment_routes(app, lambda: runtime.db, runtime.require_firebase_user)
        register_notification_routes(app, lambda: runtime.db, runtime.require_firebase_user)

    runtime.app.add_url_rule(
        '/api/machine/state', endpoint='api_machine_state',
        view_func=runtime.api_machine_state, methods=['GET'],
    )
    runtime.app.add_url_rule(
        '/api/machine/start', endpoint='api_machine_start',
        view_func=runtime.api_machine_start, methods=['POST'],
    )
    runtime.app.add_url_rule(
        '/api/machine/reset', endpoint='api_machine_reset',
        view_func=runtime.api_machine_reset, methods=['POST'],
    )
    runtime.app.add_url_rule(
        '/api/machine/finish-recycling', endpoint='api_machine_finish_recycling',
        view_func=runtime.api_machine_finish_recycling, methods=['POST'],
    )
    runtime.app.add_url_rule(
        '/api/machine/pause-recycling', endpoint='api_machine_pause_recycling',
        view_func=runtime.api_machine_pause_recycling, methods=['POST'],
    )
    runtime.app.add_url_rule(
        '/api/machine/resume-recycling', endpoint='api_machine_resume_recycling',
        view_func=runtime.api_machine_resume_recycling, methods=['POST'],
    )
    runtime.app.add_url_rule(
        '/api/water-refill/session', endpoint='api_create_water_refill_session',
        view_func=runtime.api_create_water_refill_session, methods=['POST'],
    )
    runtime.app.add_url_rule(
        '/api/water-refill/session/<session_id>', endpoint='api_get_water_refill_session',
        view_func=runtime.api_get_water_refill_session, methods=['GET'],
    )
    runtime.app.add_url_rule(
        '/api/water-refill/session/<session_id>/cancel', endpoint='api_cancel_water_refill_session',
        view_func=runtime.api_cancel_water_refill_session, methods=['POST'],
    )
    runtime.app.add_url_rule(
        '/api/water-refill/session/<session_id>/complete', endpoint='api_complete_water_refill_session',
        view_func=runtime.api_complete_water_refill_session, methods=['POST'],
    )
    runtime.app.add_url_rule(
        '/api/recycling/redeem', endpoint='api_redeem_recycling_reward',
        view_func=runtime.api_redeem_recycling_reward, methods=['POST'],
    )
    runtime.public_redeem_app.add_url_rule(
        '/api/recycling/redeem', endpoint='api_redeem_recycling_reward',
        view_func=runtime.api_redeem_recycling_reward, methods=['POST'],
    )
