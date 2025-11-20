export interface ActivityFilter {
  id: number;
  filter_type: 'include' | 'exclude';
  pattern: string;
  is_regex: boolean;
  active: boolean;
}

export interface FilterCreate {
  filter_type: 'include' | 'exclude';
  pattern: string;
  is_regex: boolean;
  active: boolean;
}

export interface FilterUpdate {
  filter_type?: 'include' | 'exclude';
  pattern?: string;
  is_regex?: boolean;
  active?: boolean;
}
