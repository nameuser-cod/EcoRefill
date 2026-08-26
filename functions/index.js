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

exports.redeemRecyclingReward = onCall(
  async (request) => {
    if (!request.auth) {
      throw new HttpsError(
        "unauthenticated",
        "You must be signed in to redeem this reward."
      );
    }

    const userId = request.auth.uid;
    const userEmail =
      request.auth.token.email || "";
    const scannedCode = String(
      request.data?.code || ""
    ).trim();
    const claimPrefix =
      "ecorefill://claim/";

    if (!scannedCode) {
      throw new HttpsError(
        "invalid-argument",
        "QR code is required."
      );
    }

    if (!scannedCode.startsWith(claimPrefix)) {
      throw new HttpsError(
        "invalid-argument",
        "Invalid EcoRefill recycling QR code."
      );
    }

    const sessionId = scannedCode
      .slice(claimPrefix.length)
      .trim();

    if (!sessionId) {
      throw new HttpsError(
        "invalid-argument",
        "Invalid reward session ID."
      );
    }

    const rewardRef = db
      .collection("redeem_qr_codes")
      .doc(sessionId);
    const userRef = db
      .collection("users")
      .doc(userId);
    const recyclingRecordRef = db
      .collection("recycling_records")
      .doc(sessionId);
    const transactionRef = db
      .collection("transactions")
      .doc();

    let redemptionResult;

    await db.runTransaction(
      async (transaction) => {
        const [
          rewardSnapshot,
          userSnapshot,
          recyclingSnapshot,
        ] = await Promise.all([
          transaction.get(rewardRef),
          transaction.get(userRef),
          transaction.get(recyclingRecordRef),
        ]);

        if (!rewardSnapshot.exists) {
          throw new HttpsError(
            "not-found",
            "This reward QR code does not exist."
          );
        }

        if (!userSnapshot.exists) {
          throw new HttpsError(
            "not-found",
            "Your EcoRefill account was not found."
          );
        }

        const reward =
          rewardSnapshot.data() || {};
        const user =
          userSnapshot.data() || {};

        if (
          reward.code !== sessionId ||
          reward.sessionId !== sessionId
        ) {
          throw new HttpsError(
            "failed-precondition",
            "The QR code does not match this reward."
          );
        }

        if (reward.status === "claimed") {
          if (reward.claimedBy === userId) {
            throw new HttpsError(
              "already-exists",
              "You already claimed this recycling reward."
            );
          }

          throw new HttpsError(
            "failed-precondition",
            "This reward has already been claimed."
          );
        }

        if (reward.status !== "unclaimed") {
          throw new HttpsError(
            "failed-precondition",
            "This recycling reward is no longer available."
          );
        }

        if (
          reward.expiresAt?.toMillis &&
          reward.expiresAt.toMillis() < Date.now()
        ) {
          throw new HttpsError(
            "deadline-exceeded",
            "This recycling QR code has expired."
          );
        }

        const pointsEarned = Number(
          reward.pointsEarned || 0
        );
        const currentPoints = Number(
          user.points || 0
        );

        if (
          !Number.isFinite(pointsEarned) ||
          pointsEarned <= 0
        ) {
          throw new HttpsError(
            "failed-precondition",
            "This reward contains invalid points."
          );
        }

        if (!Number.isFinite(currentPoints)) {
          throw new HttpsError(
            "internal",
            "Your point balance is invalid."
          );
        }

        const totalPoints =
          currentPoints + pointsEarned;
        const timestamp =
          FieldValue.serverTimestamp();

        transaction.update(userRef, {
          points: totalPoints,
          updatedAt: timestamp,
        });

        transaction.update(rewardRef, {
          status: "claimed",
          claimedBy: userId,
          claimedAt: timestamp,
          updatedAt: timestamp,
        });

        if (recyclingSnapshot.exists) {
          transaction.update(
            recyclingRecordRef,
            {
              claimedBy: userId,
              claimedAt: timestamp,
              updatedAt: timestamp,
            }
          );
        }

        transaction.set(transactionRef, {
          type: "recycling",
          userId,
          userEmail,
          machineId:
            reward.machineId || "machine_001",
          materialType:
            reward.materialType ||
            "recyclable_item",
          category: reward.category || "",
          pointsEarned,
          previousPoints: currentPoints,
          pointsAfter: totalPoints,
          status: "completed",
          qrCode: scannedCode,
          sessionId,
          createdAt: timestamp,
          updatedAt: timestamp,
        });

        redemptionResult = {
          pointsEarned,
          totalPoints,
        };
      }
    );

    return {
      ok: true,
      message:
        "Recycling reward claimed successfully.",
      ...redemptionResult,
    };
  }
);
