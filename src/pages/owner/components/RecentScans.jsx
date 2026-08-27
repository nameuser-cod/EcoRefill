import { Camera, ImageOff } from "lucide-react";
import { OwnerEmpty } from "./OwnerFeedback";
import {
  formatTimestamp,
  getDetectedMaterial,
} from "../utils/ownerDashboard";

function RecentScans({ items }) {
  return (
    <section className="owner-panel">
      <div className="owner-panel-heading">
        <div>
          <p>Visual log</p>
          <h2>Recent scans</h2>
        </div>
      </div>

      {items.length === 0 ? (
        <OwnerEmpty
          icon={Camera}
          title="No scanned items yet"
          description="New machine scans will appear here automatically."
        />
      ) : (
        <div className="owner-scan-grid">
          {items.map((item) => (
            <article className="owner-scan-card" key={item.id}>
              <div className="owner-scan-photo">
                {item.imageDataUrl || item.imageUrl ? (
                  <img
                    src={item.imageDataUrl || item.imageUrl}
                    alt={getDetectedMaterial(item)}
                    loading="lazy"
                  />
                ) : (
                  <span>
                    <ImageOff size={23} />
                  </span>
                )}
                <span
                  className={`owner-scan-status ${
                    item.accepted ? "accepted" : "rejected"
                  }`}
                >
                  {item.accepted ? "Accepted" : "Rejected"}
                </span>
              </div>
              <div className="owner-scan-info">
                <strong>{getDetectedMaterial(item)}</strong>
                <span>
                  {Math.round(Number(item.confidence || 0) * 100)}% ·{" "}
                  {formatTimestamp(item.createdAt)}
                </span>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export default RecentScans;
