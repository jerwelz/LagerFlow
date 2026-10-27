import { useCallback, useEffect, useState } from "react";

interface AsyncState<T> {
  data: T | undefined;
  error: unknown;
  loading: boolean;
  reload: () => void;
}

/** Loads data whenever `deps` change. Responses of outdated requests are ignored. */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [counter, setCounter] = useState(0);

  useEffect(() => {
    let current = true;
    setLoading(true);
    load()
      .then((result) => {
        if (current) {
          setData(result);
          setError(null);
        }
      })
      .catch((err: unknown) => current && setError(err))
      .finally(() => current && setLoading(false));
    return () => {
      current = false;
    };
    // `load` is recreated on every render; `deps` decides when to reload.
  }, [...deps, counter]);

  const reload = useCallback(() => setCounter((value) => value + 1), []);
  return { data, error, loading, reload };
}

/** Returns `value` after it has stopped changing for `delay` milliseconds. */
export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
