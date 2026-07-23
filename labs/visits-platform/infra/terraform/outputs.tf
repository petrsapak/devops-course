output "inventory_path" {
  description = "Generated Ansible inventory."
  value       = local_file.inventory.filename
}

output "web_urls" {
  description = "HTTP endpoints configured by the Ansible playbook."
  value = {
    for name, node in local.nodes : name => "http://127.0.0.1:${node.http_port}"
  }
}
