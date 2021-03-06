"""Data pipelines to parse benchmark YAML for charts.

Extracts benchmark YAML and combines with template chart YAML for Vega
charts. Run `python _data/charts.py` to build the charts.
"""
# pylint: disable=no-value-for-parameter

import glob
import os
import json
from dateutil.parser import parse

import jinja2
# pylint: disable=redefined-builtin, no-name-in-module
from toolz.curried import map, pipe, get, curry, filter, compose
from toolz.curried import valmap, itemmap, groupby, memoize
import yaml


def fcompose(*args):
    """Helper function to compose functions.

    >>> f = lambda x: x - 2
    >>> g = lambda x: 2 * x
    >>> f(g(3))
    4
    >>> fcompose(g, f)(3)
    4

    Args:
      *args: tuple of functions

    Returns:
      composed functions
    """
    return compose(*args[::-1])


def free_energy_file():
    """Get the free energy chart template file name

    Returns:
      the file name
    """
    return 'free_energy.yaml.j2'


def read_yaml(filepath):
    """Read a YAML file

    Args:
      filepath: the path to the YAML file

    Returns:
      returns a dictionary
    """
    with open(filepath) as stream:
        data = yaml.safe_load(stream)
    return data


@curry
def write_json(data, filepath):
    """Write a JSON file

    Args:
      data: the dictionary to write
      filepath: the path to the JSON file

    Returns:
      returns a tuple of (filepath, data)
    """
    with open(filepath, 'w') as stream:
        json.dump(data, stream, sort_keys=True, indent=2)
    return (filepath, data)


def get_path():
    """Return the local file path for this file.

    Returns:
      the filepath
    """
    return pipe(
        __file__,
        os.path.realpath,
        os.path.split,
        get(0)
    )


@curry
def update_dict(dict_, **kwargs):
    """Add keys to a new dictionary.

    Args:
      dict_: the dictionary to add to
      kwargs: the key, value pairs to add

    Returns:
      a new dictionary
    """
    return dict(list(dict_.items()) + list(kwargs.items()))


def filter_data(yaml_data):
    """Extract the free_energy data from the YAML files.

    Args:
      yaml_data: the benchmark YAML data

    Returns:
      the free_energy data from the YAML data
    """
    return pipe(
        yaml_data,
        dict,
        valmap(lambda val: val['data']),
        valmap(filter(lambda item: item['name'].lower() == 'free_energy')),
        valmap(list),
        valmap(get(0)),
        itemmap(lambda item: (item[0], update_dict(item[1], name=item[0]))),
        lambda dict_: sorted(list(dict_.values()),
                             key=lambda item: item['name'])
    )


def get_yaml_data():
    """Read in the YAML data but don't group

    Returns:
      list of tuples of (name, data_dict)
    """
    return pipe(
        os.path.join(get_path(), 'simulations/*/meta.yaml'),
        glob.glob,
        sorted,
        map(lambda path_: (os.path.split(os.path.split(path_)[0])[1],
                           read_yaml(path_))),
        filter(lambda item: item[0] not in ['example', 'example_minimal'])
    )


def get_data():
    """Read in the YAML data and group by benchmark id

    Returns:
      a dictionary with benchmark ids as keys and lists of appropriate
      data for values
    """
    return pipe(
        get_yaml_data(),
        groupby(
            lambda item: "{0}.{1}".format(item[1]['benchmark']['id'],
                                          str(item[1]['benchmark']['version']))
        ),
        valmap(filter_data),
    )


def get_chart_file():
    """Get the name of the chart file

    Returns:
      the chart YAML file

    """
    return os.path.join(get_path(), 'charts', free_energy_file())


def write_chart_json(item):
    """Write a chart JSON file.

    Args:
      item: a (benchmark_id, chart_dict) pair

    Returns:
      returns the (filepath, json_data) pair
    """
    file_name = fcompose(
        free_energy_file,
        lambda x: x.replace('.yaml', '.json'),
        lambda x: x.replace('.j2', '')
    )
    return pipe(
        item[0],
        lambda id_: "{0}_{1}".format(item[0], file_name()),
        lambda file_: os.path.join(get_path(), '../data/charts', file_),
        write_json(item[1])
    )


@memoize
def get_marks():
    """Get the mark data for the free energy charts

    Returns:
      a dictionary defined in marks.yaml
    """
    return pipe(
        os.path.join(get_path(), 'marks.yaml'),
        read_yaml
    )


def process_chart(id_, data):
    """Process chart's YAML with data.

    Args:
      id_: the benchmark ID
      data: the data to process the YAML file

    Returns:
      the rendered YAML as a dictionary
    """
    return pipe(
        get_chart_file(),
        render_yaml(data=data, id_=id_, marks=get_marks()[id_]),
        yaml.load
    )


def to_datetime(datetime_str, format_="%Y/%m/%d %H:%M:%S"):
    """Datetime formater for Jinja template.
    """
    return parse(datetime_str).strftime(format_)


@curry
def render_yaml(tpl_path, **kwargs):
    """Return the rendered yaml template.

    Args:
      tpl_path: path to the YAML jinja template
      **kwargs: data to render in the template

    Returns:
      the rendered template string
    """
    path, filename = os.path.split(tpl_path)
    loader = jinja2.FileSystemLoader(path or './')
    env = jinja2.Environment(loader=loader)
    env.filters['to_yaml'] = yaml.dump
    env.filters['to_datetime'] = to_datetime
    return env.get_template(filename).render(**kwargs)


def main():
    """Generate the chart JSON files

    Returns:
      list of (filepath, chart_json) pairs
    """
    return pipe(
        get_data(),
        itemmap(
            lambda item: (
                item[0],
                process_chart(item[0], item[1])
            )
        ),
        itemmap(write_chart_json)
    )


def landing_page_j2():
    """Get the name of the chart file

    Returns:
      the chart YAML file

    """
    return os.path.join(get_path(), 'charts', 'simulations.yaml.j2')


def landing_page_json():
    """Generate the landing page JSON vega spec.

    Returns:
      (filepath, chart_json) pairs
    """
    def extract_id(name):
        """Extract benchmark ID from png path
        """
        return name.replace("../images/", "").replace('_free_energy.png', '')
    return pipe(
        ['1a.1_free_energy.png',
         '1b.1_free_energy.png',
         '1c.1_free_energy.png',
         '1d.1_free_energy.png',
         '2a.1_free_energy.png',
         '2b.1_free_energy.png',
         '2c.1_free_energy.png',
         '2d.1_free_energy.png'],
        map(lambda name: os.path.join("..", 'images', name)),
        enumerate,
        map(
            lambda tup: (
                lambda count, name: dict(path=name,
                                         col=(count % 4),
                                         row=count // 4,
                                         link=extract_id(name))
                )(*tup)
        ),
        list,
        lambda data: j2_to_json(landing_page_j2(),
                                os.path.join(get_path(),
                                             '../data/charts',
                                             'simulations.json'),
                                data=data)
    )


def j2_to_json(path_in, path_out, **kwargs):
    """Render a yaml.j2 chart to JSON.

    Args:
      path_in: the j2 template path
      path_out: the JSON path to write to
      kwargs: data to pass to the j2 template

    Returns:
      the file path and JSON string
    """
    return pipe(
        render_yaml(path_in, **kwargs),
        yaml.load,
        write_json(filepath=path_out)
    )


if __name__ == "__main__":
    main()
    landing_page_json()
