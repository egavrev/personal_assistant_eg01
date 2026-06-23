import { inject, Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom, forkJoin } from 'rxjs';

/** Signal count per status — mirrors the backend's StatusCounts. */
export interface StatusCounts {
  classified: number;
  needs_review: number;
  junk_filtered: number;
  pending_classification: number;
  corrected: number;
}

export interface CategoryCount {
  name: string;
  count: number;
}

/** Headline figures from the most recent pipeline run. */
export interface LastRun {
  week: string | null;
  fetched: number;
  classified: number;
  needs_review: number;
  est_cost_usd: number;
}

/** Response of GET /api/stats/summary. */
export interface StatsSummary {
  status_counts: StatusCounts;
  total_signals: number;
  backlog_pending: number;
  needs_review_count: number;
  corrections_total: number;
  est_cost_total: number;
  categories: CategoryCount[];
  last_run: LastRun | null;
}

/** One element of GET /api/stats/weekly. */
export interface WeeklyPoint {
  week: string;
  fetched: number;
  junk_filtered: number;
  classified: number;
  needs_review: number;
}

/**
 * Fetches mail-processing stats and exposes them as signals for the dashboard.
 *
 * The session cookie is attached by the global credentialsInterceptor, so every
 * request here already goes out with `withCredentials: true` — no per-call wiring.
 */
@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly http = inject(HttpClient);

  private readonly _summary = signal<StatsSummary | null>(null);
  private readonly _weekly = signal<readonly WeeklyPoint[]>([]);
  private readonly _loading = signal(false);
  private readonly _error = signal(false);

  readonly summary = this._summary.asReadonly();
  readonly weekly = this._weekly.asReadonly();
  /** True while a load() is in flight. */
  readonly loading = this._loading.asReadonly();
  /** True when the last load() failed (transport or non-2xx). */
  readonly error = this._error.asReadonly();

  /** Load both stats endpoints in parallel and publish the result. */
  async load(): Promise<void> {
    this._loading.set(true);
    this._error.set(false);
    try {
      const [summary, weekly] = await firstValueFrom(
        forkJoin([
          this.http.get<StatsSummary>('/api/stats/summary'),
          this.http.get<WeeklyPoint[]>('/api/stats/weekly'),
        ]),
      );
      this._summary.set(summary);
      this._weekly.set(weekly);
    } catch {
      this._error.set(true);
    } finally {
      this._loading.set(false);
    }
  }
}
