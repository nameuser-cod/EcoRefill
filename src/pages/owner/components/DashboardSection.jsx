import { LoaderCircle } from "lucide-react";
import { OwnerError } from "./OwnerFeedback";

function DashboardSection({ title, sources, hasContent, onRetry, children }) {
  const pending = sources.some((source) => source.loading);
  const slow = sources.some((source) => source.slow);
  const errors = sources.map((source) => source.error).filter(Boolean);
  const showContent = hasContent || (!pending && errors.length === 0);

  return (
    <div className="owner-dashboard-section">
      {(pending || errors.length > 0) && (
        <section className="owner-panel owner-section-feedback" aria-label={`${title} status`}>
          <h2>{title}</h2>
          {errors.map((error) => <OwnerError key={error} message={error} />)}
          {pending && (
            <p className="owner-section-loading" role="status">
              <LoaderCircle className="owner-app-spin" size={20} aria-hidden="true" />
              {slow
                ? "This is taking longer than usual. We’re still trying to connect."
                : hasContent ? "Loading more activity…" : `Loading ${title.toLowerCase()}…`}
            </p>
          )}
          {(slow || errors.length > 0) && (
            <button type="button" onClick={onRetry}>Try again</button>
          )}
        </section>
      )}
      {showContent && children}
    </div>
  );
}

export default DashboardSection;
