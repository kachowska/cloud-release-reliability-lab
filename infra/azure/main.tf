# Configuration-only migration target. This lab does not apply Azure resources.
resource "azurerm_resource_group" "release" {
  name     = "${var.name_prefix}-rg"
  location = var.location

  tags = local.tags
}

resource "azurerm_container_registry" "release" {
  name                = replace("${var.name_prefix}acr", "-", "")
  resource_group_name = azurerm_resource_group.release.name
  location            = azurerm_resource_group.release.location
  sku                 = "Basic"
  admin_enabled       = false

  tags = local.tags
}

resource "azurerm_kubernetes_cluster" "release" {
  name                              = "${var.name_prefix}-aks"
  location                          = azurerm_resource_group.release.location
  resource_group_name               = azurerm_resource_group.release.name
  dns_prefix                        = "${var.name_prefix}-aks"
  kubernetes_version                = var.kubernetes_version
  local_account_disabled            = true
  role_based_access_control_enabled = true
  sku_tier                          = "Free"

  default_node_pool {
    name                 = "system"
    vm_size              = var.node_vm_size
    auto_scaling_enabled = true
    min_count            = 1
    max_count            = 2
    os_disk_size_gb      = 30
    type                 = "VirtualMachineScaleSets"
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin    = "azure"
    load_balancer_sku = "standard"
    outbound_type     = "loadBalancer"
  }

  tags = local.tags
}

resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.release.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.release.kubelet_identity[0].object_id
}

locals {
  tags = {
    project    = "cloud-release-reliability-lab"
    managed-by = "terraform"
    proof      = "configuration-only"
  }
}

