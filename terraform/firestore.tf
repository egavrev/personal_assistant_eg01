resource "google_firestore_database" "default" {
  project     = var.project_id
  name        = "personal_assistent_eg01"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
  depends_on  = [google_project_service.apis]
}

resource "google_firestore_index" "corrections_by_sender" {
  project    = var.project_id
  database   = google_firestore_database.default.name
  collection = "correction_log"
  fields {
    field_path = "sender_id"
    order      = "ASCENDING"
  }
  fields {
    field_path = "corrected_at"
    order      = "DESCENDING"
  }
}

resource "google_firestore_index" "emails_by_week_status" {
  project    = var.project_id
  database   = google_firestore_database.default.name
  collection = "emails"
  fields {
    field_path = "week_key"
    order      = "ASCENDING"
  }
  fields {
    field_path = "status"
    order      = "ASCENDING"
  }
}