output "deployment_name" {
  value = kubernetes_deployment_v1.release.metadata[0].name
}

output "service_name" {
  value = kubernetes_service_v1.release.metadata[0].name
}

