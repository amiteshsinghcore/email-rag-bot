/**
 * useTaskProgress Hook
 *
 * React hook for tracking task progress via WebSocket.
 */

import { useState, useEffect, useCallback } from 'react';
import { wsClient, WebSocketMessage } from '@/services/websocket';

export interface TaskProgress {
  taskId: string;
  status: string;
  progress: number;
  message: string;
  details?: Record<string, unknown>;
  isComplete: boolean;
  isFailed: boolean;
}

export function useTaskProgress(taskId: string | null): TaskProgress | null {
  const [progress, setProgress] = useState<TaskProgress | null>(null);

  const handleMessage = useCallback(
    (message: WebSocketMessage) => {
      const data = message.data as {
        task_id?: string;
        status?: string;
        progress?: number;
        message?: string;
      };

      if (data.task_id !== taskId) return;

      setProgress({
        taskId: data.task_id,
        status: data.status || 'unknown',
        progress: data.progress || 0,
        message: data.message || '',
        details: message.data,
        isComplete: message.type === 'task_completed',
        isFailed: message.type === 'task_failed' || message.type === 'task_cancelled',
      });
    },
    [taskId]
  );

  useEffect(() => {
    if (!taskId) {
      setProgress(null);
      return;
    }

    // Subscribe to task channel
    const unsubscribeChannel = wsClient.subscribeToTask(taskId);

    // Listen for task updates
    const unsubscribeStarted = wsClient.on('task_started', handleMessage);
    const unsubscribeProgress = wsClient.on('task_progress', handleMessage);
    const unsubscribeCompleted = wsClient.on('task_completed', handleMessage);
    const unsubscribeFailed = wsClient.on('task_failed', handleMessage);
    const unsubscribeCancelled = wsClient.on('task_cancelled', handleMessage);

    return () => {
      unsubscribeChannel();
      unsubscribeStarted();
      unsubscribeProgress();
      unsubscribeCompleted();
      unsubscribeFailed();
      unsubscribeCancelled();
    };
  }, [taskId, handleMessage]);

  return progress;
}
