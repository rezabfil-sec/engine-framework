#!/bin/bash
# print all commands
# set -x
# set -e # !!!!DO NOT UNCOMMENT THIS!!!! We rely on failure here, so never automatically exit on failure. "!" also does not work in this case

POS=pos

echo "Verifying if all hosts from host_vars directory are up and available for SSH..."

err_nodes=()
good_nodes=()

for hostname in ../host_vars/*; do
    IFS='/.' read -r -a parts <<< "$hostname"
    echo -n -e "Checking \033[0;36m${parts[4]}\033[0m:\033[20G"
    ssh -o ConnectTimeout=5 ${parts[4]} "exit" > /dev/null 2>&1
    RC=$?
    if [[ $RC -eq 0 ]]; then
        echo -e "\033[0;32mOK\033[0m..."
        good_nodes+=(${parts[4]})
    else
        echo -n -e "\033[0;31mNOT OK\033[0m... Trying bootstrapping... "
        $POS allocations allocate --duration 10 ${parts[4]} > /dev/null 2>&1
        $POS nodes bootstrap ${parts[4]} --blocking > /dev/null 2>&1
        ssh -o ConnectTimeout=5 ${parts[4]} "exit" > /dev/null 2>&1
        nRC=$?
        $POS allocations free ${parts[4]} > /dev/null 2>&1
        if [[ $nRC -eq 0 ]]; then
            echo -e "Bootstrapping succeded, node \033[0;32mOK\033[0m..."
            good_nodes+=(${parts[4]})
        else
            echo -e "Bootstrapping failed, node \033[0;31mNOT OK\033[0m..."
            err_nodes+=(${parts[4]})
        fi
    fi
done

echo ""
echo "Verification finished..."
if [ ${#err_nodes[@]} -eq 0 ]; then
    echo -e "\033[0;32mAll nodes are up!\033[0m"
elif [ ${#good_nodes[@]} -eq 0 ]; then
    echo -e "\033[0;31mAll nodes failed!\033[0m"
else
    echo -e "\033[0;33mSome nodes failed!\033[0m"
fi
if [ ${#good_nodes[@]} -gt 0 ]; then
    echo -n -e "Working nodes: \033[0;32m"
    for node in "${good_nodes[@]}"
    do
        echo -n -e "$node, "
    done
    echo -e "\033[2D\033[0m\033[0K"
fi
if [ ${#err_nodes[@]} -gt 0 ]; then
    echo -n -e "Failed nodes: \033[0;31m"
    for node in "${err_nodes[@]}"
    do
        echo -n -e "$node, "
    done
    echo -e "\033[2D\033[0m\033[0K"
fi