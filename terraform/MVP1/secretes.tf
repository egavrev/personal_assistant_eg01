resource "google_secret_manager_secret" "gmail_token" {
  secret_id  = "gmail-oauth-token"
  project    = var.project_id
  replication { 
        auto {} 
        }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "your_gmail_access" {
  secret_id = google_secret_manager_secret.gmail_token.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "user:${var.your_email}"
}

resource "google_secret_manager_secret" "telegram_token" {
  secret_id  = "telegram-bot-token"
  project    = var.project_id
  replication { 
    auto {} 
    }
  depends_on = [google_project_service.apis]
}

# After apply, add values manually:
# gcloud secrets versions add gmail-oauth-token \
#   --data-file=token.json --project=PROJECT_ID
# gcloud secrets versions add telegram-bot-token \
#   --data-file=- --project=PROJECT_ID