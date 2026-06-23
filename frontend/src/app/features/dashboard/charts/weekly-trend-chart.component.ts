import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { WeeklyPoint } from '../dashboard.service';

type SeriesKey = 'fetched' | 'junk_filtered' | 'classified' | 'needs_review';
interface Series {
  key: SeriesKey;
  label: string;
  color: string;
}
interface BarRect {
  x: number;
  y: number;
  w: number;
  h: number;
  color: string;
  title: string;
}
interface AxisLabel {
  x: number;
  text: string;
  full: string;
}
interface YTick {
  y: number;
  value: number;
}

const SERIES: readonly Series[] = [
  { key: 'fetched', label: 'Fetched', color: '#94a3b8' }, // slate-400
  { key: 'junk_filtered', label: 'Junk', color: '#cbd5e1' }, // slate-300
  { key: 'classified', label: 'Classified', color: '#4f46e5' }, // indigo-600
  { key: 'needs_review', label: 'Needs review', color: '#f59e0b' }, // amber-500
];

const PLOT_H = 180;
const PAD_TOP = 8;
const PAD_BOTTOM = 26;
const PAD_LEFT = 34;
const GROUP_W = 56;
const BAR_GAP = 2;

/**
 * Grouped bar chart: one group per week, four bars (fetched / junk / classified
 * / needs_review). Hand-rolled SVG (no chart dependency); the plot area scrolls
 * horizontally when there are many weeks so each group stays readable.
 */
@Component({
  selector: 'app-weekly-trend-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="flex flex-wrap gap-x-4 gap-y-1 pb-3">
      @for (s of series; track s.key) {
        <span class="flex items-center gap-1.5 text-xs text-slate-600">
          <span class="h-2.5 w-2.5 rounded-sm" [style.background-color]="s.color"></span>
          {{ s.label }}
        </span>
      }
    </div>
    <div class="overflow-x-auto">
      <svg
        [attr.width]="width()"
        [attr.height]="height"
        [attr.viewBox]="'0 0 ' + width() + ' ' + height"
        role="img"
        aria-label="Weekly pipeline trend"
      >
        <!-- y gridlines + labels -->
        @for (t of yTicks(); track t.value) {
          <line
            [attr.x1]="padLeft"
            [attr.y1]="t.y"
            [attr.x2]="width()"
            [attr.y2]="t.y"
            stroke="#e2e8f0"
            stroke-width="1"
          />
          <text
            [attr.x]="padLeft - 6"
            [attr.y]="t.y + 3"
            text-anchor="end"
            class="fill-slate-400 text-[10px] tabular-nums"
          >
            {{ t.value }}
          </text>
        }
        <!-- bars -->
        @for (b of bars(); track $index) {
          <rect [attr.x]="b.x" [attr.y]="b.y" [attr.width]="b.w" [attr.height]="b.h" [attr.fill]="b.color">
            <title>{{ b.title }}</title>
          </rect>
        }
        <!-- x labels -->
        @for (l of xLabels(); track l.full) {
          <text
            [attr.x]="l.x"
            [attr.y]="plotBottom + 16"
            text-anchor="middle"
            class="fill-slate-500 text-[10px]"
          >
            {{ l.text }}
            <title>{{ l.full }}</title>
          </text>
        }
      </svg>
    </div>
  `,
})
export class WeeklyTrendChartComponent {
  readonly data = input.required<readonly WeeklyPoint[]>();

  protected readonly series = SERIES;
  protected readonly height = PAD_TOP + PLOT_H + PAD_BOTTOM;
  protected readonly padLeft = PAD_LEFT;
  protected readonly plotBottom = PAD_TOP + PLOT_H;

  private readonly max = computed(() => {
    let m = 0;
    for (const p of this.data()) {
      m = Math.max(m, p.fetched, p.junk_filtered, p.classified, p.needs_review);
    }
    return m;
  });

  protected readonly width = computed(() => PAD_LEFT + this.data().length * GROUP_W + 8);

  protected readonly bars = computed<BarRect[]>(() => {
    const max = this.max() || 1;
    const innerW = GROUP_W - 8;
    const barW = (innerW - (SERIES.length - 1) * BAR_GAP) / SERIES.length;
    const out: BarRect[] = [];
    this.data().forEach((p, i) => {
      const groupX = PAD_LEFT + i * GROUP_W + 4;
      SERIES.forEach((s, j) => {
        const value = p[s.key];
        const h = (value / max) * PLOT_H;
        out.push({
          x: groupX + j * (barW + BAR_GAP),
          y: PAD_TOP + PLOT_H - h,
          w: barW,
          h,
          color: s.color,
          title: `${p.week} · ${s.label}: ${value}`,
        });
      });
    });
    return out;
  });

  protected readonly xLabels = computed<AxisLabel[]>(() =>
    this.data().map((p, i) => ({
      x: PAD_LEFT + i * GROUP_W + GROUP_W / 2,
      text: p.week.slice(5), // "2024-W16" -> "W16"
      full: p.week,
    })),
  );

  protected readonly yTicks = computed<YTick[]>(() => {
    const max = this.max();
    if (max === 0) {
      return [{ y: PAD_TOP + PLOT_H, value: 0 }];
    }
    return [0, max / 2, max].map((v) => ({
      y: PAD_TOP + PLOT_H - (v / max) * PLOT_H,
      value: Math.round(v),
    }));
  });
}
