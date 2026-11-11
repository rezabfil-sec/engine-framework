#!/bin/bash
# {{ ansible_managed }}

# Prepare Qdisc traffic priority cgroups

# print all commands and exit immediately on failure
set -x
set -e

# NOTE: Check which cgroups version you want to run.
# For cgroups v1 as used for ubuntu 20.04 and before do not uncomment the following code
# For cgroups v2 as in Ubuntu 22.04, uncomment the following code

###### CODE FOR CGROUPS v2 - there are two lines of actual code here! ######
DIR="/sys/fs/cgroup/net_prio"
#### create the directory for v2 - breaks stuff if done for v1
if ! [[ $(findmnt -M "$DIR") ]]; then
mkdir -p /sys/fs/cgroup/net_prio

#### mount it - breaks stuff if done for v1
mount -t cgroup -o net_prio none /sys/fs/cgroup/net_prio
fi
###### END CODE FOR CGROUPS v2 ######

# create cgroups - common for v1 and v2
{% for item in net_prio_list %}
cgcreate -g net_prio:{{ item }}
{% endfor %}

# set raw interface cgroup priorities
{% for item in node_ifaces | dict2items | map(attribute="value.name") | product(net_prio_list) | list %}
echo "{{ item[0] }} {{ item[1] }}" > /sys/fs/cgroup/net_prio/{{ item[1] }}/net_prio.ifpriomap
{% endfor %}

network_config=$1
echo $network_config
if [ "$network_config" = "OvS" ]; then
# set vlan interface cgroup priorities
{% for item in node_ifaces | dict2items | map(attribute="value.name") | product(net_prio_list) | list %}
echo "v{{ item[0] }} {{ item[1] }}" > /sys/fs/cgroup/net_prio/{{ item[1] }}/net_prio.ifpriomap
{% endfor %}
fi

if [ "$network_config" = "SRIOV" ]; then
# set vlan interface cgroup priorities
{% for item in node_ifaces | dict2items | map(attribute="value.name") %}
{% set interface_name = item %}
echo "{{ loop.index }}"
{% if loop.index < num_interfaces %}
{% set sriov_value = node_ifaces[loop.index].sriov %}
echo "{{ sriov_value }}"
{% for prio in net_prio_list | list %}
{% set net_prio_value = prio %}
{% if sriov_value is true %}
{% for i in range(num_virtual_ifaces) %}
{% set vlan_interface_name = interface_name + 'v' + i|string %}
echo "{{ vlan_interface_name }} {{ net_prio_value }}" > /sys/fs/cgroup/net_prio/{{ net_prio_value }}/net_prio.ifpriomap
{% endfor %}
{% endif %}
{% endfor %}
{% endif %}
{% endfor %}
fi