#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2016 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Authors:
#     Santiago Dueñas <sduenas@bitergia.com>
#

import copy
import datetime
import sys
import threading
import time
import unittest

import dateutil.tz

if not '..' in sys.path:
    sys.path.insert(0, '..')

from arthur.errors import InvalidDateError
from arthur.utils import RWLock, str_to_datetime


class RWLockThread(threading.Thread):

    def __init__(self, lock, rw_buffer, sleep_before, sleep_after):
        super().__init__()
        self.lock = lock
        self.rw_buffer = rw_buffer
        self.sleep_before = sleep_before
        self.sleep_after = sleep_after
        self.entry_time = None
        self.exit_time = None


class Reader(RWLockThread):

    def __init__(self, lock, rw_buffer, sleep_before, sleep_after):
        super().__init__(lock, rw_buffer, sleep_before, sleep_after)
        self.rdata = None

    def run(self):
        time.sleep(self.sleep_before)
        self.lock.reader_acquire()
        self.entry_time = time.time()
        self.rdata = copy.deepcopy(self.rw_buffer)
        time.sleep(self.sleep_after)
        self.exit_time = time.time()
        self.lock.reader_release()


class Writer(RWLockThread):

    def __init__(self, lock, rw_buffer, sleep_before, sleep_after, data):
        super().__init__(lock, rw_buffer, sleep_before, sleep_after)
        self.wdata = data

    def run(self):
        time.sleep(self.sleep_before)
        self.lock.writer_acquire()
        self.entry_time = time.time()
        self.rw_buffer[0] = self.wdata
        time.sleep(self.sleep_after)
        self.exit_time = time.time()
        self.lock.writer_release()


class TestRWLock(unittest.TestCase):
    """Unit tests for RWLock class"""

    def test_multiple_readers(self):
        """Test non-exclusive access to readers"""

        rw_lock = RWLock()
        rw_buffer = ['A']

        threads = [Reader(rw_lock, rw_buffer, 0, 0.05),
                   Reader(rw_lock, rw_buffer, 0.01, 0),
                   Writer(rw_lock, rw_buffer, 0.02, 0.02, 'Z'),
                   Reader(rw_lock, rw_buffer, 0.03, 0)]

        for th in threads:
            th.start()
        for th in threads:
            th.join()

        self.assertEqual(rw_buffer, ['Z'])
        self.assertEqual(threads[0].rdata, ['A'])
        self.assertEqual(threads[1].rdata, ['A'])
        self.assertEqual(threads[3].rdata, ['Z'])

        # Second reader started after the first one finishing
        # before it. This means there is no mutual exclusion
        # between readers.
        self.assertLess(threads[0].entry_time, threads[1].entry_time)
        self.assertGreater(threads[0].exit_time, threads[1].exit_time)

    def test_exclusion_writers(self):
        """Test if only one writer can access the resource at the same time"""

        rw_lock = RWLock()
        rw_buffer = ['A']

        threads = [Reader(rw_lock, rw_buffer, 0, 0.02),
                   Writer(rw_lock, rw_buffer, 0.02, 0.03, 'Z'),
                   Writer(rw_lock, rw_buffer, 0.03, 0, 'X'),
                   Reader(rw_lock, rw_buffer, 0.04, 0)]

        for th in threads:
            th.start()
        for th in threads:
            th.join()

        self.assertEqual(rw_buffer, ['X'])
        self.assertEqual(threads[0].rdata, ['A'])
        self.assertEqual(threads[3].rdata, ['X'])

        # First writting lasts more than the time that the second
        # writer needs to access the critical section. But, the
        # second writer will wait till the first writer ends its work.
        self.assertLess(threads[1].entry_time, threads[2].entry_time)
        self.assertLess(threads[1].exit_time, threads[2].exit_time)

        # The last thread (a reader) will wait till the last writer ends.
        self.assertLess(threads[2].entry_time, threads[3].entry_time)
        self.assertLess(threads[2].exit_time, threads[3].exit_time)


class TestStrToDatetime(unittest.TestCase):
    """Unit tests for str_to_datetime function"""

    def test_dates(self):
        """Check if it converts some dates to datetime objects"""

        date = str_to_datetime('2001-12-01')
        expected = datetime.datetime(2001, 12, 1, tzinfo=dateutil.tz.tzutc())
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

        date = str_to_datetime('13-01-2001')
        expected = datetime.datetime(2001, 1, 13, tzinfo=dateutil.tz.tzutc())
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

        date = str_to_datetime('12-01-01')
        expected = datetime.datetime(2001, 12, 1, tzinfo=dateutil.tz.tzutc())
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

        date = str_to_datetime('2001-12-01 23:15:32')
        expected = datetime.datetime(2001, 12, 1, 23, 15, 32,
                                     tzinfo=dateutil.tz.tzutc())
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

        date = str_to_datetime('2001-12-01 23:15:32 -0600')
        expected = datetime.datetime(2001, 12, 1, 23, 15, 32,
                                     tzinfo=dateutil.tz.tzoffset(None, -21600))
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

        date = str_to_datetime('2001-12-01 23:15:32Z')
        expected = datetime.datetime(2001, 12, 1, 23, 15, 32,
                                     tzinfo=dateutil.tz.tzutc())
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

        date = str_to_datetime('Wed, 26 Oct 2005 15:20:32 -0100 (GMT+1)')
        expected = datetime.datetime(2005, 10, 26, 15, 20, 32,
                                     tzinfo=dateutil.tz.tzoffset(None, -3600))
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

        date = str_to_datetime('Wed, 22 Jul 2009 11:15:50 +0300 (FLE Daylight Time)')
        expected = datetime.datetime(2009, 7, 22, 11, 15, 50,
                                     tzinfo=dateutil.tz.tzoffset(None, 10800))
        self.assertIsInstance(date, datetime.datetime)
        self.assertEqual(date, expected)

    def test_invalid_date(self):
        """Check whether it fails with an invalid date"""

        self.assertRaises(InvalidDateError, str_to_datetime, '2001-13-01')
        self.assertRaises(InvalidDateError, str_to_datetime, '2001-04-31')

    def test_invalid_format(self):
        """Check whether it fails with invalid formats"""

        self.assertRaises(InvalidDateError, str_to_datetime, '2001-12-01mm')
        self.assertRaises(InvalidDateError, str_to_datetime, '2001-12-01 02:00 +08888')
        self.assertRaises(InvalidDateError, str_to_datetime, 'nodate')
        self.assertRaises(InvalidDateError, str_to_datetime, None)
        self.assertRaises(InvalidDateError, str_to_datetime, '')


if __name__ == "__main__":
    unittest.main()
