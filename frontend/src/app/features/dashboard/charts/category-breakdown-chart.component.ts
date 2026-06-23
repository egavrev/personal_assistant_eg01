import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { CategoryCount } from '../dashboard.service';

/**
 * Horizontal bar breakdown of top categories. CSS bars (no chart dependency):
 * each row is a label, a proportional fill, and the count — readable and dense.
 */
@Component({
  selector: 'app-category-breakdown-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="space-y-2">
      @for (c of data(); track c.name) {
        <div class="flex items-center gap-3 text-sm">
          <span class="w-44 shrink-0 truncate text-slate-600" [title]="c.name">{{ c.name }}</span>
          <div class="h-5 flex-1 rounded bg-slate-100">
            <div class="h-5 rounded bg-indigo-500" [style.width.%]="pct(c.count)"></div>
          </div>
          <span class="w-10 shrink-0 text-right font-medium tabular-nums text-slate-700">
            {{ c.count }}
          </span>
        </div>
      }
    </div>
  `,
})
export class CategoryBreakdownChartComponent {
  readonly data = input.required<readonly CategoryCount[]>();

  private readonly max = computed(() =>
    this.data().reduce((m, c) => Math.max(m, c.count), 1),
  );

  protected pct(count: number): number {
    return (count / this.max()) * 100;
  }
}
