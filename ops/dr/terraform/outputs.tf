output "instance_id" {
  value = aws_instance.dr_runner.id
}

output "public_ip" {
  value = aws_instance.dr_runner.public_ip
}

output "private_ip" {
  value = aws_instance.dr_runner.private_ip
}

output "ssh_command" {
  value = var.key_name != "" ? "ssh -i <path-to-key> ubuntu@${aws_instance.dr_runner.public_ip}" : "ssh ubuntu@${aws_instance.dr_runner.public_ip}"
}

output "kubeconfig_hint" {
  value = "scp ubuntu@${aws_instance.dr_runner.public_ip}:/etc/rancher/k3s/k3s.yaml ./k3s-dr.yaml"
}
