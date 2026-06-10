variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Primary GCP region"
  type        = string
  default     = "europe-west1"
}

variable "your_email" {
  description = "Your Google account email"
  type        = string
}

variable "billing_account_id" {
  description = "GCP billing account ID for budget"
  type        = string
}

variable "budget_amount" {
  description = "Monthly budget USD before kill switch"
  type        = number
  default     = 20
}