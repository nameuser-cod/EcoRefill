import { useEffect, useId, useMemo, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { calculateMonthlyRecycling, getMonthlyMetric, getRecyclingMonth } from "../utils/monthlyRecycling";
import { OwnerError, OwnerLoading } from "./OwnerFeedback";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const MATERIALS = [
  { key: "bottle", label: "Bottles" },
  { key: "can", label: "Cans" },
  { key: "other", label: "Other / unknown" },
];
const formatCount = (count) => count.toLocaleString("en-US");

function RecyclingBreakdownDialog({ metric, records, total, onClose, loading = false, error = "", onRetry }) {
  const dialogRef = useRef(null);
  const titleId = useId();
  const yearId = useId();
  const detailsId = useId();
  const breakdown = useMemo(() => calculateMonthlyRecycling(records), [records]);
  const years = Object.keys(breakdown.years).map(Number).sort((a, b) => b - a);
  if (!years.length) years.push(getRecyclingMonth(new Date()).year);
  const [selectedYear, setSelectedYear] = useState(null);
  const [selectedMonth, setSelectedMonth] = useState(0);
  const year = years.includes(selectedYear) ? selectedYear : years[0];
  const months = (breakdown.years[year] || []).map((month) => getMonthlyMetric(month, metric.key));
  const yearTotal = months.reduce((sum, month) => sum + month.total, 0);
  const maximum = Math.max(1, ...months.map((month) => month.total));
  const undated = getMonthlyMetric(breakdown.undated, metric.key).total;
  const showMaterials = metric.key === "acceptedCount" || metric.key === "rejectedCount";
  const materials = showMaterials ? MATERIALS : MATERIALS.filter(({ key }) => `${key}Count` === metric.key);
  const selectedCounts = months[selectedMonth] || { bottle: 0, can: 0, other: 0, total: 0 };
  const half = selectedMonth < 6 ? 0 : 1;

  useEffect(() => {
    const dialog = dialogRef.current;
    const previousFocus = document.activeElement;
    const scrollX = window.scrollX;
    const scrollY = window.scrollY;
    const bodyStyles = ["overflow", "position", "top", "left", "width"];
    const previousStyles = bodyStyles.map((property) => [property, document.body.style[property]]);
    const previousRootOverflow = document.documentElement.style.overflow;
    dialog.showModal();
    document.documentElement.style.overflow = "hidden";
    document.body.style.overflow = "hidden";
    document.body.style.position = "fixed";
    document.body.style.top = `-${scrollY}px`;
    document.body.style.left = `-${scrollX}px`;
    document.body.style.width = "100%";
    return () => {
      dialog.close();
      previousStyles.forEach(([property, value]) => { document.body.style[property] = value; });
      document.documentElement.style.overflow = previousRootOverflow;
      window.scrollTo({ left: scrollX, top: scrollY, behavior: "instant" });
      previousFocus?.focus({ preventScroll: true });
    };
  }, []);

  return (
    <dialog ref={dialogRef} className="owner-breakdown-dialog" aria-labelledby={titleId}
      onCancel={onClose} onClick={(event) => {
        if (event.target !== event.currentTarget) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) onClose();
      }}>
      <header className="owner-breakdown-heading">
        <div>
          <p>Monthly breakdown</p>
          <h2 id={titleId}>{metric.label}</h2>
          <p>{metric.key === "rejectedCount" ? "Items rejected by the machine" : "Items accepted for collection"} · Philippine time</p>
        </div>
        <button type="button" className="owner-breakdown-close" aria-label="Close monthly breakdown" onClick={onClose} autoFocus>
          <X size={24} aria-hidden="true" />
        </button>
      </header>
      <div className="owner-breakdown-body">
        {loading || error ? <>
          {loading && <OwnerLoading label="Loading complete monthly history..." />}
          <OwnerError message={error} />
          <button className="retry-dashboard-button" type="button" onClick={onRetry}>Try again</button>
        </> : <>
        <div className="owner-breakdown-toolbar">
          <label htmlFor={yearId}>Year
            <select id={yearId} value={year} onChange={(event) => {
              setSelectedYear(Number(event.target.value));
              setSelectedMonth(0);
            }}>
              {years.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <div><span>All-time total</span><strong>{formatCount(total)}</strong></div>
          <div><span>Total in {year}</span><strong>{formatCount(yearTotal)}</strong></div>
        </div>
        {undated > 0 && <p className="owner-breakdown-notice">{formatCount(undated)} {undated === 1 ? "item has" : "items have"} no valid date. Included in the all-time total, but excluded from monthly bars.</p>}
        {yearTotal === 0 && <p className="owner-breakdown-notice">No dated {metric.label.toLowerCase()} records for {year}.</p>}
        <div className="owner-breakdown-legend" aria-label="Bar colors">
          {materials.map(({ key, label }) => <span key={key}><i className={`owner-breakdown-color-${key}`} aria-hidden="true" />{label}</span>)}
        </div>
        <div className="owner-breakdown-axis"><span>Number of items</span><span>Tap a month for details</span></div>
        <ol className="owner-monthly-chart" data-half={half} aria-label={`${metric.label} by month in ${year}`}>
          {MONTHS.map((month, index) => {
            const counts = months[index] || { bottle: 0, can: 0, other: 0, total: 0 };
            return (
              <li key={month} data-half={index < 6 ? 0 : 1}>
                <button type="button" className="owner-monthly-button" aria-pressed={selectedMonth === index}
                  aria-controls={detailsId} aria-label={`${month} ${year}: ${formatCount(counts.total)} items`}
                  onClick={() => setSelectedMonth(index)}>
                  <strong className="owner-monthly-count">{formatCount(counts.total)}</strong>
                  <span className="owner-monthly-track" aria-hidden="true">
                    {materials.map(({ key }) => <span key={key} className={`owner-breakdown-color-${key}`} style={{ height: `${counts[key] / maximum * 100}%` }} />)}
                  </span>
                  <span className="owner-monthly-label">{month.slice(0, 3)}</span>
                </button>
              </li>
            );
          })}
        </ol>
        <nav className="owner-breakdown-paging" aria-label="Chart months">
          <button type="button" disabled={half === 0} onClick={() => setSelectedMonth(selectedMonth - 6)}>
            <ChevronLeft size={16} aria-hidden="true" />Previous
          </button>
          <span aria-live="polite">{half === 0 ? "Jan – Jun" : "Jul – Dec"}</span>
          <button type="button" disabled={half === 1} onClick={() => setSelectedMonth(selectedMonth + 6)}>
            Next<ChevronRight size={16} aria-hidden="true" />
          </button>
        </nav>
        <section id={detailsId} className="owner-monthly-details" aria-label="Selected month details" aria-live="polite" aria-atomic="true">
          <div className="owner-monthly-details-heading">
            <div><p>Selected month</p><h3>{MONTHS[selectedMonth]} {year}</h3></div>
            <div><span>Total items</span><strong>{formatCount(selectedCounts.total)}</strong></div>
          </div>
          {showMaterials && <dl>
            {materials.map(({ key, label }) => <div key={key}>
              <dt><i className={`owner-breakdown-color-${key}`} aria-hidden="true" />{label}</dt>
              <dd>{formatCount(selectedCounts[key])}</dd>
            </div>)}
          </dl>}
          {selectedCounts.total === 0 && <p className="owner-monthly-empty">No {metric.label.toLowerCase()} recorded this month.</p>}
        </section>
        </>}
      </div>
    </dialog>
  );
}

export default RecyclingBreakdownDialog;
