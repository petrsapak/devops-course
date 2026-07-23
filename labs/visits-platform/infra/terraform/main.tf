provider "docker" {}

locals {
  nodes = {
    node1 = {
      address   = "172.28.0.11"
      http_port = 8081
      ssh_port  = 2221
    }
    node2 = {
      address   = "172.28.0.12"
      http_port = 8082
      ssh_port  = 2222
    }
    node3 = {
      address   = "172.28.0.13"
      http_port = 8083
      ssh_port  = 2223
    }
  }
}

resource "tls_private_key" "course" {
  algorithm = "ED25519"
}

resource "local_sensitive_file" "private_key" {
  filename        = "${path.module}/.keys/id_ed25519"
  content         = tls_private_key.course.private_key_openssh
  file_permission = "0600"
}

resource "docker_network" "ansible_lab" {
  name = "ansiblelab"

  ipam_config {
    subnet = "172.28.0.0/24"
  }
}

resource "docker_image" "labnode" {
  name = "devops-course-labnode:latest"

  build {
    context = "${path.module}/../ansible/labnode"
    build_args = {
      LAB_PUBLIC_KEY = tls_private_key.course.public_key_openssh
    }
  }
}

resource "docker_container" "node" {
  for_each = local.nodes

  name  = each.key
  image = docker_image.labnode.image_id

  networks_advanced {
    name         = docker_network.ansible_lab.name
    ipv4_address = each.value.address
  }

  ports {
    internal = 22
    external = each.value.ssh_port
    ip       = "127.0.0.1"
  }

  ports {
    internal = 80
    external = each.value.http_port
    ip       = "127.0.0.1"
  }
}

resource "local_file" "inventory" {
  filename = "${path.module}/inventory.ini"
  content = templatefile("${path.module}/inventory.tftpl", {
    nodes            = local.nodes
    private_key_path = abspath(local_sensitive_file.private_key.filename)
  })
}
