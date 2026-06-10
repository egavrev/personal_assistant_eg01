output "orchestrator_url" {
  value = google_cloud_run_v2_service.agents["orchestrator"].uri
}
output "ingestor_url" {
  value = google_cloud_run_v2_service.agents["ingestor"].uri
}
output "classifier_url" {
  value = google_cloud_run_v2_service.agents["classifier"].uri
}
output "judge_url" {
  value = google_cloud_run_v2_service.agents["judge"].uri
}
output "corrector_url" {
  value = google_cloud_run_v2_service.agents["corrector"].uri
}
output "firestore_db" {
  value = google_firestore_database.default.name
}
output "secret_next_steps" {
  value = "Run: gcloud secrets versions add gmail-oauth-token --data-file=token.json"
}