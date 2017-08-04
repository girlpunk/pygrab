import datetime

import re

from attribute import Attribute


def extract_string(element, channel=None, date=datetime.datetime.now(), page=None):
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
        if any(x in get_child_tags(element) for x in ["siteid", "string", "date"]):
            return static_string(element, channel, date)
        elif "xpath" in get_child_tags(element):
            return xpath_string(page, element)


def get_child_tags(element):
    """

    :rtype: List[Union[str, unicode]]
    """
    tags = list(element.attrib)
    for child in element.getchildren():
        tags.append(child.tag)
    return tags


def static_string(element, channel, date):
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
                output.update(output.single(blank=True) + item.text.strip())
            elif item.tag == "siteid":
                output.update(output.single(blank=True) + channel.site_id)
            elif item.tag == "date":
                output.update(output.single(blank=True) + datetime.datetime.strftime(date, item.text.strip()))
        return output


def xpath_string(page, element):
        """ Extract a string for a page using xpath

        :param page: Page to extract from
        :param element: Config element containing xpath details
        :return: extracted attribute
        :rtype: Attribute
        """
        output = page.xpath(element.attrib['xpath'])
        if not isinstance(output, list):
            output = [output]
        if "regex" in get_child_tags(element):
            output = regex_string(output, element)
        if "ignore" in get_child_tags(element):
            output = ignore_string(output, element)
        return Attribute(output, element)


def regex_string(output, element):
        temp = []
        for x in output:
            try:
                temp.append(re.search(element.attrib['regex'], x).group())
            except AttributeError:
                pass
        return temp


def ignore_string(output, element):
        temp = []
        for x in output:
            if x != element.attrib['ignore']:
                temp.append(x)
        return temp
