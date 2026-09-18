locals {
  labels = {
    "app.kubernetes.io/name"       = var.name
    "app.kubernetes.io/component"  = "release-status-api"
    "app.kubernetes.io/managed-by" = "terraform"
  }
}

resource "kubernetes_config_map_v1" "release" {
  metadata {
    name      = "${var.name}-release"
    namespace = var.namespace
    labels    = local.labels
  }

  data = {
    RELEASE_SERVICE_NAME = var.name
    RELEASE_VERSION      = var.release_version
    RELEASE_COMMIT_SHA   = var.commit_sha
    RELEASE_ENVIRONMENT  = var.environment
  }
}

resource "kubernetes_deployment_v1" "release" {
  metadata {
    name      = var.name
    namespace = var.namespace
    labels    = local.labels
  }

  spec {
    replicas               = var.replicas
    revision_history_limit = 3
    min_ready_seconds      = 2

    strategy {
      type = "RollingUpdate"
      rolling_update {
        max_surge       = "1"
        max_unavailable = "0"
      }
    }

    selector {
      match_labels = {
        "app.kubernetes.io/name" = var.name
      }
    }

    template {
      metadata {
        labels = merge(local.labels, {
          "lab.release/version" = replace(lower(var.release_version), "/[^a-z0-9.-]/", "-")
        })
        annotations = {
          "lab.release/commit-sha" = var.commit_sha
        }
      }

      spec {
        automount_service_account_token  = false
        termination_grace_period_seconds = 15

        security_context {
          run_as_non_root = true
          run_as_user     = 10001
          run_as_group    = 10001
          fs_group        = 10001

          seccomp_profile {
            type = "RuntimeDefault"
          }
        }

        container {
          name              = "release-service"
          image             = var.image
          image_pull_policy = var.image_pull_policy

          port {
            name           = "http"
            container_port = 8080
            protocol       = "TCP"
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map_v1.release.metadata[0].name
            }
          }

          env {
            name  = "RELEASE_FORCE_NOT_READY"
            value = tostring(var.force_not_ready)
          }

          readiness_probe {
            http_get {
              path = "/health/ready"
              port = "http"
            }
            initial_delay_seconds = 2
            period_seconds        = 2
            timeout_seconds       = 1
            failure_threshold     = 3
            success_threshold     = 1
          }

          liveness_probe {
            http_get {
              path = "/health/live"
              port = "http"
            }
            initial_delay_seconds = 5
            period_seconds        = 5
            timeout_seconds       = 1
            failure_threshold     = 3
          }

          resources {
            requests = {
              cpu    = "50m"
              memory = "64Mi"
            }
            limits = {
              cpu    = "250m"
              memory = "128Mi"
            }
          }

          security_context {
            allow_privilege_escalation = false
            privileged                 = false
            read_only_root_filesystem  = true
            run_as_non_root            = true

            capabilities {
              drop = ["ALL"]
            }
          }

          volume_mount {
            name       = "tmp"
            mount_path = "/tmp"
          }
        }

        volume {
          name = "tmp"
          empty_dir {
            medium     = "Memory"
            size_limit = "16Mi"
          }
        }
      }
    }
  }

  wait_for_rollout = true

  timeouts {
    create = "3m"
    update = "3m"
  }
}

resource "kubernetes_service_v1" "release" {
  metadata {
    name      = var.name
    namespace = var.namespace
    labels    = local.labels
  }

  spec {
    selector = {
      "app.kubernetes.io/name" = var.name
    }

    port {
      name        = "http"
      port        = 80
      target_port = "http"
      protocol    = "TCP"
    }

    type = "ClusterIP"
  }
}

