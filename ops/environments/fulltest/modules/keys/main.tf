provider "aws" {
  alias = "us-east-2"
}

provider "aws" {
  alias = "us-east-1"
}

provider "aws" {
  alias = "us-west-1"
}

provider "aws" {
  alias = "us-west-2"
}

provider "aws" {
  alias = "ap-south-1"
}

provider "aws" {
  alias = "ap-northeast-2"
}

provider "aws" {
  alias = "ap-northeast-1"
}

provider "aws" {
  alias = "ap-southeast-1"
}

provider "aws" {
  alias = "ap-southeast-2"
}

provider "aws" {
  alias = "ca-central-1"
}

provider "aws" {
  alias = "eu-central-1"
}

provider "aws" {
  alias = "eu-west-1"
}

provider "aws" {
  alias = "eu-west-2"
}

provider "aws" {
  alias = "eu-west-3"
}

provider "aws" {
  alias = "sa-east-1"
}

variable "keyname" {
  type        = "string"
  description = "The name of the key to create"
}

# Generate a key local to a specific run of a specific environment to avoid collisions
# This is circumvented for normal use by Lamden developers by appending to authorized_keys on each node
# the public keys of all Lamden engineer's id_rsa files
resource "tls_private_key" "provisioner" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

# Create the keypairs in AWS for provisioning
resource "aws_key_pair" "us-east-2" {
  key_name   = "${var.keyname}"
  public_key = "${tls_private_key.provisioner.public_key_openssh}"
  provider   = "aws.us-east-2"
}

resource "aws_key_pair" "us-east-1" {
  key_name   = "${var.keyname}"
  public_key = "${tls_private_key.provisioner.public_key_openssh}"
  provider   = "aws.us-east-1"
}

resource "aws_key_pair" "us-west-1" {
  key_name   = "${var.keyname}"
  public_key = "${tls_private_key.provisioner.public_key_openssh}"
  provider   = "aws.us-west-1"
}

resource "aws_key_pair" "us-west-2" {
  key_name   = "${var.keyname}"
  public_key = "${tls_private_key.provisioner.public_key_openssh}"
  provider   = "aws.us-west-2"
}

resource "aws_key_pair" "ap-south-1" {
  key_name   = "${var.keyname}"
  public_key = "${tls_private_key.provisioner.public_key_openssh}"
  provider   = "aws.ap-south-1"
}

resource "aws_key_pair" "ap-northeast-2" {
  key_name   = "${var.keyname}"
  public_key = "${tls_private_key.provisioner.public_key_openssh}"
  provider   = "aws.ap-northeast-2"
}

resource "aws_key_pair" "ap-northeast-1" {
  key_name   = "${var.keyname}"
  public_key = "${tls_private_key.provisioner.public_key_openssh}"
  provider   = "aws.ap-northeast-1"
}

resource "aws_key_pair" "ap-southeast-1" {
  key_name   = "${var.keyname}"
  public_key = "${tls_private_key.provisioner.public_key_openssh}"
  provider   = "aws.ap-southeast-1"
}

resource "aws_key_pair" "ap-southeast-2" {
  key_name   = "${var.keyname}"
  public_key = "${tls_private_key.provisioner.public_key_openssh}"
  provider   = "aws.ap-southeast-2"
}

resource "aws_key_pair" "ca-central-1" {
  key_name   = "${var.keyname}"
  public_key = "${tls_private_key.provisioner.public_key_openssh}"
  provider   = "aws.ca-central-1"
}

resource "aws_key_pair" "eu-central-1" {
  key_name   = "${var.keyname}"
  public_key = "${tls_private_key.provisioner.public_key_openssh}"
  provider   = "aws.eu-central-1"
}

resource "aws_key_pair" "eu-west-1" {
  key_name   = "${var.keyname}"
  public_key = "${tls_private_key.provisioner.public_key_openssh}"
  provider   = "aws.eu-west-1"
}

resource "aws_key_pair" "eu-west-2" {
  key_name   = "${var.keyname}"
  public_key = "${tls_private_key.provisioner.public_key_openssh}"
  provider   = "aws.eu-west-2"
}

resource "aws_key_pair" "eu-west-3" {
  key_name   = "${var.keyname}"
  public_key = "${tls_private_key.provisioner.public_key_openssh}"
  provider   = "aws.eu-west-3"
}

resource "aws_key_pair" "sa-east-1" {
  key_name   = "${var.keyname}"
  public_key = "${tls_private_key.provisioner.public_key_openssh}"
  provider   = "aws.sa-east-1"
}

output "private_key" {
  value = "${tls_private_key.provisioner.private_key_pem}"
}

output "public_key" {
  value = "${tls_private_key.provisioner.public_key_openssh}"
}
