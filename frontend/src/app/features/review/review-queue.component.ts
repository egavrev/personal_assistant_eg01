import {
  Component,
  computed,
  HostListener,
  inject,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { CorrectionChanges, ReviewService } from './review.service';

/** The three entity types a human can assign. */
const SENDER_TYPES = ['person', 'organisation', 'system'] as const;
type SenderType = (typeof SENDER_TYPES)[number];

/**
 * The human-in-the-loop review surface: one needs_review email at a time with
 * the AI's proposed classification, and Accept / Correct / Skip actions. The
 * Correct form's four fields are driven by /api/review/config (categories +
 * seed interests). All queue state and session counters live in ReviewService.
 */
@Component({
  selector: 'app-review-queue',
  imports: [RouterLink],
  templateUrl: './review-queue.component.html',
})
export class ReviewQueueComponent {
  protected readonly review = inject(ReviewService);

  /** Sentinel <option> value that reveals the free-text "new category" input. */
  protected readonly NEW_CATEGORY = '__new__';
  protected readonly senderTypes = SENDER_TYPES;

  // Correct-form state (initialised from the current item when the form opens).
  protected readonly correcting = signal(false);
  protected readonly formCategory = signal('');
  protected readonly formNewCategory = signal('');
  protected readonly formTopics = signal<readonly string[]>([]);
  protected readonly formNeedsReply = signal(false);
  protected readonly formSenderType = signal<string>('');
  protected readonly customTopic = signal('');

  /** Chip choices: seed interests ∪ the item's current topics ∪ any added. */
  protected readonly topicChoices = computed<readonly string[]>(() => {
    const current = this.review.current()?.classification.topics ?? [];
    return [
      ...new Set<string>([
        ...this.review.seedInterests(),
        ...current,
        ...this.formTopics(),
      ]),
    ];
  });

  constructor() {
    void this.review.start();
  }

  /**
   * Keyboard-first review: a=accept, c=correct, s=skip when an item is up;
   * Enter=save, Esc=cancel while the correct form is open. Letter shortcuts are
   * suppressed during correction so typing into the form fields is unaffected;
   * the topic input stops Enter from bubbling, so Enter there adds a tag instead.
   */
  @HostListener('document:keydown', ['$event'])
  protected onKeydown(e: KeyboardEvent): void {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (!this.review.current() || this.review.busy()) return;

    if (this.correcting()) {
      if (e.key === 'Enter') {
        e.preventDefault();
        this.saveCorrection();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        this.cancelCorrect();
      }
      return;
    }

    switch (e.key.toLowerCase()) {
      case 'a':
        e.preventDefault();
        this.accept();
        break;
      case 'c':
        e.preventDefault();
        this.openCorrect();
        break;
      case 's':
        e.preventDefault();
        this.skip();
        break;
    }
  }

  /** Confidence as a whole percentage for the bar/label. */
  protected confidencePct(c: number): number {
    return Math.round(c * 100);
  }

  protected accept(): void {
    if (this.correcting()) return;
    void this.review.accept();
  }

  protected skip(): void {
    if (this.correcting()) return;
    void this.review.skip();
  }

  protected reload(): void {
    void this.review.refresh();
  }

  // ---------- correct form ----------
  protected openCorrect(): void {
    const item = this.review.current();
    if (!item || this.review.busy()) return;
    const c = item.classification;
    this.formCategory.set(c.category ?? '');
    this.formNewCategory.set('');
    this.formTopics.set([...c.topics]);
    this.formNeedsReply.set(c.needs_reply);
    this.formSenderType.set(c.sender_type ?? '');
    this.customTopic.set('');
    this.correcting.set(true);
  }

  protected cancelCorrect(): void {
    this.correcting.set(false);
  }

  protected onCategoryChange(e: Event): void {
    this.formCategory.set((e.target as HTMLSelectElement).value);
  }

  protected onNewCategoryInput(e: Event): void {
    this.formNewCategory.set((e.target as HTMLInputElement).value);
  }

  protected onCustomTopicInput(e: Event): void {
    this.customTopic.set((e.target as HTMLInputElement).value);
  }

  protected isTopicSelected(t: string): boolean {
    return this.formTopics().includes(t);
  }

  protected toggleTopic(t: string): void {
    this.formTopics.update((list) =>
      list.includes(t) ? list.filter((x) => x !== t) : [...list, t],
    );
  }

  protected addCustomTopic(): void {
    const t = this.customTopic().trim();
    if (t && !this.formTopics().includes(t)) {
      this.formTopics.update((list) => [...list, t]);
    }
    this.customTopic.set('');
  }

  protected setNeedsReply(v: boolean): void {
    this.formNeedsReply.set(v);
  }

  protected setSenderType(t: SenderType): void {
    this.formSenderType.set(t);
  }

  /** Build the changed-fields-only payload and submit it. */
  protected saveCorrection(): void {
    const item = this.review.current();
    if (!item || this.review.busy()) return;
    const c = item.classification;
    const changes: CorrectionChanges = {};

    const category =
      this.formCategory() === this.NEW_CATEGORY
        ? this.formNewCategory().trim()
        : this.formCategory();
    if (category && category !== c.category) changes.category = category;

    const topics = [...this.formTopics()];
    if (!this.sameTopics(topics, c.topics)) changes.topics = topics;

    if (this.formNeedsReply() !== c.needs_reply) {
      changes.needs_reply = this.formNeedsReply();
    }

    const senderType = this.formSenderType();
    if (senderType && senderType !== c.sender_type) {
      changes.sender_type = senderType;
    }

    this.correcting.set(false);
    void this.review.correct(changes);
  }

  /** Order-insensitive list equality (matches the backend's topics diff). */
  private sameTopics(a: readonly string[], b: readonly string[]): boolean {
    if (a.length !== b.length) return false;
    const sb = [...b].sort();
    return [...a].sort().every((v, i) => v === sb[i]);
  }
}
