FROM ubuntu:jammy

EXPOSE 22

# setup keys
RUN mkdir -p /root/.ssh
COPY authorized_keys /root/.ssh/authorized_keys

# node setup
ENV DEBIAN_FRONTEND=noninteractive 
RUN apt-get update

# password
RUN echo 'root:password' | chpasswd

# linux and extra packages
RUN apt-get install -y \
      bison \
      flex \
      python3 \
      tcpdump \
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
      fio 

# python packages
RUN pip3 install --no-cache-dir \
      psutil \
      seaborn \
      pandas \
      pypacker \
      matplotlib \
      numpy \
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
RUN sed -i '/^#/!s/PermitRootLogin .*/PermitRootLogin yes/' /etc/ssh/sshd_config

# SSH login fix. Otherwise user is kicked off after login
RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd


CMD ["/usr/sbin/sshd","-D"]
