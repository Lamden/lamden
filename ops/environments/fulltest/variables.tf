###############
## Variables ##
###############
variable "docker_tag" {
  type        = "string"
  description = "The docker tag to use. NOTE: If you are attempting to run this through 'terraform apply' please consider using 'make run' instead. Unless you know what you're doing..."
}

variable "environment_name" {
  type        = "string"
  description = "The name of the environment"
}

variable "user" {
  type        = "string"
  description = "The $USER"
}

variable "aws_profile" {
  type    = "string"
  default = "default"
}

locals {
  keyname = "${var.environment_name}-${var.user}"
}
