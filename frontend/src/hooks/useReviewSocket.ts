import { useEffect, useState } from 'react';

export function useReviewSocket(onNewReview?: () => void) {
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    // Polling fallback to keep review queue fresh every 3 seconds
    const interval = setInterval(() => {
      if (onNewReview) {
        onNewReview();
      }
    }, 3000);

    setIsConnected(true);

    return () => {
      clearInterval(interval);
      setIsConnected(false);
    };
  }, [onNewReview]);

  return { isConnected };
}
