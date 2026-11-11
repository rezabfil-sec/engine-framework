# Google Cloud Platform (GCP) Integration
Through this integration, experiments that are conducted using EnGINE's physical nodes can be simulated through Google Compute Engine (GCE) VM instances. In order to use this feature, there are some things to watch out for. 

Most scripts and additional files are stored in `GCP_tools` directory. For additional clarity on GCP integration mode code changes, keywords such as the `# GCP ADDITION START` comment or `gcp is not defined` condition can be searched.

## Ansible-GCP interaction
### GCP interaction setup
There are various components that need to be initialized before using GCP integration mode. This includes:

- Create or use a GCP project
    - Users need at least a `Compute Admin` role + `IAM Service Account` permission
    - Developers need an `Editor` role
    - Permissions can be found in **IAM & Admin > IAM**
- Create or use the default service account to generate access keys
    1. `IAM & Admin > Service Accounts`
    2. Click the service account and navigate to the `KEYS` tab
    3. Create new key and save the `<service_account_file>.json` file to the `GCP_tools` directory.
- Allow the management host to SSH to the VM instances
    1. `Compute Engine > Metadata > SSH KEYS tab`
    2. Generate SSH-Key in the management host and add the public key there

- Adjust the following fields within `group_vars/all.yml`:
    - gcp_config.project
    - gcp_config.authentication.user
    - gcp_config.authentication.service_account_file
    - gcp_config.authentication.public_key_file

- Adjust `hosts` and `host_vars`
    - refer to `polkadot.yml` for TDX-enabled standalone cloud node
    - refer to `octorand.yml` for SEV-SNP-enabled flexible node
    - refer to `rococo.yml` for base standalone cloud node

- Adjust the `json_filename` field in `GCP_tools/files/obtain_access_token.py` to the created `<service_account_file>.json`



### Configuration file
`GCP_tools/ansible_gcp.cfg` file should contains all the necessary components for Ansible to use the `Google.Cloud` module. Note that GCP does not allow remote access as root by default. This is handled in the script. These fields have to be adjusted:
```yaml
[defaults]
remote_user = <ssh remote username>
private_key_file = <path to private key>
inventory = ../hosts, ./inventory.gcp.yml
...

[inventory]
enable_plugins = gcp_compute, ...
```

### Inventory file
`GCP_tools/inventory.gcp.yml` file creates an inventory, which dynamically queries GCE and tells Ansible what nodes can be managed. However, since GCP doesn't allow root ssh off-the-box, this is mainly used for debugging and is optional. [Link to documentation](https://docs.ansible.com/ansible/latest/collections/google/cloud/gcp_compute_inventory.html).

### Specifying configuration file manually
In order to override the default `ansible.cfg` file with GCP's configuration file, the `ANSIBLE_CONFIG` has to be specified before running any Ansible commands,
```sh
ANSIBLE_CONFIG=GCP_tools/ansible_gcp.cfg ansible-inventory --graph
```  

## Scenarios limitations
- `00-nodes.yml`
    - Kata-containers not supported, only RunC
- `01-network.yml`
    - Only one network configuration is suppported. For now, this is hardcoded to 'net-1'
    - It is not necessary to specify the network interfaces since this will be dynamically adjusted at runtime (refer to `scenarios/gcp-integration-demo`)
    - GCP only supports up to 5 VPCs per project. This means that only five subnets can be specified at a time
    - GCP only supports up to 8 internal-external IP address pairs per region. It is necessary to manually configure the regional location of nodes within the `host_vars` to mitigate this limitation.  
- `02-stacks.yml` (besides the limitations specified below, all existing experiments should be directly portable to GCP integration mode)
    - GCP integration mode does not support the use of control groups, so additional adjustments to existing experiments must be made
    - Clock-synchronization precision is not known and guaranteed for ns precision (although NTP is pre-configured by GCP)
    - Hardware timestamping is not supported either



## Running a playbook
On top of the environment variable `scene`, the variable `gcp` has to explicitly be specified.
```sh
ANSIBLE_CONFIG=GCP_tools/ansible_gcp.cfg ansible-playbook plays/all.yml -e "scene=kata-demo gcp=true"
```

When GCP mode is specified, some of the default EnGINE tasks are overriden with GCP-specific implementations. 
- **Install**
    1. Skipping through the entire OS installation step for physical nodes
    2. Extracting GCE machine types for each hosts specified
- **Setup**
    1. Skipping through OvS, SRIOV, Priority, LXC setups
    2. Creating of VPC networks and VPC subnetworks to replicate the multiple network interfaces used by physical nodes
    3. Instantiating VM instances on the created subnetworks and networks
    4. Exchanging ssh-keys to allow root access to the machines
    5. Updating the IP routes for individual VMs
    6. Setting up basic packages and containerD
- **Scenario**
    1. Skipping through all LXC setups
    2. Configuring VPC routes to allow container-container communication
    4. Creation of bridge per VMs with its own subnets (10.X.0.0/24) 
    5. Creation of containers on the created bridge
    6. Updating IP routes for VM to allow container-container communication
    7. Skipping through Network reset per experiment, instead only increment stack
- **Process** 
    1. Deleting all VM instances at the end
    2. Deleting all firewall rules used by VPC networks
    3. Deleting all VPC routes used by VPC networks
    4. Deleting VPC Networks used

## Confidential Computing
| TEE-solution | Machine-Type |
| ------------ | ------------- |
| AMD SEV-SNP  | N2D           |
| AMD SEV      | N2D, C2D      |
| Intel TDX    | C3            |

### VMs
GCP supports a range of VM-based TEEs. Out-of-the-box, only AMD SEV can be created using the Ansible module. AMD SEV-SNP and Intel TDX can only be used by using GCLI or REST API. This is abstracted in the script for the end-user and does not need additional setup.

Since AMD SEV-SNP and Intel TDX are still in preview, only the following regions are supported
- AMD SEV-SNP:
    - asia-southeast1-a
    - asia-southeast1-b
    - asia-southeast1-c
    - europe-west4-a
    - europe-west4-b
    - europe-west4-c
    - us-central1-a
    - us-central1-b
    - us-central1-c
- Intel TDX:
    - us-central1-a
    - us-central1-b
    - us-central1-c

### Confidential Containers
Kata-containers make use of the host's nested virtualisation feature to enable its isolation.

GCP does not allow L1 nested virtualisation on VMs running the AMD- and ARM-based processors, and therefore cannot deploy Kata-containers. At the time of writing this (03.05.2024), Intel TDX does not support nested virtualization either.