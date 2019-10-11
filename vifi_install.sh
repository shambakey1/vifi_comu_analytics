#!/bin/bash

### All commands assume sudo previliges ###

# As a precaution, upgrade and update
sudo apt update
sudo apt upgrade -y

# Install zip, unzip, JAVA 8 because newer JAVA produce problems with current NiFi
sudo apt install zip unzip openjdk-8-jdk iptables-persistent -y
sudo sh -c "echo 'JAVA_HOME="/usr/lib/jvm/java-1.8.0-openjdk-amd64"' >> /etc/environment"
. /etc/environment

# Python 3 is needed. We will install python and pip through conda. Additional libraries will be installed (e.g., pyyaml, nipyapi, docker) using conda and/or pip
conda_root='/org/conda'
conda_src='Miniconda3-latest-Linux-x86_64.sh'
conda_link='https://repo.anaconda.com/miniconda/'$conda_src

sudo mkdir -m 777 -p $conda_root
cd $conda_root
wget $conda_link
sudo bash $conda_src	# Follow the instructions. Install conda to $conda_root/installed and you may need to add the "bin" and "condabin" folders to path, so that all other users will find them
sudo chmod -R 777 $conda_root/installed	# Assuming conda has been installed under the "installed" directory
pip install pyyaml nipyapi docker paramiko pandas
#sudo reboot

# Install NiFi
nifi_root='/org/nifi'
nifi_ver='1.9.2'
nifi='nifi-'$nifi_ver
nifi_src=$nifi'-bin.zip'
nifi_download_path='http://mirror.cogentco.com/pub/apache/nifi/1.9.2/'$nifi_src
sudo mkdir -m 777 -p $nifi_root
cd $nifi_root
wget $nifi_download_path
unzip $nifi_src
sudo $nifi/bin/nifi.sh install	# To install nifi as a service
# You may need to adjust the web http host in the nifi.proprties file
# Make sure port 8080 is open and free. Otherwise, open it for NiFi. If you are going to use another port for NiFi (e.g., 8090), then open that other port (e.g., 8090) as follows:
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 9443 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 21 -j ACCEPT
sudo iptables-save > rules.dat
sudo mv rules.dat /etc/iptables/rules.v4
sudo ip6tables-save > rules.dat
sudo mv rules.dat /etc/iptables/rules.v6
# The ports may need to be opened also with ufw. So, just in case
#sudo ufw allow 80
#sudo ufw allow 8080
#sudo ufw allow 9443
#sudo ufw allow 21
#sudo ufw enable
# HERE: THE MACHINE MAY NEED TO REBOOT.

####### INSTALL DOCKER ON ALL NODES ###########
#To Be Writtein

# Now, install docker swarm
docker swarm init	# Run on manager
docker swarm join --token <tokn from previous command>	# Run on worker

######## INSTALL NFS SERVER TO SHARE DATA BETWEEN VIFI NODES #############
# Currently, we install NFS Server on Docker swarm manager
sudo apt install nfs-kernel-server
sudo mkdir -m 777 /data	# Add the required data directories to be shared among the all nodes of the docker swarm. All future data directories will be added to this directory, so there will be no need to add the new shares in the exports file
sudo chown nobody:nogroup /data
sudo mkdir -m 777 /requests	# Add the required requests directories to be shared among the all nodes of the docker swarm. All future requests directories will be added to this directory, so there will be no need to add the new shares in the exports file
sudo chown nobody:nogroup /requests
sudo sh -c "echo '/data *(rw,sync,no_root_squash,no_subtree_check)' >> /etc/exports"
sudo sh -c "echo '/requests *(rw,sync,no_root_squash,no_subtree_check)' >> /etc/exports"
sudo service nfs-kernel-server restart

######## INSTALL NFS USER ON OTHER NON-NFS SERVER NODES TO ACCESS SHARED DATA #############
# Currently, NFS User is installed on Docer swarm workers
sudo apt install nfs-common
sudo mkdir -m 777 /data
sudo mkdir -m 777 /requests
sudo sh -c "echo '<NFS Server node>:/data       /data      nfs auto,nofail,noatime,nolock,intr,tcp,actimeo=1800 0 0' >> /etc/fstab"
sudo sh -c "echo '<NFS Server node>:/requests       /requests      nfs auto,nofail,noatime,nolock,intr,tcp,actimeo=1800 0 0' >> /etc/fstab"
sudo mount -a
# Make sure each worker has access the shared /data and /requests folder on the swarm manager

######## DOWNLOAD VIFI SERVER #########
vifi_src="https://melshamb@bitbucket.org/vifi-uncc/vifi_comu_analytics.git"
vifi="/vifi"
sudo git clone $vifi_src $vifi
sudo chmod -R 777 $vifi			# To simplify VIFI management in current development phase
sudo chown -R nobody:nogroup $vifi	

######## NOTE: TO RUN THE VIFI SERVER FOR A SPECIFI SET ###########
python vifi.py --sets JPL_cordex --vifi_conf ./vifi_config.yml &> err.log
