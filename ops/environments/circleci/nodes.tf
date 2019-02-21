module "masternode0" {
  source = "./modules/cilantro_node"
  providers = {
    aws = "aws.us-west-1"
  }
  type = "masternode"
  index = 0
  keyname = "${local.keyname}"
  private_key = "${module.key.private_key}"
  docker_tag  = "${var.docker_tag}"
}

output "masternode0-ssh" {
  value = "ssh ubuntu@${module.masternode0.public_ip}"
}

module "masternode1" {
  source = "./modules/cilantro_node"
  providers = {
    aws = "aws.us-west-1"
  }
  type = "masternode"
  index = 1
  keyname = "${local.keyname}"
  private_key = "${module.key.private_key}"
  docker_tag  = "${var.docker_tag}"
}

output "masternode1-ssh" {
  value = "ssh ubuntu@${module.masternode1.public_ip}"
}

module "witness0" {
  source = "./modules/cilantro_node"
  providers = {
    aws = "aws.us-west-1"
  }
  type = "witness"
  index = 0
  keyname = "${local.keyname}"
  private_key = "${module.key.private_key}"
  docker_tag  = "${var.docker_tag}"
}

output "witness0-ssh" {
  value = "ssh ubuntu@${module.witness0.public_ip}"
}

module "witness1" {
  source = "./modules/cilantro_node"
  providers = {
    aws = "aws.us-west-1"
  }
  type = "witness"
  index = 1
  keyname = "${local.keyname}"
  private_key = "${module.key.private_key}"
  docker_tag  = "${var.docker_tag}"
}

output "witness1-ssh" {
  value = "ssh ubuntu@${module.witness1.public_ip}"
}

module "delegate0" {
  source = "./modules/cilantro_node"
  providers = {
    aws = "aws.us-west-1"
  }
  type = "delegate"
  index = 0
  keyname = "${local.keyname}"
  private_key = "${module.key.private_key}"
  docker_tag  = "${var.docker_tag}"
}

output "delegate0-ssh" {
  value = "ssh ubuntu@${module.delegate0.public_ip}"
}

module "delegate1" {
  source = "./modules/cilantro_node"
  providers = {
    aws = "aws.us-west-1"
  }
  type = "delegate"
  index = 1
  keyname = "${local.keyname}"
  private_key = "${module.key.private_key}"
  docker_tag  = "${var.docker_tag}"
}

output "delegate1-ssh" {
  value = "ssh ubuntu@${module.delegate1.public_ip}"
}

