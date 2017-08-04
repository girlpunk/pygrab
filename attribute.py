import copy
import datetime


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
