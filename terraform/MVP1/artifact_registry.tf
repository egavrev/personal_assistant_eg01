resource "google_artifact_registry_repository" "agents" {
  project       = var.project_id
  location      = var.region
  repository_id = "agents"
  description   = "Mail assistant agent container images"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

data "google_project" "project" {
  project_id = var.project_id
}

resource "google_artifact_registry_repository_iam_member" "cloudbuild_push" {
  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.agents.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"
}