resource "google_logging_metric" "judge_rejections" {
  name    = "judge_rejection_rate"
  project = var.project_id
  filter  = <<-EOT
    resource.type="cloud_run_revision"
    jsonPayload.outcome="judge_rejected"
  EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

resource "google_logging_metric" "loop_count" {
  name    = "loop_count_per_run"
  project = var.project_id
  filter  = <<-EOT
    resource.type="cloud_run_revision"
    jsonPayload.loop_count>0
  EOT
  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
  value_extractor = "EXTRACT(jsonPayload.loop_count)"
}

resource "google_monitoring_alert_policy" "p99_latency" {
  project      = var.project_id
  display_name = "Classifier p99 latency > 5s"
  combiner     = "OR"
  conditions {
    display_name = "p99 latency spike"
    condition_threshold {
      filter      = "resource.type="cloud_run_revision" AND resource.labels.service_name="classifier""
      comparison  = "COMPARISON_GT"
      threshold_value = 5000
      duration    = "300s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_PERCENTILE_99"
      }
    }
  }
  notification_channels = []
  alert_strategy {
    auto_close = "604800s"
  }
}

resource "google_monitoring_alert_policy" "judge_rejection_spike" {
  project      = var.project_id
  display_name = "Judge rejection rate > 80%"
  combiner     = "OR"
  conditions {
    display_name = "high rejection rate"
    condition_threshold {
      filter          = "metric.type="logging.googleapis.com/user/judge_rejection_rate""
      comparison      = "COMPARISON_GT"
      threshold_value = 80
      duration        = "600s"
    }
  }
  notification_channels = []
  alert_strategy {
    auto_close = "604800s"
  }
}