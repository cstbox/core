#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of CSTBox.
#
# CSTBox is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# CSTBox is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with CSTBox.  If not, see <http://www.gnu.org/licenses/>.

import csv


class TextExporter(object):
    """ Abstract root class for text file based exporters."""

    def __init__(self, to_path):
        self._to_path = to_path
        self._to_file = None

    def starting(self, parms=None):
        self._to_file = open(self._to_path, 'w')

    def terminating(self):
        if self._to_file:
            self._to_file.close()


class TabulatedTextExporter(TextExporter):
    """ Tabulated text export.

    The folowing columns are included in the records :

    - timestamp
    - variable type
    - variable name
    - variable value
    - variable units (if any)
    """
    EXPORT_FORMAT = 'text.tab'

    def export_event(self, event):
        ts, var_type, var_name, value, data = event
        self._to_file.write('\t'.join([
            ts.strftime('%Y/%m/%d %H:%M:%S.%f')[:-3],
            var_type,
            var_name,
            str(value),
            data.get('unit','')]) + '\n')


class CSVExporter(TextExporter):
    """ Standard CSV export.

    The folowing columns are included in the records :

    - timestamp
    - variable type
    - variable name
    - variable value
    - variable units (if any)

    The corresponding column header is inserted.
    """
    EXPORT_FORMAT = 'text.csv'

    def __init__(self, to_path):
        super(CSVExporter, self).__init__(to_path)
        self._writer = None

    def writeheader(self):
        self._writer.writerow(
            ['timestamp', 'msec', 'var_type', 'var_name', 'value', 'units']
        )

    def writer(self):
        return csv.writer(self._to_file)

    def starting(self, parms=None):
        super(CSVExporter, self).starting()
        self._writer = self.writer()
        self.writeheader()

    def export_event(self, event):
        ts, var_type, var_name, value, data = event
        self._writer.writerow([
            ts.strftime('%Y-%m-%d %H:%M:%S'),
            int(ts.microsecond / 1000),
            var_type,
            var_name,
            value,
            data.get('unit','')])


class ExcelCSVExporter(CSVExporter):
    """ Excel CSV dialect export."""
    EXPORT_FORMAT = 'text.csv.excel'

    def writer(self):
        return csv.writer(self._to_file,
                          delimiter=";",
                          quoting=csv.QUOTE_NONNUMERIC,
                          quotechar='"'
                          )

