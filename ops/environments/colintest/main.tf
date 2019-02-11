###############
## Variables ##
###############
variable "environment_name" {
  type        = "string"
  description = "The name of the environment"
}

variable "user" {
  type        = "string"
  description = "The $USER"
}

locals {
  keyname = "${var.environment_name}-${var.user}"
}

##################
## Provisioning ##
##################
#module "providers" {
#  source      = "./modules/providers"
#  aws_profile = "${var.aws_profile}"
#}

module "key" {
  source = "./modules/keys"

  providers = {
    aws = "aws.us-west-2"
  }

  keyname = "${local.keyname}"
}

module "shared_resources" {
  source = "./modules/shared"

  providers = {
    aws = "aws.us-west-2"
  }

  keyname = "${local.keyname}"
}

module "masternode0" {
  source = "./modules/cilantro_node"

  providers = {
    aws = "aws.us-west-2"
  }

  type  = "masternode"
  index = 0

  region         = "us-west-2"
  keyname        = "${local.keyname}"
  private_key    = "${module.key.private_key}"
  security_group = "${module.shared_resources.security_group_name}"
  docker_tag     = "devops-c062779e-9f813860"
}
