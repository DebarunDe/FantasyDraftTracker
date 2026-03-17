import { useEffect, useRef, useState } from 'react';

/**
 * Countdown timer for human pick turns. Visual only — not enforced server-side.
 * Resets to `totalSeconds` whenever `active` transitions false → true.
 * Calls `onExpire` once when the timer reaches 0.
 */
export function usePickClock(
  totalSeconds: number,
  active: boolean,
  onExpire?: () => void,
): number {
  const [remaining, setRemaining] = useState(totalSeconds);
  const prevActive = useRef(false);
  const expiredRef = useRef(false);

  useEffect(() => {
    if (active && !prevActive.current) {
      setRemaining(totalSeconds);
      expiredRef.current = false;
    }
    prevActive.current = active;

    if (!active) return;

    const interval = setInterval(() => {
      setRemaining((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => clearInterval(interval);
  }, [active, totalSeconds]);

  useEffect(() => {
    if (remaining === 0 && active && !expiredRef.current) {
      expiredRef.current = true;
      onExpire?.();
    }
  }, [remaining, active, onExpire]);

  return remaining;
}
