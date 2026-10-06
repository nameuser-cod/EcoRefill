import { useMemo, useState } from "react";
import { Camera, ChevronLeft, ChevronRight, ImageOff } from "lucide-react";
import { OwnerEmpty } from "./OwnerFeedback";
import PhotoActivityRow from "./PhotoActivityRow";
import RecyclingPhotoDialog from "./RecyclingPhotoDialog";
import {
  formatTimestamp,
  getDetectedMaterial,
  normalizeText,
} from "../utils/ownerDashboard";

const PAGE_SIZE = 6;
const STATUS_FILTERS = [
  { value: "all", label: "All results" },
  { value: "accepted", label: "Accepted" },
  { value: "rejected", label: "Rejected" },
];
const MATERIAL_FILTERS = [
  { value: "all", label: "All materials" },
  { value: "can", label: "Cans" },
  { value: "bottle", label: "Plastic bottles" },
];
const CAN_MATERIALS = new Set([
  "can", "cans", "aluminum can", "aluminium can", "metal can", "tin can",
  "aluminum", "aluminium",
]);
const BOTTLE_MATERIALS = new Set([
  "plastic bottle", "pet bottle", "plastic", "pet",
]);

function RecentScans({ items, canLoadMore = false, onLoadMore, loading = false }) {
  const [statusFilter, setStatusFilter] = useState("all");
  const [materialFilter, setMaterialFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [selectedScan, setSelectedScan] = useState(null);
  const filteredItems = useMemo(() => items.filter((item) => {
    const accepted = item.accepted === true;
    if (statusFilter === "accepted" && !accepted) return false;
    if (statusFilter === "rejected" && accepted) return false;
    if (materialFilter === "all") return true;

    // Rejected scans use category "reject", so match their detected material.
    const material = normalizeText(getDetectedMaterial(item));
    return materialFilter === "can"
      ? CAN_MATERIALS.has(material)
      : BOTTLE_MATERIALS.has(material);
  }), [items, statusFilter, materialFilter]);
  const totalPages = Math.max(1, Math.ceil(filteredItems.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const startIndex = (currentPage - 1) * PAGE_SIZE;
  const visibleItems = filteredItems.slice(startIndex, startIndex + PAGE_SIZE);

  return (
    <section className="owner-panel">
      <div className="owner-panel-heading">
        <div>
          <p>Visual log</p>
          <h2>Scan history</h2>
        </div>
      </div>

      <div className="owner-scan-filters">
        <fieldset>
          <legend>Result</legend>
          <div className="owner-filter-row">
            {STATUS_FILTERS.map((filter) => (
              <button
                key={filter.value}
                type="button"
                className={`filter-scans-button ${statusFilter === filter.value ? "active" : ""}`}
                aria-pressed={statusFilter === filter.value}
                onClick={() => {
                  setStatusFilter(filter.value);
                  setPage(1);
                }}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </fieldset>
        <fieldset>
          <legend>Material</legend>
          <div className="owner-filter-row">
            {MATERIAL_FILTERS.map((filter) => (
              <button
                key={filter.value}
                type="button"
                className={`filter-material-button ${materialFilter === filter.value ? "active" : ""}`}
                aria-pressed={materialFilter === filter.value}
                onClick={() => {
                  setMaterialFilter(filter.value);
                  setPage(1);
                }}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </fieldset>
      </div>

      <p className="owner-scan-summary" role="status">
        {filteredItems.length > 0
          ? `Showing ${startIndex + 1}–${startIndex + visibleItems.length} of ${filteredItems.length}${canLoadMore ? " loaded" : ""} scans · Newest first`
          : canLoadMore ? "0 matching loaded scans" : "0 scans"}
      </p>
      {canLoadMore && <p className="owner-scan-summary">Filters apply to loaded scans. Load older scans to search further.</p>}

      {items.length === 0 ? (
        <OwnerEmpty
          icon={Camera}
          title="No scanned items yet"
          description="New machine scans will appear here automatically."
        />
      ) : filteredItems.length === 0 ? (
        <OwnerEmpty
          icon={Camera}
          title="No matching scans"
          description="Try another result or material filter."
        />
      ) : (
        <div className="owner-scan-grid">
          {visibleItems.map((item) => {
            const material = String(getDetectedMaterial(item)).replaceAll("_", " ");
            return (
              <PhotoActivityRow className="owner-scan-card" key={item.id}
                onOpen={() => setSelectedScan({ ...item, source: "recycling_records" })}>
                <div className="owner-scan-photo">
                  {item.imageDataUrl || item.imageUrl ? (
                    <img
                      src={item.imageDataUrl || item.imageUrl}
                      alt={`Machine scan of ${material}`}
                      loading="lazy"
                    />
                  ) : (
                    <span className="owner-scan-missing">
                      <ImageOff size={23} />
                    </span>
                  )}
                  <span className="owner-scan-photo-hint">View photo</span>
                </div>
                <div className="owner-scan-info">
                  <div className="owner-scan-caption-heading">
                    <strong>{material}</strong>
                    <span className={`owner-scan-status ${item.accepted === true ? "accepted" : "rejected"}`}>
                      {item.accepted === true ? "Accepted" : "Rejected"}
                    </span>
                  </div>
                  <div className="owner-scan-meta">
                    <span>{Math.round(Number(item.confidence || 0) * 100)}% confidence</span>
                    <time>{formatTimestamp(item.createdAt)}</time>
                  </div>
                </div>
              </PhotoActivityRow>
            );
          })}
        </div>
      )}
      {canLoadMore && (
        <button type="button" className="view-transactions-button" onClick={onLoadMore} disabled={loading}>
          {loading ? "Loading older scans..." : "Load older scans"}
        </button>
      )}

      {filteredItems.length > 0 && (
        <nav className="owner-scan-pagination" aria-label="Scan history pages">
          <button
            className="previous-page-button"
            type="button"
            disabled={currentPage === 1}
            onClick={() => setPage(currentPage - 1)}
            aria-label="Previous page of scans"
          >
            <ChevronLeft size={16} aria-hidden="true" /> Previous
          </button>
          <span>Page {currentPage} of {totalPages}</span>
          <button
            className="next-page-button"
            type="button"
            disabled={currentPage === totalPages}
            onClick={() => setPage(currentPage + 1)}
            aria-label="Next page of scans"
          >
            Next <ChevronRight size={16} aria-hidden="true" />
          </button>
        </nav>
      )}
      {selectedScan && (
        <RecyclingPhotoDialog transaction={selectedScan}
          onClose={() => setSelectedScan(null)} />
      )}
    </section>
  );
}

export default RecentScans;
