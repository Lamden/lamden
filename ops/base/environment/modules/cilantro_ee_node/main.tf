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

variable "production" {
  type        = "string"
  description = "Whether or not the node is a production node"
  default     = false
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

variable "setup_ssl" {
  type        = "string"
  description = "Run the SSL setup script"
  default     = false
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
  nodename = "${var.type}${var.index}"

  prefix = "${var.keyname}-"

  images = {
    full  = "lamden/cilantro_ee_full"
    light = "lamden/cilantro_ee_light"
  }
}

##########
## DATA ##
##########

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

data "aws_ami" "cilantrobase" {
  owners      = ["self"]
  most_recent = true

  filter {
    name   = "name"
    values = ["cilantrobase-*"]
  }
}

##################
## Provisioning ##
##################

# Define the security group
resource "aws_security_group" "cilantro_ee_firewall" {
  name        = "firewall-${local.prefix}${local.nodename}"
  description = "Allow specific ports necessary for cilantro_ee to work"

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

# Configure a cilantro_ee node
resource "aws_instance" "cilantro_ee-node" {
  key_name        = "${var.keyname}"
  ami             = "${data.aws_ami.cilantrobase.id}"
  instance_type   = "${var.size}"
  security_groups = ["${aws_security_group.cilantro_ee_firewall.name}"]

  tags = {
    Name       = "${local.prefix}-${local.nodename}"
    Touch      = "${timestamp()}"
    Production = "${var.production ? "True" : "False"}"
  }

  connection {
    type        = "ssh"
    user        = "ubuntu"
    private_key = "${var.private_key}"
  }

  provisioner "file" {
    source      = "../../../scripts/setup-ssl.sh"
    destination = "/home/ubuntu/setup-ssl.sh"
  }

  depends_on = ["aws_security_group.cilantro_ee_firewall"]
}

# Conditionally create the elastic IP if requested by the user
resource "aws_eip" "static-ip" {
  count = "${var.create_eip}"

  instance = "${aws_instance.cilantro_ee-node.id}"
}

# Look up the hosted zone for use with record
data "aws_route53_zone" "primary" {
  count = "${var.create_dns}"

  name = "${var.domain}"
}

resource "aws_route53_record" "fqdn" {
  # Run if statement in terraform, check if boolean provided to module is true, then set count to 1
  count = "${var.create_dns}"

  zone_id = "${data.aws_route53_zone.primary.zone_id}"
  name    = "${var.subdomain_prefix ? "${local.prefix}" : ""}${local.nodename}"
  type    = "A"
  ttl     = "60"
  records = ["${aws_instance.cilantro_ee-node.public_ip}"]

  depends_on = ["aws_eip.static-ip", "aws_instance.cilantro_ee-node"]
}

# Setup the SSL resource
resource "null_resource" "setup-ssl" {
  count = "${var.setup_ssl}"

  triggers {
    type   = "${var.type}"
    index  = "${var.index}"
    ip     = "${aws_instance.cilantro_ee-node.public_ip}"
    record = "${aws_route53_record.fqdn.fqdn}"
  }

  connection {
    type        = "ssh"
    user        = "ubuntu"
    private_key = "${var.private_key}"
    host        = "${aws_instance.cilantro_ee-node.public_ip}"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo SSL_ENABLED=True DNS_NAME=${var.domain} HOST_NAME=${var.type}_${var.index} bash /home/ubuntu/setup-ssl.sh",
    ]
  }

  depends_on = ["aws_route53_record.fqdn"]
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
    command = "python3 aggregate_ips.py --ip ${aws_instance.cilantro_ee-node.public_ip} --type ${var.type} --index ${var.index}"
  }

  depends_on = ["aws_eip.static-ip"]
}

# Copy over cilantro_ee config only if it has changed locally
# Always run this endpoint to enforce that changes to the cilantro_ee config should be done locally then pushed
# up using the devops stack. Also prevents race conditions/errors with re-aggregating IPs
resource "null_resource" "cilantro_ee-conf" {
  triggers {
    always_run = "${uuid()}"
  }

  connection {
    type        = "ssh"
    user        = "ubuntu"
    private_key = "${var.private_key}"
    host        = "${aws_instance.cilantro_ee-node.public_ip}"
  }

  provisioner "file" {
    source      = "./conf/${var.type}${var.index}/cilantro_ee.conf"
    destination = "/home/ubuntu/cilantro_ee.conf"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo rm -rf /etc/cilantro_ee.conf",
      "sudo mv /home/ubuntu/cilantro_ee.conf /etc/cilantro_ee.conf",
    ]
  }

  depends_on = ["null_resource.aggregate-ips", "aws_eip.static-ip"]
}

