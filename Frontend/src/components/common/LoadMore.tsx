import { useEffect, useRef } from "react";
import { Button } from "./Button";

/** Infinite scroll sentinel with a manual "Load more" fallback (keyboard and screen readers). */
export function LoadMore({ hasMore, loading, onLoad, label = "Load more" }: {
  hasMore: boolean; loading: boolean; onLoad: () => void; label?: string;
}) {
  const sentinel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!hasMore || !sentinel.current || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver((entries) => {
      if (entries[0]?.isIntersecting && !loading) onLoad();
    }, { rootMargin: "400px" });
    observer.observe(sentinel.current);
    return () => observer.disconnect();
  }, [hasMore, loading, onLoad]);
  if (!hasMore) return null;
  return (
    <div ref={sentinel} className="flex justify-center py-4">
      <Button variant="outline" size="sm" loading={loading} onClick={onLoad}>{label}</Button>
    </div>
  );
}
