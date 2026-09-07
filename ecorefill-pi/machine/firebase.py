"""Firebase Admin initialization and request authentication."""

import os
from .diagnostics import log


class FirebaseSupport:
    """Methods composed into MachineRuntime; shared resources live on that instance."""

    def initialize_firebase(self):
        """
        Tries, in order:
        1. Existing initialized Firebase app
        2. FIREBASE_SERVICE_ACCOUNT environment variable
        3. ./serviceAccountKey.json
        4. Google Application Default Credentials

        Recycling can still run if Firebase is unavailable.
        Water purchase confirmation will return an error until
        Firebase Admin is configured.
        """
        from firebase_admin import credentials
        import firebase_admin
        from firebase_admin import firestore

        if firebase_admin._apps:
            return firestore.client()

        credential_path = os.getenv(
            "FIREBASE_SERVICE_ACCOUNT",
            "serviceAccountKey.json",
        )

        try:
            if os.path.exists(credential_path):
                cred = credentials.Certificate(credential_path)
                firebase_admin.initialize_app(cred)
                log(
                    f"Firebase Admin initialized using "
                    f"{credential_path}"
                )
            else:
                firebase_admin.initialize_app()
                log(
                    "Firebase Admin initialized using "
                    "Application Default Credentials."
                )

            return firestore.client()

        except Exception as error:
            log("Firebase Admin is not configured:", error)
            log(
                "Water QR sessions will work, but user point "
                "deduction will not work until Firebase Admin "
                "credentials are configured."
            )
            return None

    def require_firebase_user(self):
        """
        Reads Authorization: Bearer <Firebase ID token>
        and returns decoded Firebase token.
        """
        from firebase_admin import auth as firebase_auth
        from flask import request

        auth_header = request.headers.get("Authorization", "").strip()

        if not auth_header.startswith("Bearer "):
            raise ValueError("Missing Firebase authentication token.")

        id_token = auth_header.split("Bearer ", 1)[1].strip()

        if not id_token:
            raise ValueError("Missing Firebase authentication token.")

        return firebase_auth.verify_id_token(id_token)
