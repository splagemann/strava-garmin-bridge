import { apiClient } from './client';
import type {
  GarminWorkout,
  WorkoutSchedule,
  CreateScheduleRequest,
  SyncSchedulesRequest,
  SyncSchedulesResponse,
  SyncMonthRequest,
  SyncMonthResponse,
} from '../types';

export const workoutsApi = {
  /** Fetch the user's Garmin workout library. */
  listLibrary: async (): Promise<GarminWorkout[]> => {
    const response = await apiClient.get('/api/v1/workouts/library');
    return response.data;
  },

  /** List all saved recurring schedules. */
  listSchedules: async (): Promise<WorkoutSchedule[]> => {
    const response = await apiClient.get('/api/v1/workouts/schedules');
    return response.data;
  },

  /** Create a new recurring schedule. */
  createSchedule: async (data: CreateScheduleRequest): Promise<WorkoutSchedule> => {
    const response = await apiClient.post('/api/v1/workouts/schedules', data);
    return response.data;
  },

  /** Enable or disable a schedule. */
  toggleSchedule: async (id: number, is_active: boolean): Promise<WorkoutSchedule> => {
    const response = await apiClient.patch(`/api/v1/workouts/schedules/${id}`, { is_active });
    return response.data;
  },

  /** Delete a schedule. */
  deleteSchedule: async (id: number): Promise<{ message: string }> => {
    const response = await apiClient.delete(`/api/v1/workouts/schedules/${id}`);
    return response.data;
  },

  /** Manually push today's (or a specific date's) scheduled workouts to Garmin. */
  syncSchedules: async (data?: SyncSchedulesRequest): Promise<SyncSchedulesResponse> => {
    const response = await apiClient.post('/api/v1/workouts/schedules/sync', data ?? {});
    return response.data;
  },

  /** Push all active schedules for every remaining day of the given month to Garmin. */
  syncMonth: async (data?: SyncMonthRequest): Promise<SyncMonthResponse> => {
    const response = await apiClient.post('/api/v1/workouts/schedules/sync-month', data ?? {});
    return response.data;
  },
};
