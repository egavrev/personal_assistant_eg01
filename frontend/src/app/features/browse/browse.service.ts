import { computed, inject, Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

/** The AI label shown in a Browse row — mirrors the backend BrowseClassification. */
export interface BrowseClassification {
  category: string | null;
  confidence: number;
}

/** One classified/corrected email — mirrors the backend BrowseItem. */
export interface BrowseItem {
  id: string;
  sender_raw: string;
  subject: string;
  snippet: string;
  body_excerpt: string;
  status: string;
  week: string | null;
  classification: BrowseClassification;
}

interface BrowseResponse {
  items: BrowseItem[];
  total: number;
}

/** One row of the category dropdown — mirrors the backend CategoryCount. */
export interface CategoryCount {
  category: string;
  count: number;
}

interface CategoriesResponse {
  categories: CategoryCount[];
}

interface UnsortResponse {
  status: string;
  flagged_for_review: boolean;
}

/**
 * Drives the Browse view: loads the category list, fetches one category's
 * classified/corrected mail a page at a time (lowest-confidence first), and
 * marks a row "unsorted" (-> needs_review) so it moves to the Review Queue.
 *
 * Mirrors ReviewService/DashboardService (signals, loading/error flags). The
 * session cookie rides along via the global credentialsInterceptor — every call
 * already goes out with credentials, no per-call wiring. The only write here is
 * unsort, which logs no correction (that happens later in the Review Queue).
 */
@Injectable({ providedIn: 'root' })
export class BrowseService {
  private readonly http = inject(HttpClient);

  /** Server page size for a category. */
  private readonly PAGE = 50;

  private readonly _categories = signal<readonly CategoryCount[]>([]);
  private readonly _selected = signal<string | null>(null);
  private readonly _items = signal<readonly BrowseItem[]>([]);
  private readonly _total = signal(0);

  private readonly _categoriesLoading = signal(false);
  private readonly _categoriesError = signal(false);
  private readonly _loading = signal(false); // first page of a category
  private readonly _loadingMore = signal(false);
  private readonly _error = signal(false);
  private readonly _exhausted = signal(false);

  private readonly _busyId = signal<string | null>(null); // unsort in flight
  private readonly _flagged = signal(0); // marked unsorted this session
  private readonly _toast = signal('');
  private toastTimer: ReturnType<typeof setTimeout> | null = null;

  readonly categories = this._categories.asReadonly();
  readonly selected = this._selected.asReadonly();
  readonly items = this._items.asReadonly();
  readonly total = this._total.asReadonly();
  readonly categoriesLoading = this._categoriesLoading.asReadonly();
  readonly categoriesError = this._categoriesError.asReadonly();
  readonly loading = this._loading.asReadonly();
  readonly loadingMore = this._loadingMore.asReadonly();
  readonly error = this._error.asReadonly();
  readonly flagged = this._flagged.asReadonly();
  readonly toast = this._toast.asReadonly();

  /** True once a category is chosen but it has no classified/corrected mail. */
  readonly isEmpty = computed(
    () =>
      this._selected() !== null &&
      !this._loading() &&
      !this._error() &&
      this._items().length === 0,
  );

  /** Whether a "Load more" page remains for the current category. */
  readonly hasMore = computed(
    () => !this._exhausted() && this._items().length < this._total(),
  );

  /** Disable just the row whose unsort is in flight. */
  isBusy(id: string): boolean {
    return this._busyId() === id;
  }

  /** Load the category dropdown (counts via the backend's aggregation read). */
  async loadCategories(): Promise<void> {
    this._categoriesLoading.set(true);
    this._categoriesError.set(false);
    try {
      const res = await firstValueFrom(
        this.http.get<CategoriesResponse>('/api/signals/categories'),
      );
      this._categories.set(res.categories);
    } catch {
      this._categoriesError.set(true);
    } finally {
      this._categoriesLoading.set(false);
    }
  }

  /** Switch to a category (or clear with null): reset the list and load page 1. */
  async select(category: string | null): Promise<void> {
    this._selected.set(category);
    this._items.set([]);
    this._total.set(0);
    this._exhausted.set(false);
    this._error.set(false);
    if (category === null) return;

    this._loading.set(true);
    try {
      const res = await this.fetchPage(category);
      this._items.set(res.items);
      this._total.set(res.total);
      if (res.items.length < this.PAGE) this._exhausted.set(true);
    } catch {
      this._error.set(true);
    } finally {
      this._loading.set(false);
    }
  }

  /** Append the next page for the current category. */
  async loadMore(): Promise<void> {
    const category = this._selected();
    if (category === null || this._loadingMore() || !this.hasMore()) return;
    this._loadingMore.set(true);
    const items = this._items();
    const after = items.length ? items[items.length - 1].id : undefined;
    try {
      const res = await this.fetchPage(category, after);
      this._total.set(res.total);
      if (res.items.length === 0) {
        this._exhausted.set(true);
        return;
      }
      this._items.update((cur) => [...cur, ...res.items]);
      if (res.items.length < this.PAGE) this._exhausted.set(true);
    } catch {
      // A paging failure shouldn't wipe the list; stop here and let the user
      // retry. Treat as exhausted so we don't loop on the same error.
      this._exhausted.set(true);
      this._error.set(true);
    } finally {
      this._loadingMore.set(false);
    }
  }

  /**
   * Mark a row unsorted: POST /unsort flips it to needs_review (no correction
   * logged). On success the row drops out of the list, the category count and
   * total tick down, and the session counter ticks up.
   */
  async unsort(id: string): Promise<void> {
    if (this._busyId()) return;
    this._busyId.set(id);
    try {
      await firstValueFrom(
        this.http.post<UnsortResponse>(`/api/signals/${id}/unsort`, {}),
      );
      this._items.update((cur) => cur.filter((it) => it.id !== id));
      this._total.update((n) => Math.max(0, n - 1));
      this._flagged.update((n) => n + 1);
      this.decrementCategory(this._selected());
      this.flashToast('Sent to Review Queue');
    } catch {
      this.flashToast('Could not mark unsorted — try again');
    } finally {
      this._busyId.set(null);
    }
  }

  /** Keep the dropdown count in sync after a successful unsort. */
  private decrementCategory(category: string | null): void {
    if (category === null) return;
    this._categories.update((cats) =>
      cats.map((c) =>
        c.category === category ? { ...c, count: Math.max(0, c.count - 1) } : c,
      ),
    );
  }

  private fetchPage(category: string, after?: string): Promise<BrowseResponse> {
    const params = new URLSearchParams({
      category,
      limit: String(this.PAGE),
    });
    if (after) params.set('after', after);
    return firstValueFrom(
      this.http.get<BrowseResponse>(`/api/signals?${params.toString()}`),
    );
  }

  private flashToast(message: string): void {
    this._toast.set(message);
    if (this.toastTimer) clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => this._toast.set(''), 2500);
  }
}
