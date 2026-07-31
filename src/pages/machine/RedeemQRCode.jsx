import { useEffect, useRef, useState } from "react";
import {
  Navigate,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { QRCodeCanvas } from "qrcode.react";
import {
  doc,
  serverTimestamp,
  setDoc,
  Timestamp,
} from "firebase/firestore";
import {
  AlertTriangle,
  CheckCircle2,
  Home,
  LoaderCircle,
  QrCode,
  Recycle,
  Timer,
} from "lucide-react";
import { db } from "../../firebase/firebase";
import "../../styles/theme.css";

const API_BASE_URL =
  import.meta.env.VITE_MACHINE_API_URL ||
  "http://192.168.101.23:5000";

function RedeemQRCode() {
  const navigate = useNavigate();
  const location = useLocation();

  const machineResult = location.state;
  const savedRef = useRef(false);

  const [saving, setSaving] = useState(true);
  const [saveError, setSaveError] = useState("");

  useEffect(() => {
    if (
      !machineResult?.sessionId ||
      !machineResult?.qrCode ||
      savedRef.current
    ) {
      return;
    }

    savedRef.current = true;

    const saveRedeemCode = async () => {
      try {
        setSaving(true);
        setSaveError("");

        const pointsEarned = Number(
          machineResult.pointsEarned || 0
        );

        if (
          !Number.isFinite(pointsEarned) ||
          pointsEarned <= 0
        ) {
          throw new Error(
            "The machine returned an invalid point value."
          );
        }

        const expiresAt = Timestamp.fromMillis(
          Date.now() + 5 * 60 * 1000
        );

        await setDoc(
          doc(
            db,
            "redeem_qr_codes",
            machineResult.sessionId
          ),
          {
            code: String(
              machineResult.qrCode
            ).trim(),

            sessionId:
              machineResult.sessionId,

            machineId:
              machineResult.machineId ||
              "machine_001",

            materialType:
              machineResult.materialType ||
              "recyclable_item",

            category:
              machineResult.category || "",

            pointsEarned,

            confidence: Number(
              machineResult.confidence || 0
            ),

            status: "unclaimed",

            claimedBy: "",

            claimedAt: null,

            createdAt: serverTimestamp(),

            expiresAt,
          },
          {
            merge: false,
          }
        );
      } catch (error) {
        console.error(
          "Error saving redeem QR code:",
          error
        );

        if (
          error?.code === "permission-denied"
        ) {
          setSaveError(
            "Firestore denied the reward record. Check your Firestore security rules or machine authentication."
          );
        } else {
          setSaveError(
            error?.message ||
              "The reward record could not be saved. Please try again."
          );
        }
      } finally {
        setSaving(false);
      }
    };

    saveRedeemCode();
  }, [machineResult]);

  if (
    !machineResult?.accepted ||
    !machineResult?.sessionId ||
    !machineResult?.qrCode
  ) {
    return (
      <Navigate
        to="/machine"
        replace
      />
    );
  }

  const getMaterialLabel = (value) => {
    const normalizedValue = String(
      value || ""
    )
      .toLowerCase()
      .trim();

    if (
      normalizedValue ===
        "plastic_bottle" ||
      normalizedValue ===
        "plastic bottle" ||
      normalizedValue === "bottle"
    ) {
      return "Plastic Bottle";
    }

    if (
      normalizedValue ===
        "aluminum_can" ||
      normalizedValue ===
        "aluminum can" ||
      normalizedValue === "can"
    ) {
      return "Aluminum Can";
    }

    return "Recyclable Material";
  };

  const returnHome = async () => {
    if (saving || saveError) {
      return;
    }

    try {
      await fetch(
        `${API_BASE_URL}/api/machine/reset`,
        {
          method: "POST",
        }
      );
    } catch (error) {
      console.error(
        "Unable to reset machine state:",
        error
      );
    } finally {
      navigate("/machine", {
        replace: true,
      });
    }
  };

  const retrySaving = () => {
    savedRef.current = false;
    setSaveError("");
    setSaving(true);

    window.location.reload();
  };

  return (
    <div className="machine-page">
      <div className="machine-shell qr-shell">
        <header className="machine-header">
          <div className="machine-brand">
            <div className="machine-logo">
              <Recycle size={42} />
            </div>

            <div>
              <h1>EcoRefill</h1>
              <p>QR Code Redemption</p>
            </div>
          </div>

          <div
            className={`machine-online ${
              saveError
                ? "machine-offline"
                : ""
            }`}
          >
            <span></span>

            {saveError
              ? "Reward Error"
              : "Online"}
          </div>
        </header>

        <main className="qr-main-card">
          <div className="success-icon">
            <CheckCircle2 size={72} />
          </div>

          <h2>Item Accepted!</h2>

          <p className="qr-subtitle">
            The machine successfully detected and
            sorted your item.
          </p>

          <div className="qr-info-grid">
            <div className="qr-info-card">
              <Recycle size={34} />

              <p>Material</p>

              <h3>
                {getMaterialLabel(
                  machineResult.materialType
                )}
              </h3>
            </div>

            <div className="qr-info-card">
              <QrCode size={34} />

              <p>Points Earned</p>

              <h3>
                +
                {Number(
                  machineResult.pointsEarned || 0
                )}{" "}
                Points
              </h3>
            </div>
          </div>

          {saveError ? (
            <div className="scan-error-message">
              <AlertTriangle size={28} />

              <div>
                <h3>
                  Reward could not be saved
                </h3>

                <p>{saveError}</p>

                <button
                  type="button"
                  className="machine-primary-btn"
                  onClick={retrySaving}
                >
                  Try Saving Again
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="qr-code-box">
                <QRCodeCanvas
                  value={String(
                    machineResult.qrCode
                  ).trim()}
                  size={280}
                  bgColor="#E3EED4"
                  fgColor="#0F2A1D"
                  level="H"
                  includeMargin
                />

                <p className="qr-code-value">
                  {machineResult.sessionId}
                </p>
              </div>

              <div className="qr-instruction-card">
                {saving ? (
                  <LoaderCircle
                    size={30}
                    className="machine-spin"
                  />
                ) : (
                  <Timer size={30} />
                )}

                <div>
                  <h3>
                    {saving
                      ? "Saving reward..."
                      : "Scan this QR code"}
                  </h3>

                  <p>
                    {saving
                      ? "Please wait while the reward is being stored securely."
                      : "Open the EcoRefill mobile app, tap Scan QR, and scan this code to redeem your points."}
                  </p>

                  {!saving && (
                    <p>
                      This QR reward expires after
                      five minutes and can only be
                      claimed once.
                    </p>
                  )}
                </div>
              </div>
            </>
          )}

          <div className="qr-actions">
            <button
              type="button"
              className="machine-primary-btn"
              onClick={returnHome}
              disabled={saving || Boolean(saveError)}
            >
              {saving ? (
                <LoaderCircle
                  size={28}
                  className="machine-spin"
                />
              ) : (
                <Home size={28} />
              )}

              {saving
                ? "Saving Reward..."
                : saveError
                ? "Fix Reward Error"
                : "Finish"}
            </button>
          </div>
        </main>
      </div>
    </div>
  );
}

export default RedeemQRCode;
