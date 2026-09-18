output "namespace" {
  description = "Managed namespace."
  value       = kubernetes_namespace_v1.release.metadata[0].name
}

output "deployment_name" {
  description = "Application Deployment name."
  value       = module.release_service.deployment_name
}

output "service_name" {
  description = "ClusterIP Service name."
  value       = module.release_service.service_name
}

output "port_forward_command" {
  description = "Command for a local smoke-test tunnel."
  value       = "kubectl -n ${var.namespace} port-forward service/${module.release_service.service_name} 8080:80"
}

