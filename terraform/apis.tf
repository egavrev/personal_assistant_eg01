resource "google_project_service" "apis" {
  for_each = toset([
    "aiplatform.googleapis.com",      # Gemini 1.5 Flash
    "firestore.googleapis.com",       # Knowledge Graph storage
    "secretmanager.googleapis.com",   # Gmail token vault
    "gmail.googleapis.com"            # Inbox access
  ])

  service            = each.key
  disable_on_destroy = false
}