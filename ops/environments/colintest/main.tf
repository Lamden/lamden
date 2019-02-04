# Terraform configuration file for cilantro environment

# The profile to use for launching the nodes. Leaving this as "default"
# will work fine for most local AWS setups
variable "aws_profile" {
  type    = "string"
  default = "default"
}

variable "ssh_folder" {
  type    = "string"
  default = "${pathexpand(~/.ssh)}"
}

# The git branch
variable "git_branch" {
  type = "string"
}

# The docker tag to execute the run with
variable "docker_tag" {
  type = "string"
}

# The public key of the keypair to use
variable "public_key" {
  type = "string"
}

# The remote name of the keypair to use for AWS reproduction and storage
variable "key_name" {
  type = "string"
}

# Specify local (static) variables
locals {
  # List of all AWS regions, to use in an aws_instance resource, set the first line of
  # the resource as follows:
  #
  #   resource "aws_instance" "masternode0" {
  #     provider = "aws.us-west-1"
  #     ...
  #   }
  #
  aws_regions = [
    "us-east-2",      # Ohio
    "us-east-1",      # N. Virginia
    "us-west-1",      # N. California
    "us-west-2",      # Oregon
    "ap-south-1",     # Mumbai
    "ap-northeast-3", # Osaka-Local
    "ap-northeast-2", # Seoul
    "ap-northeast-1", # Singapore
    "ap-southeast-1", # Sydney
    "ap-southeast-2", # Tokyo
    "ca-central-1",   # Canada Central
    "cn-north-1",     # Beijing (China)
    "cn-northwest-1", # Ningxia (China)
    "eu-central-1",   # Frankfurt
    "eu-west-1",      # Ireland
    "eu-west-2",      # London
    "eu-west-3",      # Paris
    "eu-north-1",     # Stockholm
    "sa-east-1",      # Sao Paulo
    "us-gov-east-1",  # GovCloud N. Virginia
    "us-gov-west-1",  # GovCloud N. California
  ]

  images = {
    masternode = "lamden/cilantro_mn"
    base       = "lamden/cilantro"
  }
}

# Generate providers for every AWS region, allowing for a easy-to-understand way of 
# moving nodes to different regions
provider "aws" {
  count   = "${length(local.aws_regions)}"
  region  = "${element(local.aws_regions, count.index)}"
  alias   = "${element(local.aws_regions, count.index)}"
  profile = "${var.aws_profile}"
}

# Define the keypair so it can be uploaded to AWS if not exists in AWS
resource "aws_key_pair" "deployer" {
  key_name   = "${var.key_name}"
  public_key = "${file("${var.ssh_folder}/id_rsa.pub")}"
}

# Import the security.tf module containing security groups/information
resource "aws_security_group" "cilantro_firewall" {
  name        = "cilantro_firewall"
  description = "Allow specific ports necessary for cilantro to work"

  ingress {
    from_port   = 443
    to_port     = 443
    description = "Allow HTTPS traffic through"
    protocol    = "-1"
    cidr_blocks = "0.0.0.0/0"
  }

  ingress {
    from_port   = 80
    to_port     = 80
    description = "Allow HTTP traffic through for cert validation"
    protocol    = "-1"
    cidr_blocks = "0.0.0.0/0"
  }

  ingress {
    from_port   = 8080
    to_port     = 8080
    description = "Port for Webserver if SSL is not enabled"
    protocol    = "-1"
    cidr_blocks = "0.0.0.0/0"
  }

  ingress {
    from_port   = 22
    to_port     = 22
    description = "Allow SSH connections to instance"
    protocol    = "-1"
    cidr_blocks = "0.0.0.0/0"
  }

  ingress {
    from_port   = 10000
    to_port     = 10100
    description = "Open up range of ports for IPC sockets to connect"
    protocol    = "-1"
    cidr_blocks = "0.0.0.0/0"
  }
}

#################
## MASTERNODES ##
#################

## masternode0 ##
resource "aws_instance" "masternode0" {
  key_name        = "${aws_key_pair.deployer.key_name}"
  ami             = "ami-0bf3d63a666665438"
  instance_type   = "t2.large"
  name_prefix     = "masternode0-${var.git_branch}-"
  security_groups = ["${aws_security_group.cilantro_firewall.name}"]

  provisioner "local-exec" {
    command = "python3 gather_ips.py"
  }
}

resource "null_resource" "masternode0-configuration" {
  triggers {
    circus_conf   = "${file("${path.module}/conf/masternode0/circus.conf")}"
    cilantro_conf = "${file("${path.module}/conf/masternode0/cilantro.conf")}"
    tag_name      = "${var.docker_tag}"
  }

  connection {
    type        = "ssh"
    user        = "ec2-user"
    private_key = "${file("${var.ssh_folder}/id_rsa")}"
    host        = "${aws_instance.masternode0.public_ip}"
  }

  provisioner "local-exec" {}

  provisioner "file" {
    source      = "./conf/masternode0/cilantro.conf"
    destination = "/etc/cilantro.conf"
  }

  provisioner "file" {
    source      = "./conf/masternode0/circus.conf"
    destination = "/etc/circus.conf"
  }

  provisioner "remote-exec" {
    inline = [
      "docker rm -f masternode0",
    ]
  }

  provisioner "remote-exec" {
    inline = [
      "docker run -dit --name masternode0 -v /etc/cilantro.conf:/etc/cilantro.conf -v /etc/circus.conf:/etc/circus.conf -p 443:443 -p 80:80 -p 10000-10100:10000-10100 ${local.images[masternode]}:${var.docker_tag}",
    ]
  }

  depends_on = ["aws_instance.masternode0"]
}

output "masternode0_ssh" {
  value = "ssh ec2-user@${aws_instance.masternode0.public_ip}"
}
