#!/usr/bin/env python

from __future__ import print_function

import copy
import datetime
import logging
import os.path
import re
import time

import pytz
import requests
from lxml import etree

MODE_PYGRAB = "pygrab"
MODE_WEBGRAB = "webgrab"


class Attribute(object):
    def __init__(self, value, element=None):
        """

        :type value: Union[str, unicode, list]
        :type element: lxml.etree.Element
        """
        if len(value) > 0:
            if isinstance(value, list):
                self.val = value
            else:
                self.val = [value]
        else:
            self.val = []
        self.element = element
        self.is_match = False

    def update(self, value, element=None):
        """

        :param element:
        :type value: Union[str, unicode, list]
        :rtype: Attribute
        """
        if not isinstance(value, list):
            self.val = [value]
        else:
            self.val = value
        if self.element is not None:
            self.element = element
        return self
    
    def append(self, value):
        """

        :type value: Union[str, unicode, list]
        :rtype: Attribute
        """
        if not isinstance(value, list):
            self.val.append(value)
        else:
            self.val += value
        return self
    
    def datetime(self, element=None):
        """

        :rtype: Attribute
        """
        if not element:
            element = self.element
            
        temp = []
        for x in self.val:
            temp.append(datetime.datetime.strptime(x, element.attrib['format']))
        self.val = copy.copy(temp)
        
        return self
    
    def match(self, element=None):
        """

        :rtype: Attribute
        """
        if not element:
            element = self.element
        self.is_match = True
            
        temp = []
        for x in self.val:
            if x == element.attrib['match']:
                temp.append(True)
            else:
                temp.append(False)
        self.val = copy.copy(temp)
        
        return self
    
    def single(self, blank=False):
        """

        :rtype: Union[str, unicode, bool]
        """
        if self.is_match:
            return any(self.val)
        elif len(self.val) >= 1:
            return self.val[0]
        elif blank:
            return ""
        else:
            return None

    def multiple(self):
        """

        :return: List of values
        :rtype: list
        """
        return self.val


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

        if os.path.isfile(name+".pyg"):
            self.pygrab_setup()
        elif os.path.isfile(name+".ini"):
            self.webgrab_setup()
        else:
            logging.error("Unknown site "+name)

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

        logging.debug("Loading "+self.name+".pyg")

    def webgrab_setup(self):
        self.mode = MODE_WEBGRAB

    @staticmethod
    def _get_child_tags(element):
        """

        :rtype: List[Union[str, unicode]]
        """
        tags = list(element.attrib)
        for child in element.getchildren():
            tags.append(child.tag)
        return tags

    @staticmethod
    def _static_string(element, channel, date):
        """

        :param element:
        :param channel:
        :param date:
        :return:
        :rtype: Attribute
        """
        items = sorted(element.getchildren(), key=lambda x: x.attrib['order'])
        output = Attribute("", element)
        for item in items:
            if item.tag == "string":
                output.update(output.single(blank=True)+item.text.strip())
            elif item.tag == "siteid":
                output.update(output.single(blank=True)+channel.site_id)
            elif item.tag == "date":
                output.update(output.single(blank=True)+datetime.datetime.strftime(date, item.text.strip()))
        return output

    @staticmethod
    def _regex_string(output, element):
        temp = []
        for x in output:
            try:
                temp.append(re.search(element.attrib['regex'], x).group())
            except AttributeError:
                pass
        return temp

    @staticmethod
    def _ignore_string(output, element):
        temp = []
        for x in output:
            if x != element.attrib['ignore']:
                temp.append(x)
        return temp

    @staticmethod
    def _xpath_string(page, element):
        """ Extract a string for a page using xpath

        :param page: Page to extract from
        :param element: Config element containing xpath details
        :return: extracted attribute
        :rtype: Attribute
        """
        output = page.xpath(element.attrib['xpath'])
        if not isinstance(output, list):
            output = [output]
        if "regex" in Site._get_child_tags(element):
            output = Site._regex_string(output, element)
        if "ignore" in Site._get_child_tags(element):
            output = Site._ignore_string(output, element)
        return Attribute(output, element)

    @staticmethod
    def _extract_string(element, channel=None, date=datetime.datetime.now(), page=None):
        """ Extract a string for a page

        :param element: Config element containing details
        :param channel:
        :type channel: channel.Channel
        :param date:
        :type date: datetime.datetime
        :param page:
        :return: Extracted attribute
        :rtype: Attribute
        """
        if any(x in Site._get_child_tags(element) for x in ["siteid", "string", "date"]):
            return Site._static_string(element, channel, date)
        elif "xpath" in Site._get_child_tags(element):
            return Site._xpath_string(page, element)

    @staticmethod
    def _extract_element(element, page, single=True):
        # check for container
        if "container" in Site._get_child_tags(element):
            page = Site._extract_element(element.find("container"), page)
        # find item
        output = page.xpath(element.attrib['xpath'])
        if single and isinstance(output, list):
            output = output[0]
        return output

    @staticmethod
    def _extract_star_rating(program_definition, channel, show, show_xml):
        raw_rating = Site._extract_string(program_definition.find("star-rating"), channel=channel, page=show)
        if raw_rating and not Site._extract_string(program_definition.find("star-rating").find("unrated"), channel=channel, page=show).match().single():
            etree.SubElement(etree.SubElement(show_xml, "star-rating"), "value").text = raw_rating.single() + "/" + program_definition.find("star-rating").attrib["max"]

    @staticmethod
    def _extract_rating(program_definition, channel, show, show_xml):
        raw_rating = Site._extract_string(program_definition.find("rating"), channel=channel, page=show)
        if raw_rating:
            etree.SubElement(etree.SubElement(show_xml, "rating"), "value").text = raw_rating.single()

    @staticmethod
    def _extract_icon(program_definition, channel, show, show_xml):
        icon_url = Site._extract_string(program_definition.find("icon"), channel=channel, page=show).single()
        if icon_url:
            etree.SubElement(show_xml, "icon").attrib['src'] = icon_url

    @staticmethod
    def _extract_category(program_definition, channel, show, show_xml):
        categories = Site._extract_string(program_definition.find("category"), channel=channel, page=show).multiple()
        for category in categories:
            etree.SubElement(show_xml, "category").text = category

    @staticmethod
    def _extract_episode(program_definition, channel, show, show_xml):
        episode_number = Site._extract_string(program_definition.find("episode-num"), channel=channel, page=show)
        if episode_number:
            episode_tag = etree.SubElement(show_xml, "episode-num")
            episode_tag.text = episode_number.single()
            number_system = Site._extract_string(program_definition.find("episode-num").find("system"), channel=channel, page=show)
            if number_system:
                episode_tag.attrib['system'] = number_system.single()

    @staticmethod
    def _extract_subtitles(program_definition, channel, show, show_xml):
        enabled = Site._extract_string(program_definition.find("subtitles"), channel=channel, page=show).match().single()
        if enabled:
            subtitle_type = Site._extract_string(program_definition.find("subtitles").find("type"), channel=channel, page=show)
            if subtitle_type:
                etree.SubElement(show_xml, "subtitles").attrib['type'] = subtitle_type.single()

    @staticmethod
    def _extract_xmltv(program_definition, channel, show, show_xml):
        for tag in program_definition.find("xmltv").getchildren():
            val = Site._extract_string(tag, channel, page=show)
            if val:
                etree.SubElement(show_xml, tag.tag).text = val.single()

    def _extract_details(self, show, show_xml, channel, program_definition):
        program_tags = Site._get_child_tags(program_definition)
        if "start" in program_tags:
            # start time is in overview page
            self.start = Site._extract_string(program_definition.find("start"), channel=channel, page=show).datetime().single()

        if "stop" in program_tags:
            self.stop = Site._extract_string(program_definition.find("stop"), channel, page=show).datetime().single()

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

        base_url = self._extract_string(self.site_file.find("url"), channel=channel, date=day).single()
        retry_limit = int(self.retry)
        while retry_limit > 0:
            try:
                page_request = self.session.get(base_url, timeout=self.timeout)
                page_request.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                retry_limit -= 1
                print("r", end='')
                time.sleep(((self.retry-retry_limit)+1)*self.timeout)
        else:
            # noinspection PyUnboundLocalVariable
            raise e
        page = etree.fromstring(page_request.content, parser=etree.HTMLParser())
        print("i", end='')

        for item in self.site_file.find("xmltv").getchildren():
            channel_item = etree.SubElement(channel_xml, item.tag)
            channel_item.text = self._extract_string(item, channel, page=page).single()

        self._extract_icon(self.site_file, show=page, channel=None, show_xml=channel_xml)

        shows = self._extract_element(self.site_file.find("showsplit"), page, single=False)
        for show in shows:
            self._parse_show(data, channel, show, day)

    def _parse_show(self, data, channel, show, day):
            show_xml = etree.SubElement(data, 'programme')
            show_xml.attrib["channel"] = channel.xmltvid

            self._extract_details(show, show_xml, channel, self.site_file.find("program"))
            detail_page_url = self._extract_string(self.site_file.find("program").find("detailurl"), channel, page=show).single()
            if detail_page_url:
                retry_limit = int(self.retry)
                while retry_limit > 0:
                    try:
                        detail_page_request = self.session.get(detail_page_url, timeout=self.timeout)
                        detail_page_request.raise_for_status()
                        break
                    except requests.exceptions.RequestException as e:
                        retry_limit -= 1
                        print("r", end='')
                        time.sleep(((self.retry-retry_limit)+1)*self.timeout)
                else:
                    # noinspection PyUnboundLocalVariable
                    raise e
                detail_page = etree.fromstring(detail_page_request.content, parser=etree.HTMLParser())
                print(".", end='')

                self._extract_details(detail_page, show_xml, channel, self.site_file.find("program").find("detail"))

            show_xml.attrib['start'] = pytz.utc.localize(datetime.datetime.combine(day.date(), self.start.time())).astimezone(self.timezone).strftime("%Y%m%d%I%M%S %z")
            show_xml.attrib['stop'] = pytz.utc.localize(datetime.datetime.combine(day.date(), self.stop .time())).astimezone(self.timezone).strftime("%Y%m%d%I%M%S %z")

            time.sleep(self.show_delay)
