import { inject, Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

/** Per-week figures from a bulk run — mirrors the backend WeekResult. */
export interface WeekResult {
  week: string;
  fetched: number;
  junk_filtered: number;
  classified: number;
  needs_review: number;
}

/** Running totals accumulated across completed weeks. */
export interface RunTotals {
  fetched: number;
  junk_filtered: number;
  classified: number;
  needs_review: number;
}

/** Status of a bulk run job — mirrors the backend JobStatus. */
export interface JobStatus {
  job_id: string;
  state: 'running' | 'done' | 'error';
  dry_run: boolean;
  weeks_total: number;
  weeks_done: number;
  current_week: string | null;
  totals: RunTotals;
  weeks: WeekResult[];
  error: string | null;
}

interface StartResponse {
  job_id: string;
  state: string;
  weeks_total: number;
}

/** The ingestion cursor and the next window — mirrors the backend PipelineState. */
export interface PipelineState {
  last_processed_date: string;
  next_start: string;
  next_end: string;
}

/**
 * Drives the bulk week-processing control: reads the cursor, starts a background
 * run of N weeks, and polls its status until done/error. The actual pipeline
 * work runs server-side; this only kicks it off and reports progress.
 *
 * The session cookie rides along via the global credentialsInterceptor.
 */
@Injectable({ providedIn: 'root' })
export class PipelineService {
  private readonly http = inject(HttpClient);

  /** Poll cadence while a run is in progress. */
  private readonly POLL_MS = 1500;

  private readonly _state = signal<PipelineState | null>(null);
  private readonly _job = signal<JobStatus | null>(null);
  private readonly _running = signal(false);
  private readonly _error = signal('');

  readonly state = this._state.asReadonly();
  readonly job = this._job.asReadonly();
  readonly running = this._running.asReadonly();
  readonly error = this._error.asReadonly();

  /** Read the current cursor + next window (no side effects beyond a GET). */
  async loadState(): Promise<void> {
    try {
      this._state.set(
        await firstValueFrom(this.http.get<PipelineState>('/api/pipeline/state')),
      );
    } catch {
      this._state.set(null);
    }
  }

  /**
   * Start a run of ``count`` weeks and poll to completion. Resolves when the job
   * reaches done or error; the caller refreshes the dashboard counts afterward.
   */
  async run(count: number, dryRun: boolean): Promise<void> {
    if (this._running()) return;
    this._running.set(true);
    this._error.set('');
    this._job.set(null);
    try {
      const params = new URLSearchParams({
        count: String(count),
        dry_run: String(dryRun),
      });
      const start = await firstValueFrom(
        this.http.post<StartResponse>(
          `/api/pipeline/run-weeks?${params.toString()}`,
          {},
        ),
      );
      await this.poll(start.job_id);
    } catch {
      this._error.set('Could not start the run (one may already be in progress).');
    } finally {
      this._running.set(false);
    }
  }

  private async poll(jobId: string): Promise<void> {
    for (;;) {
      await this.sleep(this.POLL_MS);
      let status: JobStatus;
      try {
        status = await firstValueFrom(
          this.http.get<JobStatus>(`/api/pipeline/run-weeks/${jobId}/status`),
        );
      } catch {
        this._error.set('Lost contact with the run.');
        return;
      }
      this._job.set(status);
      if (status.state === 'done') return;
      if (status.state === 'error') {
        this._error.set(status.error ?? 'The run failed.');
        return;
      }
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
