/** Poll callback on an interval; slows down while the tab is hidden. */
export function startVisibilityAwarePoll(
  fn: () => void | Promise<void>,
  activeMs: number,
  hiddenMs = activeMs * 4,
): () => void {
  let timer: number | undefined;

  const schedule = () => {
    const ms = document.hidden ? hiddenMs : activeMs;
    timer = window.setTimeout(() => {
      void Promise.resolve(fn()).finally(schedule);
    }, ms);
  };

  const onVisibility = () => {
    if (timer !== undefined) window.clearTimeout(timer);
    schedule();
  };

  document.addEventListener("visibilitychange", onVisibility);
  schedule();

  return () => {
    document.removeEventListener("visibilitychange", onVisibility);
    if (timer !== undefined) window.clearTimeout(timer);
  };
}
