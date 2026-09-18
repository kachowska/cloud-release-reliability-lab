output "container_registry_login_server" {
  description = "ACR login server that the delivery pipeline would target."
  value       = azurerm_container_registry.release.login_server
}

output "cluster_name" {
  description = "Configuration-only AKS cluster name."
  value       = azurerm_kubernetes_cluster.release.name
}

