#!/usr/bin/python3

import argparse
import sys

import access_variables as av

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Script for autogeneration of ned file containing network with connections based on topology variable file.

def parse_cli():
    parser = argparse.ArgumentParser(prog='generate_ini', description='Generate ini file for scenario')
    parser.add_argument('topo', help='Topology file (relative to engine/scenarios/topologies)')
    parser.add_argument('-c', '--comments', action='count', help='Including comments in produced file', default=0)
    parser.add_argument('-o', '--output', help='Path to output file')
    parser.add_argument('-p', '--path', default='../..', help='Path to engine ansible root directory (relative or absolute)')
    parser.add_argument('-n', '--name', help='Module name for generated network')
    return parser.parse_args()

def generate_context(topo, comments, name, path):
    context = {'topo': topo, 'comments': comments, 'name': name }
    av.set_path_to_engine(path)
    context.update(av.get_simulation_defaults())
    context.update(av.get_group_vars())
    context.update(av.get_topology(topo))
    context.update(av.get_host_vars(context['nodes']))
    return context

def generate(topo, comments, output, path, name):
    env = Environment(loader=FileSystemLoader('templates'), autoescape=select_autoescape()) # TODO: maybe use a different loader, e.g. ChoiceLoader, if service templates are going to be stored in the respective roles: https://jinja.palletsprojects.com/en/3.1.x/api/#jinja2.BaseLoader
    template = env.get_template('topo.j2')
    context = generate_context(topo, comments, name, path)
    rendered = template.render(context)
    if output == None:
        print(rendered)
    else:
        with open(output, "w") as o:
            o.write(rendered)
    return

def main():
    parser_args = parse_cli()
    topo = parser_args.topo
    comments = parser_args.comments
    output = parser_args.output
    path = parser_args.path
    name = parser_args.name
    generate(topo, comments, output, path, name)

if __name__ == "__main__":
    main()