resource "null_resource" "vk_ip_map-json" {
  triggers {
    always_run = "${uuid()}"
  }

  connection {
    type        = "ssh"
    user        = "ubuntu"
    private_key = "${var.private_key}"
    host        = "${aws_instance.cilantro_ee-node.public_ip}"
  }

  provisioner "file" {
    source      = "./conf/${var.type}${var.index}/vk_ip_map.json"
    destination = "/home/ubuntu/vk_ip_map.json"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo rm -rf /etc/vk_ip_map.json",
      "sudo mv /home/ubuntu/vk_ip_map.json /etc/vk_ip_map.json",
    ]
  }

  depends_on = ["null_resource.aggregate-ips", "aws_eip.static-ip"]
}

# Copy over circus config only if it has changed locally
resource "null_resource" "circus-conf" {
  triggers {
    conf     = "${file("./conf/${var.type}${var.index}/circus.conf")}"
    instance = "${aws_instance.cilantro_ee-node.public_ip}"
  }

  connection {
    type        = "ssh"
    user        = "ubuntu"
    private_key = "${var.private_key}"
    host        = "${aws_instance.cilantro_ee-node.public_ip}"
  }

  provisioner "file" {
    source      = "./conf/${var.type}${var.index}/circus.conf"
    destination = "/home/ubuntu/circus.conf"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo rm -rf /etc/circus.conf",
      "sudo mv /home/ubuntu/circus.conf /etc/circus.conf",
    ]
  }

  depends_on = ["aws_eip.static-ip"]
}

# Copy over redis.conf file
resource "null_resource" "redis-conf" {
  triggers {
    instance = "${aws_instance.cilantro_ee-node.public_ip}"
    conf     = "${file("./conf/${var.type}${var.index}/redis.conf")}"
  }

  connection {
    type        = "ssh"
    user        = "ubuntu"
    private_key = "${var.private_key}"
    host        = "${aws_instance.cilantro_ee-node.public_ip}"
  }

  provisioner "file" {
    source      = "./conf/${var.type}${var.index}/redis.conf"
    destination = "/home/ubuntu/redis.conf"
  }

  provisioner "remote-exec" {
    inline = [
      "sudo rm -rf /etc/redis.conf",
      "sudo mv /home/ubuntu/redis.conf /etc/redis.conf",
    ]
  }
}

# Push up authorized keys to the nodes so all of Lamden's team can easily access them
resource "null_resource" "ssh-keys" {
  triggers {
    instance = "${aws_instance.cilantro_ee-node.public_ip}"
    conf     = "${file("../../security/authorized_keys")}"
  }

  connection {
    type        = "ssh"
    user        = "ubuntu"
    private_key = "${var.private_key}"
    host        = "${aws_instance.cilantro_ee-node.public_ip}"
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
    tag         = "${var.docker_tag}"
    image       = "${var.type}"
    circus      = "${file("./conf/${var.type}${var.index}/circus.conf")}"
    cilantro_ee = "${file("./conf/${var.type}${var.index}/cilantro_ee.conf")}"
  }

  connection {
    type        = "ssh"
    user        = "ubuntu"
    private_key = "${var.private_key}"
    host        = "${aws_instance.cilantro_ee-node.public_ip}"
  }

  # 1) Kill the 'cil' container
  # 2) Launch the new container
  provisioner "remote-exec" {
    inline = [
      "sudo docker rm -f cil",
      "sleep 5",
      "sudo docker run --name cil -dit -v /usr/local/db/cilantro_ee/:/usr/local/db/cilantro_ee -v /etc/vk_ip_map.json:/etc/vk_ip_map.json -v /etc/cilantro_ee.conf:/etc/cilantro_ee.conf -v /etc/redis.conf:/etc/redis.conf -v /etc/circus.conf:/etc/circus.conf ${var.setup_ssl ? "-v /home/ubuntu/.sslconf:/root/.sslconf -v /home/ubuntu/.acme.sh:/home/root/.acme.sh" : ""} -p 8080:8080 -p 443:443 -p 10000-10100:10000-10100 ${var.type == "masternode" ? "${local.images["full"]}" : "${local.images["light"]}"}:${var.docker_tag}",
    ]
  }

  depends_on = ["null_resource.cilantro_ee-conf", "null_resource.circus-conf", "null_resource.aggregate-ips", "aws_eip.static-ip"]
}

output "public_ip" {
  value = "${aws_instance.cilantro_ee-node.public_ip}"
}
