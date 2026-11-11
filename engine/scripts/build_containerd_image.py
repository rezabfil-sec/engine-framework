import argparse
import fabric
from fabric import Connection, Config

BUILDKIT_VERSION = "0.12.0"
BUILDKIT_URL= f'https://github.com/moby/buildkit/releases/download/v{BUILDKIT_VERSION}/buildkit-v{BUILDKIT_VERSION}.linux-amd64.tar.gz'

NERDCTL_VERSION = "1.4.0"
NERDCTL_URL = f'https://github.com/containerd/nerdctl/releases/download/v{NERDCTL_VERSION}/nerdctl-{NERDCTL_VERSION}-linux-amd64.tar.gz'

DOCKERFILE_DIR = "./dockerfiles/"

OUTPUT_DIR = "/srv/testbed/vehiclenet/experiments/software/"

parser = argparse.ArgumentParser(description='Build containerd image on host for a given Dockerfile')
parser.add_argument('node', metavar='node', type=str, help='Node to build image on')
parser.add_argument('dockerfile', metavar='dockerfile', type=str, help='Name of Dockerfile (without suffix))')
parser.add_argument('-o', '--outpath', metavar='outpath', type=str, help='Path to store image on host', default="/srv/testbed/vehiclenet/experiments/software/")
parser.add_argument('-f', '--outname', metavar='outname', type=str, help='Name of image to save; uses Dockerfile name if not specified', default=None)

args = parser.parse_args()

args.outname = args.outname if args.outname else args.dockerfile

with Connection(args.node) as conn:
    # install nerdctl
    print(f'Installing nerdctl v{NERDCTL_VERSION} on {args.node}..')
    conn.run(f'curl -sL {NERDCTL_URL} | tar -C /usr/local/bin -xz')

    # install buildkit
    print(f'Installing buildkit v{BUILDKIT_VERSION} on {args.node}..')
    conn.run(f'curl -sL {BUILDKIT_URL} | tar -C /usr/local -xz')

    # create temporary directory
    conn.run(f'rm -r /tmp/buildkit > /dev/null 2>&1 || true')
    conn.run(f'mkdir -p /tmp/buildkit')

    # copy Dockerfile to host
    print(f'Copying Dockerfile to {args.node}..')
    conn.put(f'{DOCKERFILE_DIR}/{args.dockerfile}.Dockerfile', f'/tmp/buildkit/{args.dockerfile}.Dockerfile')

    # copy authorized_keys to host
    conn.run('cp /root/.ssh/authorized_keys /tmp/buildkit/authorized_keys')

    # start buildkit in background
    print(f'Starting buildkit on {args.node}..')
    conn.run('nohup buildkitd </dev/null >/dev/null 2>&1 & sleep 1')

    print(f'Building image {args.outname} on {args.node}..')
    conn.run(f'nerdctl build -f /tmp/buildkit/{args.dockerfile}.Dockerfile -t {args.outname} --output type=oci,dest=/tmp/buildkit/{args.outname}.tar /tmp/buildkit', warn=True)

    # check if image was built with stat
    result = conn.run(f'stat /tmp/buildkit/{args.outname}.tar > /dev/null 2>&1', warn=True)
    if result.failed:
        print(f'Image {args.outname} could not be built on {args.node}!')
        exit(1)

    print(f'Image {args.outname} successfully built on {args.node}!')

    # stop buildkit
    print(f'Stopping buildkit on {args.node}..')
    conn.run('pkill buildkitd')

    # copy image to local machine
    print(f'Copying image {args.outname} to current host..')
    conn.get(f'/tmp/buildkit/{args.outname}.tar', f'{args.outpath}/{args.outname}.tar')