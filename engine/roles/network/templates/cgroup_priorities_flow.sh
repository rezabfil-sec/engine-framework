#!/bin/bash
# {{ ansible_managed }}

# Set TSN traffic cgroup priorities for flow interfaces

# print all commands and exit immediately on failure
set -x
set -e

# set flow interface cgroup priorities
{% for item in flow_ifaces | map(attribute="name") | product(net_prio_list) | list %}
echo "{{ item[0] }} {{ item[1] }}" > /sys/fs/cgroup/net_prio/{{ item[1] }}/net_prio.ifpriomap
{% endfor %}
