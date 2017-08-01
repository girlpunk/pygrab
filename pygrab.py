#!/usr/bin/env python

import time

import datetime

import configuration
from lxml import etree


__version__ = "0.0.1"
__author__ = "Jacob Mansfield"

ELEMENT_ORDER_WEIGHTS = {
    # tv element
    "channel": 1,
    "programme": 2,

    # Programme element
    "title": 1,
    "sub-title": 2,
    "desc": 3,
    "credits": 4,
    "date": 5,
    "category": 6,
    "keyword": 7,
    "language": 8,
    "orig-language": 9,
    "length": 10,
    "icon": 11,
    "url": 12,
    "country": 13,
    "episode-num": 14,
    "video": 15,
    "audio": 16,
    "previously-shown": 17,
    "premiere": 18,
    "last-chance": 19,
    "new": 20,
    "subtitles": 21,
    "rating": 22,
    "star-rating": 23,
    "review": 24,
}


def __main__():
    config = configuration.Config()

    data = etree.Element("tv")
    data.attrib['generator-info-name'] = "PyGrab v"+__version__

    for channel in config.channels:
        print("\n{0} - {1}".format(datetime.datetime.now(), channel.name))
        config.sites[channel.site].parse(channel, data)
        time.sleep(config.sites[channel.site].channel_delay)

    for parent in data.xpath('//*[./*]'):
        # XLMTV is fussy about element order, so we'll sort everything here to make sure it's the right way round
        parent[:] = sorted(parent, key=lambda x: ELEMENT_ORDER_WEIGHTS[x.tag])

    data.getroottree().write(config.filename, pretty_print=True)

if __name__ == "__main__":
    __main__()
