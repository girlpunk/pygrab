from __future__ import print_function

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
        tags = list(element.attrib)
        for child in element.getchildren():
            tags.append(child.tag)
        return tags

    @staticmethod
    def _static_string(element, channel, date):
        items = sorted(element.getchildren(), key=lambda x: x.attrib['order'])
        output = ""
        for item in items:
            if item.tag == "string":
                output += item.text.strip()
            elif item.tag == "siteid":
                output += channel.site_id
            elif item.tag == "date":
                output += datetime.datetime.strftime(date, item.text.strip())
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
    def _datetime_string(output, element):
        temp = []
        for x in output:
            temp.append(datetime.datetime.strptime(x, element.attrib['format']))
        return temp

    @staticmethod
    def _match_string(output, element):
        temp = []
        for x in output:
            if x == element.attrib['match']:
                temp.append(True)
            else:
                temp.append(False)
        return temp

    @staticmethod
    def _xpath_string(page, element, is_datetime, is_match, single):
        output = page.xpath(element.attrib['xpath'])
        if type(output) is not list:
            output = [output]
        if "regex" in Site._get_child_tags(element):
            output = Site._regex_string(output, element)
        if "ignore" in Site._get_child_tags(element):
            output = Site._ignore_string(output, element)
        if is_datetime:
            output = Site._datetime_string(output, element)
        if is_match:
            output = Site._match_string(output, element)
        if single:
            if is_match:
                output = any(output)
            elif len(output) >= 1:
                output = output[0]
            else:
                output = None
        return output

    @staticmethod
    def _extract_string(element, channel=None, date=datetime.datetime.now(), page=None, is_datetime=False, is_match=False, single=True):
        if any(x in Site._get_child_tags(element) for x in ["siteid", "string", "date"]):
            return Site._static_string(element, channel, date)
        elif "xpath" in Site._get_child_tags(element):
            return Site._xpath_string(page, element, is_datetime, is_match, single)

    @staticmethod
    def _extract_element(element, page, single=True):
        # check for container
        if "container" in Site._get_child_tags(element):
            page = Site._extract_element(element.find("container"), page)
        # find item
        output = page.xpath(element.attrib['xpath'])
        if single and type(output) == list:
            output = output[0]
        return output

    @staticmethod
    def _extract_star_rating(program_definition, channel, show, show_xml):
        raw_rating = Site._extract_string(program_definition.find("star-rating"), channel=channel, page=show)
        if raw_rating and not Site._extract_string(program_definition.find("star-rating").find("unrated"), is_match=True, channel=channel, page=show):
            etree.SubElement(show_xml, "star-rating").text = raw_rating + "/" + program_definition.find("star-rating").attrib["max"]

    @staticmethod
    def _extract_icon(program_definition, channel, show, show_xml):
        icon_url = Site._extract_string(program_definition.find("icon"), channel=channel, page=show)
        if icon_url:
            etree.SubElement(etree.SubElement(show_xml, "icon"), "url").text = icon_url

    @staticmethod
    def _extract_category(program_definition, channel, show, show_xml):
        categories = Site._extract_string(program_definition.find("category"), channel=channel, page=show, single=False)
        for category in categories:
            etree.SubElement(show_xml, "category").text = category

    @staticmethod
    def _extract_episode(program_definition, channel, show, show_xml):
        episode_number = Site._extract_string(program_definition.find("episode-num"), channel=channel, page=show)
        if episode_number:
            episode_tag = etree.SubElement(show_xml, "episode-num")
            episode_tag.text = episode_number
            number_system = Site._extract_string(program_definition.find("episode-num").find("system"), channel=channel, page=show)
            if number_system:
                episode_tag.attrib['system'] = number_system

    @staticmethod
    def _extract_subtitles(program_definition, channel, show, show_xml):
        enabled = Site._extract_string(program_definition.find("subtitles"), channel=channel, page=show, is_match=True)
        if enabled:
            subtitle_type = Site._extract_string(program_definition.find("subtitles").find("type"), channel=channel, page=show)
            if subtitle_type:
                etree.SubElement(show_xml, "subtitles").attrib['type'] = subtitle_type

    @staticmethod
    def _extract_xmltv(program_definition, channel, show, show_xml):
        for tag in program_definition.find("xmltv").getchildren():
            val = Site._extract_string(tag, channel, page=show)
            if val:
                etree.SubElement(show_xml, tag.tag).text = val

    def _extract_details(self, show, show_xml, channel, program_definition):
        program_tags = Site._get_child_tags(program_definition)
        if "start" in program_tags:
            # start time is in overview page
            self.start = Site._extract_string(program_definition.find("start"), channel=channel, page=show, is_datetime=True)

        if "stop" in program_tags:
            self.stop = Site._extract_string(program_definition.find("stop"), channel, page=show, is_datetime=True)

        if "star-rating" in program_tags:
            self._extract_star_rating(program_definition, channel, show, show_xml)

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
            self.parse(channel, data)
        else:
            logging.warning("WebGrab site files not currently supported")

    def parse_pygrab(self, channel, data):
        channel_xml = etree.SubElement(data, 'channel')
        channel_xml.attrib["id"] = channel.xmltvid

        day = datetime.datetime.today()

        base_url = self._extract_string(self.site_file.find("url"), channel=channel, date=day)
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
            channel_item.text = self._extract_string(item, channel, page=page)

        shows = self._extract_element(self.site_file.find("showsplit"), page, single=False)
        for show in shows:
            self._parse_show(data, channel, show, day)

    def _parse_show(self, data, channel, show, day):
            show_xml = etree.SubElement(data, 'program')
            show_xml.attrib["channel"] = channel.xmltvid

            self._extract_details(show, show_xml, channel, self.site_file.find("program"))
            detail_page_url = self._extract_string(self.site_file.find("program").find("detailurl"), channel, page=show)
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
