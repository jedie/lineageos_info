#!/usr/bin/env python3

'''
    Convert the Wiki pages:
        https://wiki.lineageos.org/devices/

    use the git sources from:
        https://github.com/LineageOS/lineage_wiki.git
    via git submodule, see:
        https://github.com/jedie/lineageos_info/blob/master/.gitmodules

    more info in README, see:
        https://github.com/jedie/lineageos_info#readme

    created 28.12.2018 by Jens Diemer
'''

import csv
import datetime
import logging
import re
import shutil
import subprocess
from pathlib import Path

# https://pyyaml.org/wiki/PyYAMLDocumentation
from yaml import Loader, load

logging.basicConfig(
    level=logging.DEBUG,
    filename='device_info.log',
    filemode='w',
)
log = logging.getLogger(__name__)

LINEAGE_OS_VERSIONS = {16, 17}
INFO_TEMPLATE = '''{vendor} {name} - https://wiki.lineageos.org/devices/{codename}'''
README_TOP10_HEADLINE = '=== top 10 devices'

GIT_BIN = shutil.which('git')


class CsvGenerator:
    HEADER_VENDOR = 'vendor'
    HEADER_NAME = 'name'
    HEADER_MAINTAINER_COUNT = 'maintainers'
    HEADER_CODENAME = 'codename'
    HEADER_REMOVEABLE_BATTERY = 'removable battery'
    HEADER_RELEASE = 'release'
    HEADER_SCREEN = 'screen'
    HEADER_MODELS = 'models'
    HEADER_RAM = 'RAM'
    HEADER_STORAGE = 'storage'
    HEADER_SOC = 'SOC'
    HEADER_VERSIONS = 'versions'

    HEADER_WIKI_DATE = 'Wiki mod.Date'
    HEADER_WIKI_LINK = 'Wiki Link'

    def __init__(self, *, csv_file):

        self.csv_file = csv_file

        fieldnames = [  # Note: Order here is the order in the CVS file!
            self.HEADER_VENDOR,
            self.HEADER_NAME,
            self.HEADER_RELEASE,
            self.HEADER_SCREEN,
            self.HEADER_RAM,
            self.HEADER_STORAGE,
            self.HEADER_REMOVEABLE_BATTERY,
            self.HEADER_MAINTAINER_COUNT,
            self.HEADER_CODENAME,
            self.HEADER_MODELS,
            self.HEADER_SOC,
            self.HEADER_VERSIONS,
            self.HEADER_WIKI_DATE,
            self.HEADER_WIKI_LINK,
        ]

        self.csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        self.csv_writer.writeheader()

    def add_device(self, device):
        row = {  # Note: Order is *not* important here!
            self.HEADER_VENDOR: device.lineageos_data['vendor_short'].capitalize(),
            self.HEADER_NAME: device.lineageos_data['name'],
            self.HEADER_MAINTAINER_COUNT: device.lineageos_data['maintainer_count'],
            self.HEADER_CODENAME: device.lineageos_data['codename'],
            self.HEADER_REMOVEABLE_BATTERY: device.lineageos_data['removable_battery'],
            self.HEADER_RELEASE: device.lineageos_data['release'],
            self.HEADER_SCREEN: device.lineageos_data['screen'],
            self.HEADER_MODELS: ','.join([x for x in device.lineageos_data.get('models', '')]),
            self.HEADER_RAM: device.lineageos_data['ram'],
            self.HEADER_STORAGE: device.lineageos_data['storage'],
            self.HEADER_SOC: device.lineageos_data['soc'],
            self.HEADER_VERSIONS: device.lineageos_data['versions'],
            self.HEADER_WIKI_DATE: device.wiki_commit_date,
            self.HEADER_WIKI_LINK: device.lineageos_wiki_link,
        }
        self.csv_writer.writerow(row)


class MultiCsvFile:
    def __init__(self, path, filename_template, versions):
        self.path = path
        assert '{version}' in filename_template
        self.filename_template = filename_template
        self.versions = versions

    def __enter__(self):
        self.files = []
        self.csv_generators = {}
        for version in self.versions:
            filename = self.filename_template.format(version=version)
            file_path = Path(self.path, filename)
            csv_file = file_path.open('w')
            self.files.append(csv_file)
            self.csv_generators[version] = CsvGenerator(csv_file=csv_file)
        return self

    def add_device(self, version, device):
        csv_generator = self.csv_generators[version]
        csv_generator.add_device(device)

    def __exit__(self, exc_type, exc_val, exc_tb):
        print()
        for f in self.files:
            f.close()
            print(f' *** file generated: {f.name} ***')


