const {
  onCall,
  HttpsError,
} = require("firebase-functions/v2/https");

const {
  initializeApp,
} = require("firebase-admin/app");

const {
  getFirestore,
  FieldValue,
} = require("firebase-admin/firestore");

initializeApp();

const db = getFirestore();

const WATER_OPTIONS = {
  250: 3,
  500: 5,
  1000: 10,
};

exports.confirmWaterRefill = onCall(
  async (request) => {
    // -----------------------------------------
    // 1. Require Firebase login
    // -----------------------------------------

    if (!request.auth) {
      throw new HttpsError(
        "unauthenticated",
        "You must be logged in to refill water."
      );
    }

    const userId = request.auth.uid;

    const sessionId = String(
      request.data?.sessionId || ""
    ).trim();

    const waterAmountMl = Number(
      request.data?.waterAmountMl
    );

    if (!sessionId) {
      throw new HttpsError(
        "invalid-argument",
        "A refill session ID is required."
      );
    }

    if (
      !Object.prototype.hasOwnProperty.call(
        WATER_OPTIONS,
        waterAmountMl
      )
    ) {
      throw new HttpsError(
        "invalid-argument",
        "Choose 250 ml, 500 ml, or 1000 ml."
      );
    }

    const pointsRequired =
      WATER_OPTIONS[waterAmountMl];

    const userRef = db
      .collection("users")
      .doc(userId);

    const sessionRef = db
      .collection("water_refill_sessions")
      .doc(sessionId);

    const commandRef = db
      .collection("machine_commands")
      .doc();

    const transactionRef = db
      .collection("transactions")
      .doc();

    let remainingPoints = 0;
    let machineId = "";

    // -----------------------------------------
    // 2. Atomic purchase transaction
    // -----------------------------------------

    await db.runTransaction(
      async (transaction) => {
        const sessionSnapshot =
          await transaction.get(sessionRef);

        const userSnapshot =
          await transaction.get(userRef);

        if (!sessionSnapshot.exists) {
          throw new HttpsError(
            "not-found",
            "This water refill session does not exist."
          );
        }

        if (!userSnapshot.exists) {
          throw new HttpsError(
            "not-found",
            "Your EcoRefill account could not be found."
          );
        }

        const session =
          sessionSnapshot.data() || {};

        const user =
          userSnapshot.data() || {};

        if (
          session.status !==
          "waiting_for_user"
        ) {
          throw new HttpsError(
            "failed-precondition",
            "This refill QR has already been used, cancelled, or expired."
          );
        }

        machineId = String(
          session.machineId || ""
        ).trim();

        if (!machineId) {
          throw new HttpsError(
            "failed-precondition",
            "This refill session has no machine ID."
          );
        }

        const expiresAt =
          session.expiresAt;

        if (
          expiresAt?.toMillis &&
          expiresAt.toMillis() <
            Date.now()
        ) {
          throw new HttpsError(
            "deadline-exceeded",
            "This water refill QR has expired."
          );
        }

        const currentPoints = Number(
          user.points || 0
        );

        if (
          !Number.isFinite(
            currentPoints
          )
        ) {
          throw new HttpsError(
            "internal",
            "Your point balance is invalid."
          );
        }

        if (
          currentPoints <
          pointsRequired
        ) {
          throw new HttpsError(
            "failed-precondition",
            "You do not have enough points for this refill."
          );
        }

        remainingPoints =
          currentPoints -
          pointsRequired;

        // Deduct points.
        transaction.update(
          userRef,
          {
            points:
              remainingPoints,

            updatedAt:
              FieldValue.serverTimestamp(),
          }
        );

        // Claim refill session.
        transaction.update(
          sessionRef,
          {
            status:
              "waiting_for_machine",

            userId,

            waterAmountMl,

            pointsUsed:
              pointsRequired,

            commandId:
              commandRef.id,

            updatedAt:
              FieldValue.serverTimestamp(),
          }
        );

        // Command for Raspberry Pi.
        transaction.set(
          commandRef,
          {
            commandId:
              commandRef.id,

            machineId,

            sessionId,

            userId,

            command:
              `WATER_${waterAmountMl}`,

            waterAmountMl,

            pointsUsed:
              pointsRequired,

            status:
              "pending",

            createdAt:
              FieldValue.serverTimestamp(),

            updatedAt:
              FieldValue.serverTimestamp(),
          }
        );

        // User history.
        transaction.set(
          transactionRef,
          {
            type:
              "water_refill",

            userId,

            machineId,

            sessionId,

            commandId:
              commandRef.id,

            waterAmountMl,

            pointsUsed:
              pointsRequired,

            previousPoints:
              currentPoints,

            pointsAfter:
              remainingPoints,

            status:
              "waiting_for_machine",

            createdAt:
              FieldValue.serverTimestamp(),

            updatedAt:
              FieldValue.serverTimestamp(),
          }
        );
      }
    );

    return {
      ok: true,
      sessionId,
      machineId,
      waterAmountMl,
      pointsUsed:
        pointsRequired,
      remainingPoints,
    };
  }
);