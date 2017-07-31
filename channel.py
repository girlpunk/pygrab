#!/usr/bin/env python

import sitefile


class Channel(object):
    def __init__(self, xml, config):
        if "site" in xml.attrib:
            self.basic = True
            self.site = xml.attrib['site']
            self.site_id = xml.attrib['site_id']
            self.update = xml.attrib['update']  # TODO: Something useful with this
            if self.site not in config.sites:
                config.sites[self.site] = sitefile.Site(self.site, config)
        else:
            self.basic = False
            self.offset = xml.attrib['offset']
            self.same_as = xml.attrib['same_as']
        self.xmltvid = xml.attrib['xmltv_id']
        self.name = xml.text
