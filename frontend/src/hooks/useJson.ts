import { useEffect, useState } from "react";
import { DataError } from "../api/dataClient";

interface State<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
}

/** Generic JSON-loading hook. */
export function useJson<T>(loader: () => Promise<T>): State<T> {
  const [state, setState] = useState<State<T>>({ data: null, error: null, loading: true });
  useEffect(() => {
    let cancelled = false;
    setState({ data: null, error: null, loading: true });
    loader()
      .then((data) => {
        if (cancelled) return;
        setState({ data, error: null, loading: false });
      })
      .catch((err) => {
        if (cancelled) return;
        const error = err instanceof Error ? err : new DataError(String(err));
        setState({ data: null, error, loading: false });
      });
    return () => {
      cancelled = true;
    };
  }, [loader]);
  return state;
}