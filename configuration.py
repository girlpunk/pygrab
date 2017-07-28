import requests
from lxml import etree

import logging

import postprocess
from channel import Channel


class Config(object):
    filename = ""
    mode = ""
    postprocess = []
    logging = ""
    timespan = ""
    update = ""
    skip_longer = 0
    skip_shorter = 0
    channels = []
    sites = {}

    def __init__(self, path="pygrab.config.xml"):
        xml = etree.parse(path)

        self.filename = xml.find("filename").text
        self.mode = xml.find("mode").text  # TODO: Find a use for this
        self.skip = xml.find("skip").text
        self.timespan = xml.find("timespan").text
        self.update = xml.find("update").text

        for postprocess_xml in xml.findall("postprocess"):
            self.postprocess = postprocess.Postprocess(postprocess_xml)

        if xml.find("proxy").text != "automatic":
            logging.warning("Custom proxies are not currently supported")  # TODO: proxy support

        if xml.find("logging").text != "on":
            logging.warning("Logging is always on in this version")  # TODO: Configurable logging

        self.headers = []
        if xml.find("headers"):
            for header in xml.find("headers").getchildren():
                self.headers[header.tag] = header.text

        if xml.find("skip") is not None and xml.find("skip").text != "noskip":
            self.skip_longer = xml.find("skip").split(",")[0]
            self.skip_shorted = xml.find("skip").split(",")[1]

        for channel_xml in xml.findall("channel"):
            self.channels.append(Channel(channel_xml, self))

    def get_session(self):
        session = requests.Session()
        if len(self.headers) > 0:
            session.headers.update(self.headers)

        return session
