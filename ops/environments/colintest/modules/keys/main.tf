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

# Create the keypair in AWS for provisioning
resource "aws_key_pair" "deployer" {
  key_name   = "${var.keyname}"
  public_key = "${tls_private_key.provisioner.public_key_openssh}"
}

output "private_key" {
  value = "${tls_private_key.provisioner.private_key_openssh}"
}

output "public_key" {
  value = "${tls_private_key.provisioner.public_key_openssh}"
}