class Device:
    def __init__(self, lineageos_versions, wiki_commit_date):
        self.lineageos_versions = lineageos_versions
        self.wiki_commit_date = wiki_commit_date
        self.short_name = None
        self.lineageos_data = {}

    def __lt__(self, other):
        if self.lineageos_data['maintainer_count'] != other.lineageos_data['maintainer_count']:
            return self.lineageos_data['maintainer_count'] > other.lineageos_data['maintainer_count']

        return self.short_name < other.short_name

    def __str__(self):
        return f'{self.short_name} ({self.lineageos_data["maintainer_count"]} maintainers)'

    def load_lineageos_wiki_data(self, data):
        self.short_name = '{vendor_short} {name}'.format(**data).capitalize()
        self.lineageos_data = data

        self.lineageos_data['maintainer_count'] = len(self.lineageos_data['maintainers'])
        self.lineageos_data['versions'] = {int(ver) for ver in self.lineageos_data['versions']}
        self.filtered_lineageos_version = self.lineageos_data['versions'] & self.lineageos_versions
        self.lineageos_wiki_link = f'https://wiki.lineageos.org/devices/{self.lineageos_data["codename"]}'

        screen = self.lineageos_data['screen']
        if screen:
            try:
                inches = re.findall(r'([\d\.]+) in', repr(screen))[0]
            except IndexError:
                pass
            else:
                self.lineageos_data['screen'] = inches

        battery = repr(self.lineageos_data.get('battery'))
        if "'removable': True" in battery:
            self.lineageos_data['removable_battery'] = True
        elif "'removable': False" in battery:
            self.lineageos_data['removable_battery'] = False
        else:
            self.lineageos_data['removable_battery'] = '???'

        print(INFO_TEMPLATE.format(**self.lineageos_data))

    def skip_device(self):
        if self.lineageos_data['maintainer_count'] < 1:
            log.info('Skip %r: no maintainers.', self.short_name)
            return True

        if not self.filtered_lineageos_version:
            log.info('Skip %r: only: %r', self.short_name, self.lineageos_versions)
            return True

        ram = self.lineageos_data['ram']
        if ram in ('1 GB', '2 GB'):
            log.info('Skip %r: Only %r RAM', self.short_name, ram)
            return True

        storage = self.lineageos_data['storage']
        if storage in ('8 GB', '16 GB'):
            log.info('Skip %r: Only %r Storage', self.short_name, storage)
            return True

        return False  # Keep this device


def get_git_commit_date(wiki_devices_path, item):
    item_path = item.relative_to(wiki_devices_path)
    popenargs = [GIT_BIN, 'log', '-1', '--format="%cd"', '--date=short', str(item_path)]
    # print(' '.join(popenargs))
    raw_commit_date = subprocess.check_output(popenargs, cwd=wiki_devices_path, universal_newlines=True)
    commit_date = raw_commit_date.strip().strip('"\'')
    return commit_date


def generate_readme_top10(wiki_commit_dates, devices):
    lines = []

    for device in sorted(devices)[:10]:
        lines.append(
            f'* [[{device.lineageos_wiki_link}|{device.short_name}]]'
            f' ({device.lineageos_data["maintainer_count"]} maintainers)'
        )
    lines.append('')

    newest_commit_date = max(wiki_commit_dates)
    lines.append(f'Last LineageOS wiki page update: {newest_commit_date}')
    now = datetime.datetime.now()
    lines.append(f'Generated: {now.strftime("%Y-%m-%d")}')

    return lines


def generate_csv(*, csv_file_path, filename_template, wiki_devices_path, lineageos_versions, readme_path):
    assert isinstance(csv_file_path, Path)
    assert isinstance(wiki_devices_path, Path)
    assert isinstance(readme_path, Path)

    print(f'Read WIKI divice files from: {wiki_devices_path}')
    assert wiki_devices_path.is_dir(), f'ERROR: Path not found: {wiki_devices_path}'

    csv_file_path = csv_file_path.resolve()

    print(f'Generate: {csv_file_path}')
    log.info('Generate csv on %s+0000', datetime.datetime.utcnow())

    ##################################################################
    # read LineageOS Wiki files:

    devices = []
    wiki_commit_dates = []
    for item in wiki_devices_path.iterdir():
        wiki_commit_date = get_git_commit_date(wiki_devices_path, item)
        wiki_commit_dates.append(wiki_commit_date)

        device = Device(lineageos_versions, wiki_commit_date=wiki_commit_date)

        with item.open('r', encoding='utf-8') as ymlfile:
            device_data = load(ymlfile, Loader=Loader)

        device.load_lineageos_wiki_data(data=device_data)

        devices.append(device)
        # if len(devices) > 10: # only for developing!
        #     break

    ##################################################################
    # save .cvs files:

    with MultiCsvFile(csv_file_path, filename_template, lineageos_versions) as multi_csv:
        for device in sorted(devices):
            print(device)
            if device.skip_device():
                continue

            for version in device.filtered_lineageos_version:
                multi_csv.add_device(version, device)

    ##################################################################
    # update TOP-10 in README:

    readme_top10 = generate_readme_top10(wiki_commit_dates, devices)
    print('-' * 100)
    print('\n'.join(readme_top10))
    print('-' * 100)

    new_readme = []
    top10_found = False
    in_top10 = False
    with readme_path.open('r') as f:
        for line in f:
            line = line.rstrip()
            if not in_top10:
                new_readme.append(line)
                if line == README_TOP10_HEADLINE:
                    top10_found = True
                    new_readme.append('')
                    new_readme += readme_top10
                    new_readme.append('')
                    in_top10 = True
            elif line.startswith('=='):
                new_readme.append(line)
                in_top10 = False

    assert top10_found, 'replace top10 in readme failed!'
    new_readme = '\n'.join(new_readme)
    # print(new_readme)
    with readme_path.open('w') as f:
        f.write(new_readme)


if __name__ == '__main__':
    generate_csv(
        csv_file_path=Path('.'),
        filename_template='device_info_{version}.csv',
        wiki_devices_path=Path('lineage_wiki/_data/devices'),
        lineageos_versions=LINEAGE_OS_VERSIONS,
        readme_path=Path('./README.creole'),
    )
    print()
    print('---END---')
