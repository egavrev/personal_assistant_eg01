import { Component, inject } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { DashboardService } from './dashboard.service';
import { PipelineControlComponent } from './pipeline-control.component';
import { WeeklyTrendChartComponent } from './charts/weekly-trend-chart.component';
import { CategoryBreakdownChartComponent } from './charts/category-breakdown-chart.component';

/**
 * Mail-processing status: headline stat cards, the last pipeline run, and two
 * charts (weekly trend + category breakdown). Data comes from DashboardService,
 * loaded once on construction and exposed via signals.
 */
@Component({
  selector: 'app-dashboard',
  imports: [
    DecimalPipe,
    PipelineControlComponent,
    WeeklyTrendChartComponent,
    CategoryBreakdownChartComponent,
  ],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent {
  protected readonly stats = inject(DashboardService);

  constructor() {
    void this.stats.load();
  }

  protected reload(): void {
    void this.stats.load();
  }
}
