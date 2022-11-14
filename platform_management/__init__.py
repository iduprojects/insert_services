'''
IDU Digital City Platform management tool, GUI and CLI versions
'''

from platform_management.cli.insert_services import (InsertionMapping,
                                                     add_objects,
                                                     get_properties_keys,
                                                     load_objects, run_cli)

__author__ = 'Aleksei Sokol'
__maintainer__ = __author__

__email__ = 'kanootoko@gmail.com'
__license__ = 'MIT'
__version__ = '0.1.0'


__all__ = (
    '__author__',
    '__email__',
    '__license__',
    '__maintainer__',
    '__version__',
    '__app__',
    'InsertionMapping',
    'add_objects',
    'get_properties_keys',
    'load_objects',
    'run_cli'
)