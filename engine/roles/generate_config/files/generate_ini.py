#!/usr/bin/python3

import argparse
import sys

import ptp
import access_variables as av

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Doc

def parse_cli():
    parser = argparse.ArgumentParser(prog='generate_ini', description='Generate ini file for scenario')
    parser.add_argument('scene', help='Scene directory (relative to engine/scenarios')
    parser.add_argument('-c', '--comments', action='count', help='Including comments in produced file', default=0)
    parser.add_argument('-o', '--output', help='Path to output file')
    parser.add_argument('-p', '--path', default='../../..', help='Path to engine ansible root directory (relative or absolute)')
    parser.add_argument('-m', '--mode', choices=['mac'], help='Mode for generating PTP hierarchy and related configuration')
    return parser.parse_args()

def generate_context(scene, comments, path, mode):
    context = { 'scene': scene, 'comments': comments, 'mode': mode }
    av.set_path_to_engine(path)
    context.update(av.get_simulation_defaults())
    context.update(av.get_group_vars())
    nodes = av.get_nodes(scene)
    context.update(nodes)
    host_vars = av.get_host_vars(nodes['nodes'])
    context.update(host_vars)
    network_processed = av.get_network_processed(scene)
    context.update(network_processed)
    if mode != None:
        context.update({ 'ptp_vars': ptp.mode(mode, nodes['node_mapping'], network_processed, host_vars )})
    context.update(av.get_stacks_with_service_defaults(scene))
    context.update(av.get_actions(scene))
    context.update(av.get_experiments(scene))
    return context

def generate(scene, comments, output, path, mode):
    env = Environment(loader=FileSystemLoader('../templates'), autoescape=select_autoescape()) # TODO: maybe use a different loader, e.g. ChoiceLoader, if service templates are going to be stored in the respective roles: https://jinja.palletsprojects.com/en/3.1.x/api/#jinja2.BaseLoader
    template = env.get_template('scenario.j2')
    context = generate_context(scene, comments, path, mode)
    rendered = template.render(context)
    if output == None:
        print(rendered)
    else:
        with open(output, "w") as o:
            o.write(rendered)
    return

def main():
    parser_args = parse_cli()
    scene = parser_args.scene
    comments = parser_args.comments
    output = parser_args.output
    path = parser_args.path
    mode = parser_args.mode
    generate(scene, comments, output, path, mode)

if __name__ == "__main__":
    main()
