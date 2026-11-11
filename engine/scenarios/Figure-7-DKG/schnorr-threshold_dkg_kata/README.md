# tss-frost
Scenario that defines and executes experiments with the schnorr-frost service.
Check roles/services/schnorr-frost for more details.

## Content
- scenario-single.py - script for processing the results (plotting graphs)

## Setting up Interfaces
There was a problem with running the schnorr-frost service on three nodes. 
At a random point in the scenario execution, a participant from one physical node
would send a message to a participant on another physical node, but the message would
arrive incomplete (eg. 21kB instead of 30kB would be delivered).
Since all messages are ciphertexts, the decryption would fail.

The application (schnorr-frost) service was thoroughly analyzed and debugged,
but the cause and the solution were not found. Since the service worked well on 
a single node, the switch or the Linux networking stack were suspected as 
possible causes of the problem.

It was decided to try changing the MTU size and turning off the segmentation offloads
(TCP segmentation offload, Generic Segmentation Offload, and Generic Receive Offload).
In the end, turning off the mentioned segmentation offloads and increasing the MTU
size to 9000 bytes solved the problem, but the cause is still unknown.

The required setup of the interfaces is done in roles/setup/tasks/setup_ifaces.yml.
The role is executed from the plays/setup.yml playbook.
