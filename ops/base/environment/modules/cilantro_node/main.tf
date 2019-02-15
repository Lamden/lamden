####################################
## Node classification parameters ##
####################################
variable "type" {
  type        = "string"
  description = "The type of node to launch, 'masternode' 'witness' 'delegate'"
}

variable "index" {
  type        = "string"
  description = "The index of the node being launched"
}

#################################
## AWS provisioning parameters ##
#################################
variable "keyname" {
  type        = "string"
  description = "The name of the key as set inside AWS"
}

variable "private_key" {
  type        = "string"
  description = "The contents of the private key to use for deployment"
}

# true/false flag
variable "create_eip" {
  type        = "string"
  description = "Boolean, whether or not to use EIPs"
  default     = false
}

# true/false flag
variable "create_dns" {
  type        = "string"
  description = "Boolean, whether or not to create DNS records"
  default     = false
}

# true/false flag
variable "subdomain_prefix" {
  type        = "string"
  description = "Flag to set whether or not to add a subdomain prefix"
  default     = true
}

variable "domain" {
  type        = "string"
  description = "The domain name to use for creating DNS records"
  default     = "none"
}

variable "size" {
  type        = "string"
  description = "The size of the node to launch"
  default     = "t2.large"
}

#######################
## Docker parameters ##
#######################
variable "docker_tag" {
  type        = "string"
  description = "The docker tag to use to launch the instance"
}

#####################
## Local Variables ##
#####################
locals {
  # All ubuntu 18.04 AMIs
  amis = {
    us-east-2      = "ami-06e2e609dbf389341"
    us-east-1      = "ami-012fd5eb46f56731f"
    us-west-1      = "ami-0bf3d63a666665438"
    us-west-2      = "ami-082fd9a18128c9e8c"
    ap-south-1     = "ami-092e1fd695ed0e93c"
    ap-northeast-2 = "ami-069c1055fab7b32e5"
    ap-northeast-1 = "ami-0f63c02167ca94956"
    ap-southeast-1 = "ami-0393b4f16793f7f12"
    ap-southeast-2 = "ami-0deda1f8bbb52aac7"
    ca-central-1   = "ami-008c2d1a8ad81bc10"
    eu-central-1   = "ami-0cf8fa6a01bb07363"
    eu-west-1      = "ami-0286372f78291e588"
    eu-west-2      = "ami-04b69fa254407c8ee"
    eu-west-3      = "ami-0e82c2554d8492095"
    sa-east-1      = "ami-05a01ab93a59b45de"
  }

  nodename = "${var.type}${var.index}"

  prefix = "${var.keyname}-"

  images = {
    full  = "lamden/cilantro_full"
    light = "lamden/cilantro_light"
  }
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

##################
## Provisioning ##
##################

# Define the security group
resource "aws_security_group" "cilantro_firewall" {
  name        = "firewall-${local.prefix}${local.nodename}"
  description = "Allow specific ports necessary for cilantro to work"

  ingress {
    from_port   = 443
    to_port     = 443
    description = "Allow HTTPS traffic through"
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    description = "Allow HTTP traffic through for cert validation"
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 8080
    to_port     = 8080
    description = "Port for Webserver if SSL is not enabled"
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    description = "Allow SSH connections to instance"
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 10000
    to_port     = 10100
    description = "Open up range of ports for inter-node communications to connect"
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    description = "Open up all ports for outbound traffic"
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Configure a cilantro node
resource "aws_instance" "cilantro-node" {
  key_name        = "${var.keyname}"
  ami             = "${local.amis["${data.aws_region.current.name}"]}"
  instance_type   = "${var.size}"
  security_groups = ["${aws_security_group.cilantro_firewall.name}"]

  tags = {
    Name = "${local.prefix}-${local.nodename}"
  }

  connection {
    type        = "ssh"
    user        = "ubuntu"
    private_key = "${var.private_key}"
  }

  # Provisioner step here will only run on creation of a new instance
  # If you would like to run code more frequently, please use a null_resource
  # with the appropriate trigger
  provisioner "remote-exec" {
    inline = [
      "sudo apt-get update",               # Update the package manager
      "sudo apt-get install -y docker.io", # Install docker
      "sudo apt-get install -y socat",     # Instal socat (for issuing SSL certificates
      "sudo usermod -aG docker ubuntu",    # Add the ubuntu user to the docker group so docker can be non-sudo
      "sudo mkdir -p /var/db/cilantro",    # Create the db directory on the host machine to mount into the container
    ]
  }

  provisioner "file" {
    source      = "../../../scripts/setup-ssl.sh"
    destination = "/home/ubuntu/setup-ssl.sh"
  }

  depends_on = ["aws_security_group.cilantro_firewall"]
}

# Conditionally create the elastic IP if requested by the user
resource "aws_eip" "static-ip" {
  count = "${var.create_eip}"

  instance = "${aws_instance.cilantro-node.id}"
}

# Look up the hosted zone for use with record
data "aws_route53_zone" "primary" {
  name = "${var.domain}"
}

resource "aws_route53_record" "fqdn" {
  # Run if statement in terraform, check if boolean provided to module is true, then set count to 1
  count = "${var.create_dns}"

  zone_id = "${data.aws_route53_zone.primary.zone_id}"
  name    = "${var.subdomain_prefix ? "${local.prefix}" : ""}${local.nodename}"
  type    = "A"
  ttl     = "60"
  records = ["${aws_instance.cilantro-node.public_ip}"]

  depends_on = ["aws_eip.static-ip"]
}

# Run the script to aggregate the ips
# This needs to always be run because since we are a module we have no knowledge of the rest of the network.
# The only way we can be sure that we correctly re-aggregate the IPs in the case of a subset of IPs being
# changed is to run it every time. The way that the validation works is checking the conf/ folder for who
# should exist in the network by their configuration files, then waiting on the files .cache/<type><index>_ip
# to contain all the IPs necessary. These files are cleared at the end of a successful apply to ensure we
# will not get any half-states on the rerun
resource "null_resource" "aggregate-ips" {
  triggers {
    always_run = "${uuid()}"
  }

  provisioner "local-exec" {
    command = "python3 aggregate_ips.py --ip ${aws_instance.cilantro-node.public_ip} --type ${var.type} --index ${var.index}"
  }

  depends_on = ["aws_eip.static-ip"]
}

# Copy over cilantro config only if it has changed locally
# Always run this endpoint to enforce that changes to the cilantro config should be done locally then pushed
# up using the devops stack. Also prevents race conditions/errors with re-aggregating IPs
resource "null_resource" "cilantro-conf" {
  triggers {
    always_run = "${uuid()}"
  }

  connection {
    type        = "ssh"
    user        = "ubuntu"
    private_key = "${var.private_key}"
    host        = "${aws_instance.cilantro-node.public_ip}"
  }

  provisioner "file" {
    source      = "./conf/${var.type}${var.index}/cilantro.conf"
    destination = "/home/ubuntu/cilantro.conf"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo mv /home/ubuntu/cilantro.conf /etc/cilantro.conf",
    ]
  }

  depends_on = ["null_resource.aggregate-ips", "aws_eip.static-ip"]
}

# Copy over circus config only if it has changed locally
resource "null_resource" "circus-conf" {
  triggers {
    conf = "${file("./conf/${var.type}${var.index}/circus.conf")}"
  }

  connection {
    type        = "ssh"
    user        = "ubuntu"
    private_key = "${var.private_key}"
    host        = "${aws_instance.cilantro-node.public_ip}"
  }

  provisioner "file" {
    source      = "./conf/${var.type}${var.index}/circus.conf"
    destination = "/home/ubuntu/circus.conf"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo mv /home/ubuntu/circus.conf /etc/circus.conf",
    ]
  }

  depends_on = ["aws_eip.static-ip"]
}

# Copy over redis.conf file
resource "null_resource" "redis-conf" {
  triggers {
    conf = "${file("./conf/${var.type}${var.index}/redis.conf")}"
  }

  connection {
    type        = "ssh"
    user        = "ubuntu"
    private_key = "${var.private_key}"
    host        = "${aws_instance.cilantro-node.public_ip}"
  }

  provisioner "file" {
    source      = "./conf/${var.type}${var.index}/redis.conf"
    destination = "/home/ubuntu/redis.conf"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo mv /home/ubuntu/redis.conf /etc/redis.conf",
    ]
  }
}

