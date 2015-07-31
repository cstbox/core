#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'Eric Pascual - CSTB (eric.pascual@cstb.fr)'


import os
from errno import ESRCH
from argparse import ArgumentTypeError

from pycstbox.cli import get_argument_parser
from pycstbox.log import getLogger, set_loglevel_from_args


def remove_dead_pid(args):
    logger = getLogger('cbx-pid-janitor')
    set_loglevel_from_args(logger, args)

    for pid_file_name in [n for n in os.listdir(args.pid_files_dir) if n.endswith('.pid')]:
        pid_path = os.path.join(args.pid_files_dir, pid_file_name)
        with file(pid_path) as fp:
            pid = int(fp.readline().strip())

        try:
            os.kill(pid, 0)
        except OSError as err:
            if err.errno == ESRCH:
                os.remove(pid_path)
                logger.info('dead process PID file removed: %s', pid_file_name)


def dir_path(s):
    if not os.path.isdir(s):
        raise ArgumentTypeError('path is not a directory')
    try:
        tmp = file(os.path.join(s, '99999999'), 'wt')
    except IOError:
        raise ArgumentTypeError('path cannot be written to')
    else:
        tmp.close()
        os.remove(tmp.name)
        return s

if __name__ == '__main__':
    parser = get_argument_parser('Remove PID files left there by dead processes')

    parser.add_argument(
        '-d', '--pid-files-dir',
        dest='pid_files_dir',
        default='/var/run/cstbox',
        type=dir_path,
        help='path of the directory where CSTBox PID files are stored'
    )

    remove_dead_pid(parser.parse_args())
