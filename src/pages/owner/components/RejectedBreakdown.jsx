import { PackageX, ShieldCheck } from "lucide-react";
import { OwnerEmpty } from "./OwnerFeedback";

function RejectedBreakdown({ rejectedTypes }) {
  const entries = Object.entries(rejectedTypes).sort(
    (first, second) => second[1] - first[1]
  );

  return (
    <section className="owner-panel">
      <div className="owner-panel-heading">
        <div>
          <p>Detection quality</p>
          <h2>Rejected items</h2>
        </div>
      </div>

      {entries.length === 0 ? (
        <OwnerEmpty
          icon={ShieldCheck}
          title="No rejected items"
          description="Rejected object types will be grouped here."
        />
      ) : (
        <div className="owner-breakdown-list">
          {entries.slice(0, 6).map(([name, count]) => (
            <div key={name}>
              <span>
                <PackageX size={18} />
                <strong>{name}</strong>
              </span>
              <b>{count}</b>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export default RejectedBreakdown;
