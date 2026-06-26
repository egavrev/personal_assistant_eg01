import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { DashboardService } from './dashboard.service';
import { PipelineService } from './pipeline.service';

/**
 * Bulk week-processing control for the Dashboard: pick how many weeks to process,
 * optionally dry-run, and Run. It starts a background pipeline job and shows live
 * progress while polling. On completion it refreshes the dashboard counts so the
 * newly processed mail shows up.
 *
 * State lives in PipelineService; this component is just the form + progress.
 */
@Component({
  selector: 'app-pipeline-control',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="rounded-lg border border-slate-200 bg-white p-4">
      <div class="flex items-center justify-between">
        <h2 class="text-sm font-semibold text-slate-900">Process weeks</h2>
        @if (pipeline.state(); as st) {
          <p class="text-xs text-slate-500">
            Next window:
            <span class="tabular-nums text-slate-700">{{ st.next_start }} → {{ st.next_end }}</span>
          </p>
        }
      </div>
      <p class="mt-1 text-xs text-slate-500">
        Runs the real pipeline forward from the cursor, one week at a time.
      </p>

      <!-- Controls -->
      <div class="mt-3 flex flex-wrap items-end gap-4">
        <div>
          <label class="text-[10px] font-medium uppercase tracking-wide text-slate-400">Weeks</label>
          <input
            type="number"
            min="1"
            max="52"
            [value]="count()"
            (input)="onCountInput($event)"
            [disabled]="pipeline.running()"
            class="mt-1 block w-24 rounded-md border border-slate-300 px-3 py-2 text-sm tabular-nums text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50"
          />
        </div>

        <label class="flex items-center gap-2 pb-2 text-sm text-slate-700">
          <input
            type="checkbox"
            [checked]="dryRun()"
            (change)="onDryRunChange($event)"
            [disabled]="pipeline.running()"
            class="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 disabled:opacity-50"
          />
          Dry run
          <span class="text-xs text-slate-400">(no writes, cursor stays)</span>
        </label>

        <button
          type="button"
          (click)="run()"
          [disabled]="pipeline.running()"
          class="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50"
        >
          {{ pipeline.running() ? 'Running…' : 'Run' }}
        </button>
      </div>

      <!-- Progress -->
      @if (pipeline.job(); as job) {
        <div class="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
          <div class="flex items-center justify-between text-xs">
            <span class="font-medium text-slate-700">
              @if (job.state === 'running') {
                Week {{ job.weeks_done + 1 }} of {{ job.weeks_total }}
                @if (job.current_week) {
                  · last done {{ job.current_week }}
                }
              } @else if (job.state === 'done') {
                Done — {{ job.weeks_done }} of {{ job.weeks_total }} week(s){{ job.dry_run ? ' (dry run)' : '' }}
              } @else {
                Stopped after {{ job.weeks_done }} of {{ job.weeks_total }} week(s)
              }
            </span>
            <span class="tabular-nums text-slate-500">
              {{ job.totals.classified }} classified · {{ job.totals.needs_review }} to review
            </span>
          </div>
          <div class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
            <div
              class="h-full rounded-full transition-all"
              [class]="job.state === 'error' ? 'bg-red-500' : 'bg-indigo-500'"
              [style.width.%]="progressPct(job.weeks_done, job.weeks_total)"
            ></div>
          </div>
        </div>
      }

      @if (pipeline.error(); as err) {
        <p class="mt-3 text-xs font-medium text-red-700">{{ err }}</p>
      }
    </section>
  `,
})
export class PipelineControlComponent {
  protected readonly pipeline = inject(PipelineService);
  private readonly stats = inject(DashboardService);

  protected readonly count = signal(1);
  protected readonly dryRun = signal(false);

  constructor() {
    void this.pipeline.loadState();
  }

  protected onCountInput(e: Event): void {
    const n = Number.parseInt((e.target as HTMLInputElement).value, 10);
    this.count.set(Number.isFinite(n) ? Math.max(1, Math.min(n, 52)) : 1);
  }

  protected onDryRunChange(e: Event): void {
    this.dryRun.set((e.target as HTMLInputElement).checked);
  }

  protected progressPct(done: number, total: number): number {
    return total > 0 ? (done / total) * 100 : 0;
  }

  protected async run(): Promise<void> {
    const dryRun = this.dryRun();
    await this.pipeline.run(this.count(), dryRun);
    // Refresh the cursor, and the dashboard counts when real mail was written.
    await this.pipeline.loadState();
    if (!dryRun) await this.stats.load();
  }
}
