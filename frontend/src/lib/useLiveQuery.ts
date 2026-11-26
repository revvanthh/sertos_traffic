import { useCallback, useEffect, useRef, useState } from "react";

export function useLiveQuery<T>(loader: () => Promise<T>, intervalMs = 10_000) {
  const loaderRef = useRef(loader);
  const [data, setData] = useState<T>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState<Date>();
  const [refreshCount, setRefreshCount] = useState(0);

  useEffect(() => {
    loaderRef.current = loader;
  }, [loader]);

  const refresh = useCallback(() => setRefreshCount((count) => count + 1), []);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    let requestInFlight = false;

    const poll = async () => {
      if (requestInFlight) return;
      requestInFlight = true;
      try {
        const result = await loaderRef.current();
        if (active) {
          setData(result);
          setError("");
          setLastUpdated(new Date());
        }
      } catch (reason: unknown) {
        if (active) setError(reason instanceof Error ? reason.message : "Unable to refresh live data.");
      } finally {
        requestInFlight = false;
        if (active) {
          setLoading(false);
          timer = window.setTimeout(poll, intervalMs);
        }
      }
    };

    setLoading(true);
    void poll();
    return () => {
      active = false;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [intervalMs, refreshCount]);

  return { data, loading, error, lastUpdated, refresh };
}
