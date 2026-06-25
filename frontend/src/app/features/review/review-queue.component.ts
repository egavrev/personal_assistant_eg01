import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ReviewService } from './review.service';

/**
 * The human-in-the-loop review surface: one needs_review email at a time with
 * the AI's proposed classification, and Accept / Skip actions. The Correct form
 * and keyboard shortcuts are layered on in later steps. All queue state and the
 * session counters live in ReviewService.
 */
@Component({
  selector: 'app-review-queue',
  imports: [RouterLink],
  templateUrl: './review-queue.component.html',
})
export class ReviewQueueComponent {
  protected readonly review = inject(ReviewService);

  constructor() {
    void this.review.start();
  }

  /** Confidence as a whole percentage for the bar/label. */
  protected confidencePct(c: number): number {
    return Math.round(c * 100);
  }

  protected accept(): void {
    void this.review.accept();
  }

  protected skip(): void {
    void this.review.skip();
  }

  protected reload(): void {
    void this.review.refresh();
  }
}
