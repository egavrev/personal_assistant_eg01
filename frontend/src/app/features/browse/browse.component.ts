import { Component, inject } from '@angular/core';
import { BrowseService } from './browse.service';

/**
 * Browse classified mail by category to spot mislabels. Scan sender + subject +
 * a short excerpt, lowest-confidence first, and "Mark unsorted" anything wrong —
 * that sends it to the Review Queue, where the actual correction is made. There
 * is deliberately no correction form here. All state lives in BrowseService.
 */
@Component({
  selector: 'app-browse',
  imports: [],
  templateUrl: './browse.component.html',
})
export class BrowseComponent {
  protected readonly browse = inject(BrowseService);

  constructor() {
    void this.browse.loadCategories();
  }

  protected onCategoryChange(e: Event): void {
    const value = (e.target as HTMLSelectElement).value;
    void this.browse.select(value || null);
  }

  protected markUnsorted(id: string): void {
    void this.browse.unsort(id);
  }

  protected loadMore(): void {
    void this.browse.loadMore();
  }

  /** Confidence as a whole percentage for the bar/label. */
  protected confidencePct(c: number): number {
    return Math.round(c * 100);
  }

  /** Display name from a raw sender ("GitHub <x@y>" -> "GitHub"); fall back to raw. */
  protected senderName(raw: string): string {
    const name = raw.split('<')[0].trim().replace(/^"|"$/g, '');
    return name || raw;
  }
}
