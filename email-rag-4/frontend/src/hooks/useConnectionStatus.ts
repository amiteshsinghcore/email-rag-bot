/**
 * useConnectionStatus Hook
 *
 * React hook for tracking WebSocket connection status.
 */

import { useState, useEffect } from 'react';
import { ConnectionState, onConnectionChange } from '@/services/websocket';

export function useConnectionStatus(): ConnectionState {
  const [state, setState] = useState<ConnectionState>('disconnected');

  useEffect(() => {
    const unsubscribe = onConnectionChange(setState);
    return unsubscribe;
  }, []);

  return state;
}
