# Default
provider "aws" {
  region  = "us-west-1"
  profile = "${var.aws_profile}"
}

# Ohio
provider "aws" {
  region  = "us-east-2"
  alias   = "us-east-2"
  profile = "${var.aws_profile}"
}

# N. Virginia
provider "aws" {
  region  = "us-east-1"
  alias   = "us-east-1"
  profile = "${var.aws_profile}"
}

# N. California
provider "aws" {
  region  = "us-west-1"
  alias   = "us-west-1"
  profile = "${var.aws_profile}"
}

# Oregon
provider "aws" {
  region  = "us-west-2"
  alias   = "us-west-2"
  profile = "${var.aws_profile}"
}

# Mumbai
provider "aws" {
  region  = "ap-south-1"
  alias   = "ap-south-1"
  profile = "${var.aws_profile}"
}

# Seoul
provider "aws" {
  region  = "ap-northeast-2"
  alias   = "ap-northeast-2"
  profile = "${var.aws_profile}"
}

# Singapore
provider "aws" {
  region  = "ap-northeast-1"
  alias   = "ap-northeast-1"
  profile = "${var.aws_profile}"
}

# Sydney
provider "aws" {
  region  = "ap-southeast-1"
  alias   = "ap-southeast-1"
  profile = "${var.aws_profile}"
}

# Tokyo
provider "aws" {
  region  = "ap-southeast-2"
  alias   = "ap-southeast-2"
  profile = "${var.aws_profile}"
}

# Canada Central
provider "aws" {
  region  = "ca-central-1"
  alias   = "ca-central-1"
  profile = "${var.aws_profile}"
}

# Frankfurt
provider "aws" {
  region  = "eu-central-1"
  alias   = "eu-central-1"
  profile = "${var.aws_profile}"
}

# Ireland
provider "aws" {
  region  = "eu-west-1"
  alias   = "eu-west-1"
  profile = "${var.aws_profile}"
}

# London
provider "aws" {
  region  = "eu-west-2"
  alias   = "eu-west-2"
  profile = "${var.aws_profile}"
}

# Paris
provider "aws" {
  region  = "eu-west-3"
  alias   = "eu-west-3"
  profile = "${var.aws_profile}"
}

# Stockholm
provider "aws" {
  region  = "eu-north-1"
  alias   = "eu-north-1"
  profile = "${var.aws_profile}"
}

# Sao Paulo
provider "aws" {
  region  = "sa-east-1"
  alias   = "sa-east-1"
  profile = "${var.aws_profile}"
}
