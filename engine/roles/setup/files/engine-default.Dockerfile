FROM ubuntu:jammy

EXPOSE 22

# setup keys
RUN mkdir -p /root/.ssh
COPY authorized_keys /root/.ssh/authorized_keys

# node setup
ENV DEBIAN_FRONTEND=noninteractive 
RUN apt update

# linux and extra packages
RUN apt install -y \
      bison \
      flex \
      iproute2 \
      libcmocka-dev \
      pkg-config \
      cgroup-tools \
      python3-pip \
      scapy \
      gnuplot \
      libtool \
      autoconf \
      libsodium-dev \
      libb2-dev \
      tshark \
      rsync \
      software-properties-common \
      curl \
      expect \
      libpixman-1-dev \
      libfdt-dev \
      openssh-server \
      inetutils-ping \
      bc \
      golang \
      fio \
      nftables \
      vim \
      chrony

# python packages
RUN pip3 install --no-cache-dir \
      psutil \
      seaborn \
      pandas==1.3.5 \
      pypacker \
      matplotlib==3.5.3 \
      numpy==1.24.3 \
      netifaces \
      python-ndn \
      web3 \
      eth-keys \
      pyyaml

# cleanup
RUN apt-get clean

# sshd setup
RUN mkdir /var/run/sshd
RUN sed -i 's/#UseDNS no/UseDNS no/' /etc/ssh/sshd_config
CMD ["/usr/sbin/sshd","-D"]
