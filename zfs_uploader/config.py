from configparser import ConfigParser
import logging
import os
import sys

from zfs_uploader.job import ZFSjob


class Config:
    """ Wrapper for configuration file. """

    @property
    def jobs(self):
        """ ZFS backup jobs. """
        return self._jobs

    def __init__(self, file_path=None):
        """ Construct Config object from file.

        Parameters
        ----------
        file_path : str
            File path to config file.

        """
        file_path = file_path or 'config.cfg'

        self._logger = logging.getLogger(__name__)
        self._logger.info(f'file_path={file_path} '
                          'msg="Loading configuration file."')

        if not os.path.isfile(file_path):
            self._logger.critical('No configuration file found.')
            sys.exit(1)

        self._cfg = ConfigParser()
        self._cfg.read(file_path)

        default = self._cfg['DEFAULT']
        self._jobs = {}
        for k, v in self._cfg.items():
            if k != 'DEFAULT':
                bucket_name = (v.get('bucket_name') or
                               default.get('bucket_name'))
                access_key = v.get('access_key') or default.get('access_key')
                secret_key = v.get('secret_key') or default.get('secret_key')
                filesystem = k

                if not all((bucket_name, access_key, secret_key)):
                    self._logger.critical(f'file_path={file_path} '
                                          f'filesystem={filesystem}'
                                          'msg="bucket_name, access_key or '
                                          'secret_key is missing from config."'
                                          )
                    sys.exit(1)

                cron_dict = None
                cron = v.get('cron') or default.get('cron')
                if cron:
                    cron_dict = _create_cron_dict(cron)

                self._jobs[k] = (
                    ZFSjob(
                        bucket_name,
                        access_key,
                        secret_key,
                        filesystem,
                        prefix=v.get('prefix') or default.get('prefix'),
                        region=v.get('region') or default.get('region'),
                        endpoint=v.get('endpoint') or default.get('endpoint'),
                        cron=cron_dict,
                        max_snapshots=(v.getint('max_snapshots') or
                                       default.getint('max_snapshots')),
                        max_backups=(
                                v.getint('max_backups') or
                                default.getint('max_backups')),
                        max_incremental_backups_per_full=(
                                v.getint('max_incremental_backups_per_full') or
                                default.getint('max_incremental_backups_per_full')), # noqa
                        storage_class=(v.get('storage_class') or
                                       default.get('storage_class')),
                        max_multipart_parts=(
                                v.getint('max_multipart_parts') or
                                default.getint('max_multipart_parts')),
                        retention_policy=_create_retention_policy(v, default)
                    )
                )


def _create_cron_dict(cron):
    values = cron.split()

    return {'minute': values[0],
            'hour': values[1],
            'day': values[2],
            'month': values[3],
            'day_of_week': values[4]}


def _create_retention_policy(section, default):
    retention_policy = _parse_retention_block(default.get('retention'))
    retention_policy.update(_parse_retention_block(section.get('retention')))

    for period in ('daily', 'weekly', 'monthly', 'yearly'):
        value = _get_retention_value(section, default, period)
        if value is not None:
            retention_policy[period] = value

    return retention_policy or None


def _parse_retention_block(retention):
    retention_policy = {}

    if retention is None:
        return retention_policy

    for line in retention.splitlines():
        line = line.strip()
        if not line:
            continue

        if ':' in line:
            period, value = line.split(':', 1)
        elif '=' in line:
            period, value = line.split('=', 1)
        else:
            continue

        period = period.strip()
        if period in ('daily', 'weekly', 'monthly', 'yearly'):
            retention_policy[period] = int(value.strip())

    return retention_policy


def _get_retention_value(section, default, period):
    for key in (f'retention_{period}', period):
        value = section.get(key)
        if value is None:
            value = default.get(key)
        if value is not None:
            return int(value)

    return None
