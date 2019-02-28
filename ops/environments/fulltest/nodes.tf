module "masternode0" {
  source = "./modules/cilantro_ee_node"

  providers = {
    aws = "aws.us-west-2"
  }

  type  = "masternode"
  index = 0

  keyname     = "${local.keyname}"
  private_key = "${module.key.private_key}"
  docker_tag  = "${var.docker_tag}"

  create_dns       = true
  subdomain_prefix = true
  domain           = "anarchynet.io"
}

module "masternode1" {
  source = "./modules/cilantro_ee_node"

  providers = {
    aws = "aws.us-west-1"
  }

  type  = "masternode"
  index = 1

  keyname     = "${local.keyname}"
  private_key = "${module.key.private_key}"
  docker_tag  = "${var.docker_tag}"

  create_dns       = true
  subdomain_prefix = true
  domain           = "anarchynet.io"
}
