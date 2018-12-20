#!/bin/bash

set -x

if [ -z "$SSL_ENABLED" ]
then
    echo "SSL not enabled, not generating cert"
    exit 0
fi

if ! $SSL_ENABLED
then
    echo "SSL not enabled, not generating cert"
    exit 0
fi

# cd into directory of script to be run-location agnostic
cd "$(dirname "$0")"

# Get the acme.sh script to install/setup certs only if not already cloned in
if [ ! -d "$PWD/acme.sh" ]
then
        git clone https://github.com/Neilpang/acme.sh.git
fi

# Get latest code for acme.sh
cd acme.sh
git pull origin master

# Run install script
./acme.sh --install

# Check if HOST_NAME env is set. If unset we cannot continue
if [ -z "$HOST_NAME" ]
then
	echo "ERROR: environment variable HOST_NAME not set, cannot generate FQDN for cert, aborting"
	exit 1
fi

if [ -z "$DNS_NAME" ]
then
	echo "ERROR: environment variable DNS_NAME not set, cannot generate FQDN for cert, aborting"
    exit 1
fi


# Resolve FQDN
# Cut off first bit before _ to get the type
NODETYPE=$(echo $HOST_NAME | cut -d'_' -f 1)
# Cut off the last bit after the last underscore for the index (calling rev twice solves this in bash)
NODEINDEX=$(echo $HOST_NAME | rev | cut -d'_' -f 1 | rev)

# Concatenate into FQDN
FQDN="$NODETYPE$NODEINDEX.$DNS_NAME"

# Generate the certificate
~/.acme.sh/acme.sh --issue --standalone -d $FQDN

# Reconfigure the certificate authority to include the new cert
cp ~/.acme.sh/$FQDN/ca.cer /usr/share/ca-certificates/ca.crt
grep -q -F 'ca.crt' /etc/ca-certificates.conf || echo 'ca.crt' >> /etc/ca-certificates.conf
update-ca-certificates

echo "{ \"cert\": \"/home/${USER}/.acme.sh/$FQDN/$FQDN.cer\", \"key\": \"/home/$USER/.acme.sh/$FQDN/$FQDN.key\" }" > ~/.sslconf
