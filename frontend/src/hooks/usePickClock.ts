import { useEffect, useRef, useState } from 'react';

/**
 * Countdown timer for human pick turns. Visual only — not enforced server-side.
 * Resets to `seconds` whenever `active` transitions false → true.
 */
export function usePickClock(totalSeconds: number, active: boolean): number {
  const [remaining, setRemaining] = useState(totalSeconds);
  const prevActive = useRef(false);

  useEffect(() => {
    // Reset when newly activated
    if (active && !prevActive.current) {
      setRemaining(totalSeconds);
    }
    prevActive.current = active;

    if (!active) return;

    const interval = setInterval(() => {
      setRemaining((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => clearInterval(interval);
  }, [active, totalSeconds]);

  return remaining;
}
