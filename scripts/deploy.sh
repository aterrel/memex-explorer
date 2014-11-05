#!/usr/bin/env bash
export scriptdir=/vagrant/scripts

echo "test for" > /echo.txt # 2112 test, if this file exists on the VM then this script ran

# this only needs to be done once
sudo apt-get update

# Add your deployment scripts here:
sudo $scriptdir/debian.sh
sudo $scriptdir/conda.sh
sudo $scriptdir/supervisor.sh

mkdir -p /var/lib/image_space/uploads
chmod a+rwX -R /var/lib/image_space

ln -s /vagrant/data /data
ln -s /vagrant/UPLOADED_DATA /UPLOADED_DATA