import { computed, inject, Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

/** The AI's proposed classification — mirrors the backend AIClassification. */
export interface AIClassification {
  category: string | null;
  topics: string[];
  sender_type: string | null;
  needs_reply: boolean;
  confidence: number;
}

/** One needs_review email — mirrors the backend QueueItem. */
export interface ReviewItem {
  id: string;
  sender_raw: string;
  sender_ref: string | null;
  subject: string;
  snippet: string;
  body_excerpt: string;
  week: string | null;
  classification: AIClassification;
}

interface QueueResponse {
  items: ReviewItem[];
  remaining: number;
}

/** Source-of-truth dropdown/topic options from GET /api/review/config. */
export interface ReviewConfig {
  categories: string[];
  seed_interests: string[];
}

/** Only the changed fields are sent to POST /correct. */
export interface CorrectionChanges {
  category?: string;
  topics?: string[];
  needs_reply?: boolean;
  sender_type?: string;
}

interface AcceptResponse {
  status: string;
  category: string | null;
  labeled: boolean;
}

interface CorrectResponse {
  status: string;
  corrections_written: number;
  changed_fields: string[];
  labeled: boolean;
}

/**
 * Drives the Review Queue: fetches needs_review items one page at a time, tracks
 * the current item, advances through accept/correct/skip, and keeps the session
 * counters. Mirrors DashboardService (signals, loading/error flags); the session
 * cookie rides along via the global credentialsInterceptor.
 */
@Injectable({ providedIn: 'root' })
export class ReviewService {
  private readonly http = inject(HttpClient);

  /** Server page size for the queue. */
  private readonly PAGE = 20;

  private readonly _items = signal<readonly ReviewItem[]>([]);
  private readonly _index = signal(0);
  private readonly _remaining = signal(0);
  private readonly _sessionTotal = signal(0);
  private readonly _exhausted = signal(false); // no more server pages

  private readonly _loading = signal(false);
  private readonly _error = signal(false);
  private readonly _busy = signal(false); // an accept/correct request is in flight

  private readonly _categories = signal<readonly string[]>([]);
  private readonly _seedInterests = signal<readonly string[]>([]);

  private readonly _processed = signal(0); // accept + correct + skip (for position)
  private readonly _reviewed = signal(0); // accept + correct (not skip)
  private readonly _correctionsLogged = signal(0);
  private readonly _lastConfirmation = signal<string>('');

  /** The item currently under review, or null when the queue is drained. */
  readonly current = computed<ReviewItem | null>(
    () => this._items()[this._index()] ?? null,
  );
  readonly loading = this._loading.asReadonly();
  readonly error = this._error.asReadonly();
  readonly busy = this._busy.asReadonly();
  readonly remaining = this._remaining.asReadonly();
  readonly categories = this._categories.asReadonly();
  readonly seedInterests = this._seedInterests.asReadonly();
  readonly reviewedCount = this._reviewed.asReadonly();
  readonly correctionsLogged = this._correctionsLogged.asReadonly();
  readonly lastConfirmation = this._lastConfirmation.asReadonly();

  /** 1-based position of the current item in the session. */
  readonly position = computed(() => this._processed() + 1);
  /** Stable session total captured at first load (the remaining count then). */
  readonly total = computed(() => this._sessionTotal());
  /** True once everything is reviewed and there are no more pages. */
  readonly isEmpty = computed(
    () => !this._loading() && !this._error() && this.current() === null,
  );

  /** Initial load: config + first page, resetting all session counters. */
  async start(): Promise<void> {
    this._loading.set(true);
    this._error.set(false);
    this._items.set([]);
    this._index.set(0);
    this._exhausted.set(false);
    this._processed.set(0);
    this._reviewed.set(0);
    this._correctionsLogged.set(0);
    this._lastConfirmation.set('');
    try {
      if (this._categories().length === 0) {
        await this.loadConfig();
      }
      const res = await this.fetchQueue();
      this._items.set(res.items);
      this._remaining.set(res.remaining);
      this._sessionTotal.set(res.remaining);
      if (res.items.length < this.PAGE) {
        this._exhausted.set(true);
      }
    } catch {
      this._error.set(true);
    } finally {
      this._loading.set(false);
    }
  }

  /** Confirm the AI was right: status -> classified, no correction. Advances. */
  async accept(): Promise<void> {
    const item = this.current();
    if (!item || this._busy()) return;
    this._busy.set(true);
    try {
      await firstValueFrom(
        this.http.post<AcceptResponse>(`/api/review/${item.id}/accept`, {}),
      );
      this._reviewed.update((n) => n + 1);
      this._remaining.update((n) => Math.max(0, n - 1));
      this._lastConfirmation.set('Accepted');
      await this.advance();
    } catch {
      this._lastConfirmation.set('Accept failed — try again');
    } finally {
      this._busy.set(false);
    }
  }

  /** Submit only the changed fields. Logs one correction per changed field. */
  async correct(changes: CorrectionChanges): Promise<void> {
    const item = this.current();
    if (!item || this._busy()) return;
    this._busy.set(true);
    try {
      const res = await firstValueFrom(
        this.http.post<CorrectResponse>(`/api/review/${item.id}/correct`, changes),
      );
      this._reviewed.update((n) => n + 1);
      this._correctionsLogged.update((n) => n + res.corrections_written);
      this._remaining.update((n) => Math.max(0, n - 1));
      const c = res.corrections_written;
      this._lastConfirmation.set(
        c === 0
          ? 'No changes — nothing logged'
          : `${c} correction${c === 1 ? '' : 's'} logged`,
      );
      await this.advance();
    } catch {
      this._lastConfirmation.set('Correction failed — try again');
    } finally {
      this._busy.set(false);
    }
  }

  /** Leave the item in needs_review and move on (revisit it later). */
  async skip(): Promise<void> {
    if (!this.current() || this._busy()) return;
    this._lastConfirmation.set('Skipped');
    await this.advance();
  }

  /** Reload the queue without resetting the session counters (manual refresh). */
  async refresh(): Promise<void> {
    await this.start();
  }

  private async loadConfig(): Promise<void> {
    const cfg = await firstValueFrom(
      this.http.get<ReviewConfig>('/api/review/config'),
    );
    this._categories.set(cfg.categories);
    this._seedInterests.set(cfg.seed_interests);
  }

  private fetchQueue(after?: string): Promise<QueueResponse> {
    const params = new URLSearchParams({ limit: String(this.PAGE) });
    if (after) params.set('after', after);
    return firstValueFrom(
      this.http.get<QueueResponse>(`/api/review/queue?${params.toString()}`),
    );
  }

  /** Move to the next item, fetching the next server page when needed. */
  private async advance(): Promise<void> {
    this._processed.update((n) => n + 1);
    const next = this._index() + 1;
    if (next < this._items().length) {
      this._index.set(next);
      return;
    }
    if (!this._exhausted()) {
      await this.loadMore();
    }
    // If loadMore appended items, `next` now points at the first of them;
    // otherwise current() resolves to null and the empty state shows.
    this._index.set(next);
  }

  private async loadMore(): Promise<void> {
    const items = this._items();
    const after = items.length ? items[items.length - 1].id : undefined;
    try {
      const res = await this.fetchQueue(after);
      this._remaining.set(res.remaining);
      if (res.items.length === 0) {
        this._exhausted.set(true);
        return;
      }
      this._items.update((cur) => [...cur, ...res.items]);
      if (res.items.length < this.PAGE) {
        this._exhausted.set(true);
      }
    } catch {
      // A paging failure shouldn't wipe the session; stop here and let the user
      // refresh. Treat as exhausted so we don't loop on the same error.
      this._exhausted.set(true);
      this._error.set(true);
    }
  }
}
