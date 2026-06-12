# 1. The Knowledge Graph Database
resource "google_firestore_database" "default" {
  project     = var.project_id
  
  # "(default)" is a required naming convention for your primary DB in GCP
  name        = "(default)" 
  location_id = var.region
  
  # This sets it as a NoSQL document database, perfect for our arrays
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.apis]
}

# 2. The Empty Secret Container for the Gmail Token
resource "google_secret_manager_secret" "gmail_refresh_token" {
  secret_id = "gmail-refresh-token"
  project   = var.project_id
  
  # Tells GCP to automatically replicate this secret for high availability
  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}