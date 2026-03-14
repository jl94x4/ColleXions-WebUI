import { AppConfig, AppStatus, PinEvent, HistoryResponse, PlexCollection } from "../types";
import { DEFAULT_CONFIG, USER_PROVIDED_CONFIG } from "../constants";

class ApiService {
  // Use the user's config as the mock/fallback if API is offline
  private mockConfig: AppConfig = USER_PROVIDED_CONFIG;
  private mockHistory: PinEvent[] = [];

  private getHeaders() {
    const token = localStorage.getItem('collexions_token');
    return {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    };
  }

  private async get(url: string) {
    const response = await fetch(`/api${url.startsWith('/') ? url : '/' + url}${url.includes('?') ? '&' : '?'}__=${Date.now()}`, {
      headers: this.getHeaders()
    });

    if (response.status === 401) {
      localStorage.removeItem('collexions_token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const error = new Error(errorData.error || `Fetch error: ${response.statusText}`);
      (error as any).status = response.status;
      (error as any).data = errorData;
      throw error;
    }
    return response.json();
  }

  private async post(url: string, body: any) {
    const response = await fetch(`/api${url.startsWith('/') ? url : '/' + url}`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(body)
    });

    if (response.status === 401) {
      localStorage.removeItem('collexions_token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const error = new Error(errorData.error || `Post error: ${response.statusText}`);
      (error as any).status = response.status;
      (error as any).data = errorData;
      throw error;
    }
    return response.json();
  }

  // -- AUTH --
  async getAuthStatus(): Promise<{ is_setup: boolean, needs_onboarding?: boolean }> {
    const response = await fetch(`/api/auth/status?_=${Date.now()}`);
    return response.json();
  }

  async setupAuth(password: string): Promise<any> {
    return this.post('/auth/setup', { password });
  }

  async login(password: string): Promise<any> {
    return this.post('/auth/login', { password });
  }

  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    await this.post('/auth/change-password', { currentPassword, newPassword });
  }

  async verifyToken(token: string): Promise<boolean> {
    try {
      const response = await fetch(`/api/auth/verify?_=${Date.now()}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  // -- CONFIG --
  async getConfig(): Promise<AppConfig> {
    try {
      const data = await this.get('/config');
      return { ...DEFAULT_CONFIG, ...data };
    } catch (e) {
      console.warn("API unreachable, using fallback config.");
      return this.mockConfig;
    }
  }

  async saveConfig(config: AppConfig): Promise<void> {
    try {
      await this.post('/config', config);
    } catch (e) {
      console.error("Failed to save config to backend");
      this.mockConfig = config;
      throw e;
    }
  }

  // -- STATUS --
  async getStatus(): Promise<AppStatus> {
    try {
      return await this.get('/status');
    } catch (e) {
      return {
        status: "Offline",
        last_update: "",
        next_run_timestamp: 0
      };
    }
  }

  // -- LOGS --
  async getLogs(): Promise<string> {
    try {
      const response = await fetch(`/api/logs?_=${Date.now()}`, {
        headers: this.getHeaders()
      });
      if (!response.ok) throw new Error('API unreachable');
      return await response.text();
    } catch (e) {
      return "Backend is offline. Logs unavailable.";
    }
  }

  async clearLogs(): Promise<void> {
    await this.post('/logs/clear', {});
  }

  // -- HISTORY (Server-Side Stats) --
  async getHistory(limit?: number): Promise<HistoryResponse> {
    try {
      const params = new URLSearchParams();
      if (limit) params.append('limit', limit.toString());
      const data = await this.get(`/history?${params.toString()}`);

      if (Array.isArray(data)) {
        return {
          events: data,
          total_count: data.length,
          unique_count: new Set(data.map((e: any) => e.collectionName)).size
        };
      }
      return data;
    } catch (e) {
      console.warn("Could not fetch server history, using local/empty session.", e);
      return {
        events: this.mockHistory,
        total_count: this.mockHistory.length,
        unique_count: new Set(this.mockHistory.map(e => e.collectionName)).size
      };
    }
  }

  async saveHistory(events: PinEvent[]): Promise<void> {
    try {
      await this.post('/history', events);
    } catch (e) {
      console.error("Failed to save history to backend", e);
      this.mockHistory = events;
    }
  }

  // -- ACTIONS --
  async runNow(): Promise<void> {
    await this.post('/run', {});
  }

  async stopScript(): Promise<void> {
    await this.post('/stop', {});
  }

  // -- GALLERY --
  async getCollections(forceRefresh = false): Promise<PlexCollection[]> {
    if (forceRefresh) {
      // Wipe server-side gallery + image caches before re-fetching
      try { await this.post('/cache/clear', {}); } catch { /* ignore */ }
    }
    const params = new URLSearchParams();
    if (forceRefresh) params.append('refresh', 'true');
    const data = await this.get(`/collections?${params.toString()}`);

    if (data && typeof data === 'object' && !Array.isArray(data)) {
      return data.collections || [];
    }
    return data || [];
  }

  // -- TRENDING --
  async getTrending(): Promise<any[]> {
    try {
      return this.get('/trending');
    } catch (e) {
      console.error("Failed to fetch trending data:", e);
      return [];
    }
  }

  async searchLibrary(library: string, query: string, genre?: string, year?: string): Promise<any[]> {
    const params = new URLSearchParams({ library, query });
    if (genre) params.append('genre', genre);
    if (year) params.append('year', year);
    return this.get(`/search/local?${params.toString()}`);
  }

  async searchExternal(query: string, type: 'movie' | 'tv'): Promise<any[]> {
    return this.get(`/search/external?query=${encodeURIComponent(query)}&type=${type}`);
  }

  async getTmdbGenres(type: 'movie' | 'tv'): Promise<any[]> {
    return this.get(`/tmdb/genres?type=${type}`);
  }

  async discoverTmdb(params: Record<string, any>): Promise<any[]> {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, String(value));
      }
    });
    return this.get(`/search/discover?${searchParams.toString()}`);
  }

  async createCollection(library: string, title: string, items: string[], sort_order: string = 'custom'): Promise<any> {
    return this.post('/collections/create', { library, title, items, sort_order });
  }

  async createFromExternal(library: string, title: string, items: any[], sort_order: string = 'custom', auto_sync: boolean = false, source_type?: string, source_id?: string): Promise<any> {
    return this.post('/collections/create-from-external', { library, title, items, sort_order, auto_sync, source_type, source_id });
  }

  // -- JOBS / AUTO-SYNC --
  async getJobs(): Promise<any> {
    return this.get('/jobs');
  }

  async runJobNow(id: string): Promise<any> {
    return this.post('/jobs/run', { id });
  }

  async deleteJob(id: string): Promise<any> {
    return this.post('/jobs/delete', { id });
  }

  async getTraktList(url: string): Promise<any[]> {
    return this.get(`/trakt/list?url=${encodeURIComponent(url)}`);
  }

  async getMdbList(url: string): Promise<any[]> {
    return this.get(`/mdblist/list?url=${encodeURIComponent(url)}`);
  }

  async pinCollection(title: string, library: string): Promise<void> {
    await this.post('/collections/pin', { title, library });
  }

  async unpinCollection(title: string, library: string): Promise<void> {
    await this.post('/collections/unpin', { title, library });
  }

  async getPlexLibraries(): Promise<any[]> {
    return this.get('/plex/libraries');
  }
}

export const api = new ApiService();