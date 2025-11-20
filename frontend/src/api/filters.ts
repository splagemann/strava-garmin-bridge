import { apiClient } from './client';
import type { ActivityFilter, FilterCreate, FilterUpdate } from '../types';

export const filtersApi = {
  /**
   * Get all filters for the user
   */
  getFilters: async (): Promise<ActivityFilter[]> => {
    const response = await apiClient.get('/api/v1/filters/');
    return response.data;
  },

  /**
   * Get a specific filter by ID
   */
  getFilter: async (filterId: number): Promise<ActivityFilter> => {
    const response = await apiClient.get(`/api/v1/filters/${filterId}`);
    return response.data;
  },

  /**
   * Create a new filter
   */
  createFilter: async (data: FilterCreate): Promise<ActivityFilter> => {
    const response = await apiClient.post('/api/v1/filters/', data);
    return response.data;
  },

  /**
   * Update an existing filter
   */
  updateFilter: async (filterId: number, data: FilterUpdate): Promise<ActivityFilter> => {
    const response = await apiClient.put(`/api/v1/filters/${filterId}`, data);
    return response.data;
  },

  /**
   * Delete a filter
   */
  deleteFilter: async (filterId: number): Promise<void> => {
    await apiClient.delete(`/api/v1/filters/${filterId}`);
  },
};
