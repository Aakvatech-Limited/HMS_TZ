/**
 * Run `fetcher` for a store and pass its rows to `apply`, unless a newer call
 * started meanwhile. The store owns `latestRequest`, `isFetching` and `loadError`.
 * A failed load applies an empty list so the grid never shows another day's data.
 */
export const fetchLatest = async (store, fetcher, apply) => {
  const request = ++store.latestRequest;
  const isLatest = () => request === store.latestRequest;
  store.isFetching = true;
  store.loadError = null;
  try {
    const rows = await fetcher();
    if (isLatest()) apply(rows);
  } catch (error) {
    if (!isLatest()) return;
    apply([]);
    store.loadError = error.message || "Failed to load data";
  } finally {
    if (isLatest()) store.isFetching = false;
  }
};
