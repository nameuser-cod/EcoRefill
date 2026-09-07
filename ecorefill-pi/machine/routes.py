"""Register HTTP routes without starting a server or hardware."""


def create_apps(runtime):
    from flask import Flask
    from flask_cors import CORS
    from point_payments import register_payment_routes

    runtime.app = Flask("ecorefill.machine")
    CORS(runtime.app)
    # Only redemption and payment routes are exposed by the public server.
    runtime.public_redeem_app = Flask("ecorefill.machine.public_redeem")
    CORS(runtime.public_redeem_app)
    for app in (runtime.app, runtime.public_redeem_app):
        register_payment_routes(app, lambda: runtime.db, runtime.require_firebase_user)

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
