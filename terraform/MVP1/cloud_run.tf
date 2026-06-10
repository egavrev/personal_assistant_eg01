locals {
  agent_config = {
    orchestrator = { port = 8000, memory = "512Mi" }
    ingestor     = { port = 8001, memory = "512Mi" }
    classifier   = { port = 8002, memory = "1Gi"  }
    judge        = { port = 8003, memory = "512Mi" }
    corrector    = { port = 8004, memory = "512Mi" }
  }
}

resource "google_cloud_run_v2_service" "agents" {
  for_each = local.agent_config
  name     = each.key
  location = var.region

  template {
    service_account = google_service_account.agents[each.key].email
    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/agents/${each.key}:latest"
      ports { container_port = each.value.port }
      resources {
        limits = { cpu = "1", memory = each.value.memory }
      }
      env { 
          name = "GOOGLE_CLOUD_PROJECT"   
          value = var.project_id 
          }
      env { 
        name = "ENV"                  
        value = "prod" 
        }
    }
  }
  depends_on = [google_artifact_registry_repository.agents]
}