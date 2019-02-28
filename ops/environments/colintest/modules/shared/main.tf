variable "keyname" {
  type        = "string"
  description = "The keyname to use as a unique identifier naming prefix"
}

locals {
  name = "${var.keyname}-cilantro_ee-firewall"
}

# Define the security group
resource "aws_security_group" "cilantro_ee_firewall" {
  name        = "${local.name}"
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
    description = "Open up range of ports for IPC sockets to connect"
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

output "security_group_name" {
  value = "${local.name}"
}
