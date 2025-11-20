export const SYNC_STATUS_COLORS = {
  success: 'text-green-600 bg-green-50 border-green-200',
  failed: 'text-red-600 bg-red-50 border-red-200',
  skipped: 'text-yellow-600 bg-yellow-50 border-yellow-200',
  pending: 'text-blue-600 bg-blue-50 border-blue-200',
} as const;

export const SYNC_STATUS_LABELS = {
  success: 'Success',
  failed: 'Failed',
  skipped: 'Skipped',
  pending: 'Pending',
} as const;

export const FILTER_TYPE_COLORS = {
  include: 'text-green-600 bg-green-50 border-green-200',
  exclude: 'text-red-600 bg-red-50 border-red-200',
} as const;

export const FILTER_TYPE_LABELS = {
  include: 'Include',
  exclude: 'Exclude',
} as const;

export const QUERY_KEYS = {
  authStatus: ['authStatus'] as const,
  filters: ['filters'] as const,
  filter: (id: number) => ['filter', id] as const,
  syncHistory: (params?: Record<string, unknown>) => ['syncHistory', params] as const,
  syncLog: (id: number) => ['syncLog', id] as const,
  syncStats: ['syncStats'] as const,
} as const;
