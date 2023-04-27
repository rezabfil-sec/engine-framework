#!/bin/bash
# {{ ansible_managed }}

# Prepare TSN traffic priority cgroups

# print all commands and exit immediately on failure
set -x
set -e

# create the directory for v2 - breaks stuff if done for v1
# mkdir -p /sys/fs/cgroup/net_prio
# mount it
# create the directory for v2 - breaks stuff if done for v1
# mount -t cgroup -o net_prio none /sys/fs/cgroup/net_prio
# create cgroups
{% for item in net_prio_list %}
cgcreate -g net_prio:{{ item }}
{% endfor %}

# set raw interface cgroup priorities
{% for item in node_ifaces | dict2items | map(attribute="value.name") | product(net_prio_list) | list %}
echo "{{ item[0] }} {{ item[1] }}" > /sys/fs/cgroup/net_prio/{{ item[1] }}/net_prio.ifpriomap
{% endfor %}

# set vlan interface cgroup priorities
{% for item in node_ifaces | dict2items | map(attribute="value.name") | product(net_prio_list) | list %}
echo "v{{ item[0] }} {{ item[1] }}" > /sys/fs/cgroup/net_prio/{{ item[1] }}/net_prio.ifpriomap
{% endfor %}
