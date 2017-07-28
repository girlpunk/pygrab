import time

import configuration
from lxml import etree


__version__ = "0.0.1"
__author__ = "Jacob Mansfield"


def __main__():
    config = configuration.Config()

    data = etree.Element("tv")
    data.attrib['generator-info-name'] = "PyGrab v"+__version__

    for channel in config.channels:
        print("\n{0}".format(channel.name))
        config.sites[channel.site].parse(channel, data)
        time.sleep(config.sites[channel.site].channeldelay)

    etree.dump(data)

if __name__ == "__main__":
    __main__()
