
export interface SpecialCollection {
  start_date: string;
  end_date: string;
  collection_names: string[];
}

export interface CategoryConfig {
  category_name: string;
  pin_count: number;
  collections: string[];
}

export interface AppConfig {
  plex_url: string;
  plex_token: string;
  collexions_label: string;
  dry_run: boolean;
  pinning_interval: number;
  repeat_block_hours: number;
  min_items_for_pinning: number;
  discord_webhook_url: string;
  use_random_category_mode: boolean;
  random_category_skip_percent: number;
  exclusion_list: string[];
  regex_exclusion_patterns: string[];
  special_collections: SpecialCollection[];
  library_names: string[];
  number_of_collections_to_pin: Record<string, number>;
  categories: Record<string, CategoryConfig[]>;
  tmdb_api_key?: string;
  trakt_client_id?: string;
  mdblist_api_key?: string;
  enable_trending_pinning?: boolean;
}

export interface AppStatus {
  status: string;
  last_update: string;
  next_run_timestamp?: number;
}

export interface PlexCollection {
  title: string;
  library: string;
  is_pinned: boolean;
  has_label: boolean;
  thumb: string;
  ratingKey: string;
}

export interface PinEvent {
  timestamp: string; // ISO Date String
  collectionName: string;
  library: string;
}

export interface HistoryResponse {
  events: PinEvent[];
  total_count: number;
  unique_count: number;
}

export enum Tab {
  DASHBOARD = 'dashboard',
  GALLERY = 'gallery',
  STATS = 'stats',
  CREATOR = 'creator',
  JOBS = 'jobs',
  SETTINGS = 'settings',
  LOGS = 'logs'
}