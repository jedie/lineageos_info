#!/usr/bin/env python3

"""
    Convert the Wiki pages:
        https://wiki.lineageos.org/devices/

    use the git sources from:
        https://github.com/LineageOS/lineage_wiki.git
    via git submodule, see:
        https://github.com/jedie/lineageos_info/blob/master/.gitmodules

    more info in README, see:
        https://github.com/jedie/lineageos_info#readme

    created 28.12.2018 by Jens Diemer
"""

import csv
import datetime
import logging
import re
from pathlib import Path
from pprint import pprint

# https://pyyaml.org/wiki/PyYAMLDocumentation
from yaml import Loader, load

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

log.addHandler(logging.FileHandler("device_info.log", mode="w", encoding="UTF-8"))


INFO_TEMPLATE = """{vendor} {name} - https://wiki.lineageos.org/devices/{codename}"""


class CsvGenerator:
    HEADER_VENDOR = "vendor"
    HEADER_NAME = "name"
    HEADER_MAINTAINERS = "maintainers"
    HEADER_REMOVEABLE_BATTERY = "removable battery"
    HEADER_RELEASE = "release"
    HEADER_SCREEN = "screen"
    HEADER_MODELS = "models"
    HEADER_RAM = "RAM"
    HEADER_STORAGE = "storage"
    HEADER_SOC = "SOC"

    HEADER_WIKI_LINK = "Wiki Link"

    def __init__(self, *, csv_file):

        self.csv_file = csv_file

        fieldnames = [
            self.HEADER_VENDOR,
            self.HEADER_NAME,
            self.HEADER_MAINTAINERS,
            self.HEADER_REMOVEABLE_BATTERY,
            self.HEADER_RELEASE,
            self.HEADER_SCREEN,
            self.HEADER_MODELS,
            self.HEADER_RAM,
            self.HEADER_STORAGE,
            self.HEADER_SOC,
            self.HEADER_WIKI_LINK,
        ]

        self.csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        self.csv_writer.writeheader()

    def add_device(self, device):

        row = {
            self.HEADER_VENDOR: device["vendor_short"],
            self.HEADER_NAME: device["name"],
            self.HEADER_MAINTAINERS: len(device["maintainers"]),
            self.HEADER_REMOVEABLE_BATTERY: device["removable_battery"],
            self.HEADER_RELEASE: device["release"],
            self.HEADER_SCREEN: device["screen"],
            self.HEADER_MODELS: ",".join([x for x in device.get("models", "")]),
            self.HEADER_RAM: device["ram"],
            self.HEADER_STORAGE: device["storage"],
            self.HEADER_SOC: device["soc"],
            self.HEADER_WIKI_LINK: "https://wiki.lineageos.org/devices/%s" % device["codename"],
        }
        self.csv_writer.writerow(row)


def generate_csv(*, csv_file_path, wiki_devices_path):
    assert isinstance(csv_file_path, Path)
    assert isinstance(wiki_devices_path, Path)

    print("Read WIKI divice files from: %s" % wiki_devices_path)
    assert wiki_devices_path.is_dir(), "ERROR: Path not found: %s" % wiki_devices_path

    csv_file_path = csv_file_path.resolve()

    print("Generate: %s" % csv_file_path)
    log.info("Generate csv on %s+0000", datetime.datetime.utcnow())

    with csv_file_path.open("w") as csv_file:
        csv_generator = CsvGenerator(csv_file=csv_file)

        for item in wiki_devices_path.iterdir():
            # print(item)

            with item.open("r", encoding="utf-8") as ymlfile:
                device = load(ymlfile, Loader=Loader)

            short_name = "{vendor_short} {name}".format(**device)

            maintainers = device["maintainers"]
            if not maintainers:
                log.info("Skip %r: no maintainers.", short_name)
                continue

            versions = device["versions"]
            if not 16 in versions:
                log.info("Skip %r: only: %r", short_name, versions)
                continue

            ram = device["ram"]
            if ram in ("1 GB", "2 GB"):
                log.info("Skip %r: RAM only: %r", short_name, ram)
                continue

            storage = device["storage"]
            if storage in ("8 GB", "16 GB"):
                log.info("Skip %r: Storage only: %r", short_name, storage)
                continue

            screen = device["screen"]
            if screen:
                try:
                    inches = re.findall(".*?([\d\.]+) in.*?", screen)[0]
                except IndexError:
                    pass
                else:
                    device["screen"] = inches

            removable_battery = "???"
            battery = device.get("battery")
            if not battery:
                log.warning("Device %r hat no 'battery' entry!" % short_name)
            else:
                # Most wiki entry has only one battery entry...
                # But e.g.: Device 'oneplus 3 / 3T' has:
                # [
                #   {3: {'removable': False, 'capacity': 3000, 'tech': 'Li-Ion'}},
                #   {'3T': {'removable': False, 'capacity': 3400, 'tech': 'Li-Ion'}}
                # ]
                # Just convert to a list and join the result ;)
                if not isinstance(battery, list):
                    battery = [battery]

                try:
                    removable_battery = "/".join([get_removeable_info(short_name, b) for b in battery])
                except Exception:
                    # e.g.:
                    # oppo Find 7a/s {'Find 7a': {'removable': True, 'capacity': 2800, 'tech': 'Li-Po', 'fastcharge': True}}
                    removable_battery=" ".join([repr(i) for i in battery])
                    log.error("Error parsing battery info from %r: %s", short_name, removable_battery)

            device["removable_battery"] = removable_battery

            print(INFO_TEMPLATE.format(**device))
            csv_generator.add_device(device)

            # pprint(device)

    print("\n *** File generated: %s ***\n" % csv_file_path)


def get_removeable_info(short_name, battery):
    # print(short_name, battery)

    if battery == "None":
        # e.g.: nvidia Shield Android TV has no battery ;)
        return "-"

    convert = {None: "-", True: "yes", False: "no"}
    removable = battery["removable"]
    removable_battery = convert[removable]

    return removable_battery


if __name__ == "__main__":
    generate_csv(csv_file_path=Path("device_info.csv"), wiki_devices_path=Path("lineage_wiki/_data/devices"))
