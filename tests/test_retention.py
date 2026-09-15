import logging
import unittest

from zfs_uploader.backup_db import Backup
from zfs_uploader.config import _parse_retention_block
from zfs_uploader.job import ZFSjob, _select_retained_backups


def _backup(backup_time, backup_type='full', dependency=None):
    return Backup(backup_time, backup_type, 'pool/filesystem',
                  f'pool/filesystem/{backup_time}.{backup_type}',
                  dependency=dependency, backup_size=1)


class RetentionSelectionTests(unittest.TestCase):
    def test_parse_retention_block(self):
        retention = """
        daily: 14
        weekly: 8
        monthly: 12
        yearly: 5
        """

        self.assertEqual({
            'daily': 14,
            'weekly': 8,
            'monthly': 12,
            'yearly': 5,
        }, _parse_retention_block(retention))

    def test_selects_latest_backup_for_each_period(self):
        backups = [
            _backup('20240101_010000'),
            _backup('20240101_230000'),
            _backup('20240102_010000'),
            _backup('20240201_010000'),
        ]

        retained, categories = _select_retained_backups(
            backups, {'daily': 2, 'monthly': 1})

        self.assertEqual({'20240102_010000', '20240201_010000'}, retained)
        self.assertEqual({'daily'}, categories['20240102_010000'])
        self.assertEqual({'daily', 'monthly'},
                         categories['20240201_010000'])

    def test_zero_or_missing_periods_do_not_retain_backups(self):
        backups = [
            _backup('20240101_010000'),
            _backup('20240102_010000'),
        ]

        retained, categories = _select_retained_backups(
            backups, {'daily': 0})

        self.assertEqual(set(), retained)
        self.assertEqual({}, categories)


class FakeBackupDB:
    def __init__(self, backups):
        self._backups = backups

    def get_backups(self):
        return self._backups


class FakeRetentionJob:
    _limit_backups_by_retention = ZFSjob._limit_backups_by_retention
    _add_retained_dependencies = ZFSjob._add_retained_dependencies
    _delete_backups_except = ZFSjob._delete_backups_except

    def __init__(self, backups, retention_policy):
        self._backup_db = FakeBackupDB(backups)
        self._retention_policy = retention_policy
        self._filesystem = 'pool/filesystem'
        self._logger = logging.getLogger(__name__)
        self.deleted = []

    def _delete_backup(self, backup):
        self.deleted.append(backup.backup_time)


class RetentionRotationTests(unittest.TestCase):
    def test_retained_incremental_keeps_full_dependency(self):
        backups = [
            _backup('20240101_010000', 'full'),
            _backup('20240102_010000', 'inc',
                    dependency='20240101_010000'),
            _backup('20240103_010000', 'inc',
                    dependency='20240101_010000'),
        ]
        job = FakeRetentionJob(backups, {'daily': 1})

        job._limit_backups_by_retention()

        self.assertEqual(['20240102_010000'], job.deleted)

    def test_deletes_incremental_backups_before_full_backups(self):
        backups = [
            _backup('20240101_010000', 'full'),
            _backup('20240102_010000', 'inc',
                    dependency='20240101_010000'),
            _backup('20240201_010000', 'full'),
        ]
        job = FakeRetentionJob(backups, {'daily': 1})

        job._limit_backups_by_retention()

        self.assertEqual(['20240102_010000', '20240101_010000'],
                         job.deleted)


if __name__ == '__main__':
    unittest.main()