# Push up authorized keys to the nodes so all of Lamden's team can easily access them
resource "null_resource" "ssh-keys" {
  triggers {
    conf = "${file("../../security/authorized_keys")}"
  }

  connection {
    type        = "ssh"
    user        = "ubuntu"
    private_key = "${var.private_key}"
    host        = "${aws_instance.cilantro-node.public_ip}"
  }

  # Copy up our public keys to the nodes, leave existing file to keep existing keys
  provisioner "file" {
    source      = "../../security/authorized_keys"
    destination = "/home/ubuntu/.ssh/authorized_keys.loc"
  }

  # Copy up authorized_keys to unique file, append into system authorized_keys, merge & deduplicate, move resulting file to system authorized_keys 
  provisioner "remote-exec" {
    inline = [
      "cat /home/ubuntu/.ssh/authorized_keys.loc >> /home/ubuntu/.ssh/authorized_keys",
      "sort /home/ubuntu/.ssh/authorized_keys | uniq > /home/ubuntu/.ssh/authorized_keys.loc",
      "mv /home/ubuntu/.ssh/authorized_keys.loc /home/ubuntu/.ssh/authorized_keys",
    ]
  }

  depends_on = ["aws_eip.static-ip"]
}

# Swap out docker containers only if a new tag or image has been provided
resource "null_resource" "docker" {
  triggers {
    tag      = "${var.docker_tag}"
    image    = "${var.type}"
    circus   = "${file("./conf/${var.type}${var.index}/circus.conf")}"
    cilantro = "${file("./conf/${var.type}${var.index}/cilantro.conf")}"
  }

  connection {
    type        = "ssh"
    user        = "ubuntu"
    private_key = "${var.private_key}"
    host        = "${aws_instance.cilantro-node.public_ip}"
  }

  # 1) Kill the 'cil' container
  # 2) Launch the new container
  provisioner "remote-exec" {
    inline = [
      "sudo docker rm -f cil",
      "sudo docker run --name cil -dit -v /var/db/cilantro/:/var/db/cilantro -v /etc/cilantro.conf:/etc/cilantro.conf -v /etc/redis.conf:/etc/redis.conf -v /etc/circus.conf:/etc/circus.conf -p 8080:8080 -p 443:443 -p 10000-10100:10000-10100 ${var.type == "masternode" ? "${local.images["full"]}" : "${local.images["light"]}"}:${var.docker_tag}",
    ]
  }

  depends_on = ["null_resource.cilantro-conf", "null_resource.circus-conf", "null_resource.aggregate-ips", "aws_eip.static-ip"]
}

output "public_ip" {
  value = "${aws_instance.cilantro-node.public_ip}"
}
