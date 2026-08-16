import {
  useEffect,
  useRef,
  useState,
} from "react";
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
  ScanLine,
  Sparkles,
  Timer,
} from "lucide-react";
import { db } from "../../firebase/firebase";
import "../../styles/machine.css";

const API_BASE_URL =
  import.meta.env.VITE_MACHINE_API_URL ||
  "http://192.168.101.23 :5000";

function RedeemQRCode() {
  const navigate = useNavigate();
  const location = useLocation();

  const machineResult =
    location.state;

  const savedRef = useRef(false);

  const [saving, setSaving] =
    useState(true);

  const [saveError, setSaveError] =
    useState("");

  useEffect(() => {
    if (
      !machineResult?.sessionId ||
      !machineResult?.qrCode ||
      savedRef.current
    ) {
      return;
    }

    savedRef.current = true;

    const saveRedeemCode =
      async () => {
        try {
          setSaving(true);
          setSaveError("");

          const pointsEarned =
            Number(
              machineResult.pointsEarned ||
                0
            );

          if (
            !Number.isFinite(
              pointsEarned
            ) ||
            pointsEarned <= 0
          ) {
            throw new Error(
              "The machine returned an invalid point value."
            );
          }

          const expiresAt =
            Timestamp.fromMillis(
              Date.now() +
                5 * 60 * 1000
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
                machineResult.category ||
                "",

              pointsEarned,

              confidence: Number(
                machineResult.confidence ||
                  0
              ),

              status: "unclaimed",

              claimedBy: "",

              claimedAt: null,

              createdAt:
                serverTimestamp(),

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
            error?.code ===
            "permission-denied"
          ) {
            setSaveError(
              "Reward saving is blocked. Please ask for assistance."
            );
          } else {
            setSaveError(
              error?.message ||
                "The reward could not be saved. Please try again."
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

  const getMaterialLabel = (
    value
  ) => {
    const normalizedValue =
      String(value || "")
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
    <div className="machine-page machine-kiosk-page">
      <div className="machine-kiosk-shell">
        <header className="machine-kiosk-header">
          <div className="machine-kiosk-brand">
            <div className="machine-brand-icon">
              <Recycle size={30} />
            </div>

            <div>
              <h1>EcoRefill</h1>

              <p>
                Your recycling reward
              </p>
            </div>
          </div>

          <div className="machine-kiosk-status is-online">
            <CheckCircle2 size={18} />

            Accepted
          </div>
        </header>

        <main className="reward-kiosk">
          <section className="reward-celebration">
            <div className="reward-success-badge">
              <Sparkles size={28} />

              Great job!
            </div>

            <h2>
              You helped the planet 🌍
            </h2>

            <p>
              Your{" "}
              {getMaterialLabel(
                machineResult.materialType
              ).toLowerCase()}{" "}
              was successfully recycled.
            </p>

            <div className="reward-points">
              <span>YOU EARNED</span>

              <strong>
                +
                {Number(
                  machineResult.pointsEarned ||
                    0
                )}
              </strong>

              <p>EcoPoints</p>
            </div>
          </section>

          <section className="reward-scan-panel">
            {saveError ? (
              <div className="reward-error-state">
                <AlertTriangle
                  size={52}
                />

                <h3>
                  We couldn't prepare your
                  reward
                </h3>

                <p>{saveError}</p>

                <button
                  type="button"
                  className="machine-kiosk-primary"
                  onClick={retrySaving}
                >
                  Try Again
                </button>
              </div>
            ) : saving ? (
              <div className="reward-loading-state">
                <LoaderCircle
                  size={54}
                  className="machine-spin"
                />

                <h3>
                  Preparing your reward...
                </h3>

                <p>Just a moment.</p>
              </div>
            ) : (
              <>
                <div className="reward-scan-heading">
                  <div>
                    <span className="machine-kiosk-eyebrow">
                      Final step
                    </span>

                    <h3>
                      Scan to collect your
                      points
                    </h3>
                  </div>

                  <ScanLine size={38} />
                </div>

                <div className="reward-qr-frame">
                  <QRCodeCanvas
                    value={String(
                      machineResult.qrCode
                    ).trim()}
                    size={250}
                    bgColor="#ffffff"
                    fgColor="#10281d"
                    level="H"
                    includeMargin
                  />
                </div>

                <div className="reward-steps">
                  <span>1</span>
                  <p>
                    Open the EcoRefill app
                  </p>

                  <span>2</span>
                  <p>
                    Tap{" "}
                    <strong>
                      Scan QR
                    </strong>
                  </p>

                  <span>3</span>
                  <p>
                    Scan this code
                  </p>
                </div>

                <div className="reward-expiry">
                  <Timer size={20} />

                  QR expires in 5 minutes
                </div>
              </>
            )}
          </section>
        </main>

        <footer className="reward-footer">
          <div>
            <QrCode size={20} />

            One-time reward
          </div>

          <button
            type="button"
            className="machine-kiosk-finish"
            onClick={returnHome}
            disabled={
              saving ||
              Boolean(saveError)
            }
          >
            <Home size={22} />

            Done
          </button>
        </footer>
      </div>
    </div>
  );
}

export default RedeemQRCode;