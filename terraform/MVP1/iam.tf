locals {
  agents = [
    "orchestrator","ingestor",
    "classifier","judge","corrector"
  ]
}

resource "google_service_account" "agents" {
  for_each     = toset(local.agents)
  account_id   = "sa-${each.key}"
  display_name = "${each.key} agent SA"
}

resource "google_project_iam_member" "vertex_users" {
  for_each = toset(["classifier","orchestrator"])
  project  = var.project_id
  role     = "roles/aiplatform.user"
  member   = "serviceAccount:${google_service_account.agents[each.key].email}"
}

resource "google_project_iam_member" "firestore_users" {
  for_each = toset(local.agents)
  project  = var.project_id
  role     = "roles/datastore.user"
  member   = "serviceAccount:${google_service_account.agents[each.key].email}"
}

resource "google_secret_manager_secret_iam_member" "ingestor_token" {
  secret_id = google_secret_manager_secret.gmail_token.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agents["ingestor"].email}"
}

resource "google_cloud_run_service_iam_member" "orch_calls_ingestor" {
  location = var.region
  service  = google_cloud_run_v2_service.agents["ingestor"].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.agents["orchestrator"].email}"
}

resource "google_cloud_run_service_iam_member" "orch_calls_classifier" {
  location = var.region
  service  = google_cloud_run_v2_service.agents["classifier"].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.agents["orchestrator"].email}"
}

resource "google_cloud_run_service_iam_member" "orch_calls_judge" {
  location = var.region
  service  = google_cloud_run_v2_service.agents["judge"].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.agents["orchestrator"].email}"
}

resource "google_cloud_run_service_iam_member" "orch_calls_corrector" {
  location = var.region
  service  = google_cloud_run_v2_service.agents["corrector"].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.agents["orchestrator"].email}"
}

resource "google_cloud_run_service_iam_member" "you_call_orch" {
  location = var.region
  service  = google_cloud_run_v2_service.agents["orchestrator"].name
  role     = "roles/run.invoker"
  member   = "user:${var.your_email}"
}