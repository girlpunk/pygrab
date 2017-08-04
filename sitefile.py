#!/usr/bin/env python

from __future__ import print_function

import datetime
import logging
import os.path
import time

import pytz
import requests
from lxml import etree

from extract import extract_string, get_child_tags

MODE_PYGRAB = "pygrab"
MODE_WEBGRAB = "webgrab"


class Site(object):
    def __init__(self, name, config):
        self.name = name
        self.config = config

        self.retry = 0
        self.timeout = 10
        self.channel_delay = 0
        self.index_delay = 0
        self.show_delay = 0

        self.mode = None
        self.site_file = None
        self.timezone = None
        self.session = None

        if os.path.isfile(name + ".pyg"):
            self.pygrab_setup()
        elif os.path.isfile(name + ".ini"):
            self.webgrab_setup()
        else:
            logging.error("Unknown site " + name)

    def pygrab_setup(self):
        self.mode = MODE_PYGRAB
        self.site_file = etree.parse(self.name + ".pyg")

        self.timezone = pytz.timezone(self.site_file.find("site").find("timezone").text)
        self.session = self.config.get_session()

        retry_data = self.site_file.find("site").find("retry")
        self.retry = int(retry_data.text)
        if "time-out" in retry_data.attrib:
            self.timeout = int(retry_data.attrib['time-out'])
        if "channel-delay" in retry_data.attrib:
            self.channel_delay = int(retry_data.attrib['channel-delay'])
        if "index-delay" in retry_data.attrib:
            self.index_delay = int(retry_data.attrib['index-delay'])
        if "show-delay" in retry_data.attrib:
            self.show_delay = int(retry_data.attrib['show-delay'])

        logging.debug("Loading " + self.name + ".pyg")

    def webgrab_setup(self):
        self.mode = MODE_WEBGRAB

    @staticmethod
    def _extract_element(element, page, single=True):
        # check for container
        if "container" in get_child_tags(element):
            page = Site._extract_element(element.find("container"), page)
        # find item
        output = page.xpath(element.attrib['xpath'])
        if single and isinstance(output, list):
            output = output[0]
        return output

    @staticmethod
    def _extract_star_rating(program_definition, channel, show, show_xml):
        raw_rating = extract_string(program_definition.find("star-rating"), channel=channel, page=show)
        if raw_rating and not extract_string(program_definition.find("star-rating").find("unrated"), channel=channel, page=show).match().single():
            try:
                rounded_rating = str(round(float(raw_rating.single()), 0))
            except (TypeError, ValueError):
                rounded_rating = raw_rating.single()
            etree.SubElement(etree.SubElement(show_xml, "star-rating"), "value").text = rounded_rating + " / " + program_definition.find("star-rating").attrib["max"]

    @staticmethod
    def _extract_rating(program_definition, channel, show, show_xml):
        raw_rating = extract_string(program_definition.find("rating"), channel=channel, page=show)
        if raw_rating:
            etree.SubElement(etree.SubElement(show_xml, "rating"), "value").text = raw_rating.single()

    @staticmethod
    def _extract_icon(program_definition, channel, show, show_xml):
        icon_url = extract_string(program_definition.find("icon"), channel=channel, page=show).single()
        if icon_url:
            etree.SubElement(show_xml, "icon").attrib['src'] = icon_url

    @staticmethod
    def _extract_category(program_definition, channel, show, show_xml):
        categories = extract_string(program_definition.find("category"), channel=channel, page=show).multiple()
        for category in categories:
            etree.SubElement(show_xml, "category").text = category

    @staticmethod
    def _extract_episode(program_definition, channel, show, show_xml):
        episode_number = extract_string(program_definition.find("episode-num"), channel=channel, page=show)
        if episode_number:
            episode_tag = etree.SubElement(show_xml, "episode-num")
            episode_tag.text = episode_number.single()
            number_system = extract_string(program_definition.find("episode-num").find("system"), channel=channel, page=show)
            if number_system:
                episode_tag.attrib['system'] = number_system.single()

    @staticmethod
    def _extract_subtitles(program_definition, channel, show, show_xml):
        enabled = extract_string(program_definition.find("subtitles"), channel=channel, page=show).match().single()
        if enabled:
            subtitle_type = extract_string(program_definition.find("subtitles").find("type"), channel=channel, page=show)
            if subtitle_type:
                etree.SubElement(show_xml, "subtitles").attrib['type'] = subtitle_type.single()

    @staticmethod
    def _extract_xmltv(program_definition, channel, show, show_xml):
        for tag in program_definition.find("xmltv").getchildren():
            val = extract_string(tag, channel, page=show)
            if val:
                etree.SubElement(show_xml, tag.tag).text = val.single()

    @staticmethod
    def _extract_previously_shown(program_definition, channel, show, show_xml):
        previously_shown = extract_string(program_definition.find("previously-shown"), channel=channel, page=show).match().single()
        if previously_shown:
            etree.SubElement(show_xml, "previously-shown")

    def _extract_details(self, show, show_xml, channel, program_definition):
        program_tags = get_child_tags(program_definition)
        if "start" in program_tags:
            # start time is in overview page
            self.start = extract_string(program_definition.find("start"), channel=channel, page=show).datetime().single()

        if "stop" in program_tags:
            self.stop = extract_string(program_definition.find("stop"), channel, page=show).datetime().single()

        if "star-rating" in program_tags:
            self._extract_star_rating(program_definition, channel, show, show_xml)

        if "rating" in program_tags:
            self._extract_rating(program_definition, channel, show, show_xml)

        if "icon" in program_tags:
            self._extract_icon(program_definition, channel, show, show_xml)

        if "category" in program_tags:
            self._extract_category(program_definition, channel, show, show_xml)

        if "episode-num" in program_tags:
            self._extract_episode(program_definition, channel, show, show_xml)

        if "subtitles" in program_tags:
            self._extract_subtitles(program_definition, channel, show, show_xml)

        if "previously-shown" in program_tags:
            self._extract_previously_shown(program_definition, channel, show, show_xml)

        if "xmltv" in program_tags:
            self._extract_xmltv(program_definition, channel, show, show_xml)

    def parse(self, channel, data):
        if self.mode == MODE_PYGRAB:
            self.parse_pygrab(channel, data)
        else:
            logging.warning("WebGrab site files not currently supported")

    def parse_pygrab(self, channel, data):
        channel_xml = etree.SubElement(data, 'channel')
        channel_xml.attrib["id"] = channel.xmltvid

        day = datetime.datetime.today()

        base_url = extract_string(self.site_file.find("url"), channel=channel, date=day).single()
        page = self.load_page_html(base_url, self.session, self.retry, self.timeout)
        print("i", end='')

        for item in self.site_file.find("xmltv").getchildren():
            channel_item = etree.SubElement(channel_xml, item.tag)
            channel_item.text = extract_string(item, channel, page=page).single()

        self._extract_icon(self.site_file, show=page, channel=channel, show_xml=channel_xml)

        shows = self._extract_element(self.site_file.find("showsplit"), page, single=False)
        for show in shows:
            self._parse_show(data, channel, show, day)

    def _parse_show(self, data, channel, show, day):
        show_xml = etree.SubElement(data, 'programme')
        show_xml.attrib["channel"] = channel.xmltvid

        self._extract_details(show, show_xml, channel, self.site_file.find("program"))
        detail_page_url = extract_string(self.site_file.find("program").find("detailurl"), channel, page=show).single()
        if detail_page_url:
            self._parse_show_details(detail_page_url, show_xml, channel)

        show_xml.attrib['start'] = self.timezone.localize(datetime.datetime.combine(day.date(), self.start.time())).strftime("%Y%m%d%H%M%S %z")
        show_xml.attrib['stop'] = self.timezone.localize(datetime.datetime.combine(day.date(), self.stop.time())).strftime("%Y%m%d%H%M%S %z")

        time.sleep(self.show_delay)

    def _parse_show_details(self, detail_page_url, show_xml, channel):
        detail_page = self.load_page_html(detail_page_url, self.session, self.retry, self.timeout)
        print(".", end='')

        self._extract_details(detail_page, show_xml, channel, self.site_file.find("program").find("detail"))

    @staticmethod
    def load_page_html(page_url, session, retry, timeout):
        retry_limit = int(retry)
        while retry_limit > 0:
            try:
                detail_page_request = session.get(page_url, timeout=timeout)
                detail_page_request.raise_for_status()
                return etree.fromstring(detail_page_request.content, parser=etree.HTMLParser())
            except requests.exceptions.RequestException as e:
                retry_limit -= 1
                print("r", end='')
                time.sleep(((retry - retry_limit) + 1) * timeout)
        else:
            # noinspection PyUnboundLocalVariable
            raise e
