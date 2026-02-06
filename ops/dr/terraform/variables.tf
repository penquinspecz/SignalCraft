variable "region" {
  type    = string
  default = "us-east-1"
}

variable "name_prefix" {
  type    = string
  default = "jobintel-dr"
}

variable "vpc_id" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "instance_type" {
  type    = string
  default = "t4g.small"
}

variable "ami_id" {
  type    = string
  default = ""
}

variable "key_name" {
  type    = string
  default = ""
}

variable "allowed_cidr" {
  type    = string
  default = "10.0.0.0/8"
}
