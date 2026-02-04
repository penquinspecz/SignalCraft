output "cluster_name" {
  value = aws_eks_cluster.this.name
}

output "region" {
  value = var.region
}

output "oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.this.arn
}

output "jobintel_irsa_role_arn" {
  value = aws_iam_role.jobintel_irsa.arn
}

output "serviceaccount_annotation" {
  value = "eks.amazonaws.com/role-arn=${aws_iam_role.jobintel_irsa.arn}"
}

output "update_kubeconfig_command" {
  value = "aws eks update-kubeconfig --region ${var.region} --name ${aws_eks_cluster.this.name}"
}
