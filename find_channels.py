import requests
import time
from lxml import etree

channel_url = "http://my.tvguide.co.uk/channellisting.asp?ch={0}&cTime=8/8/2017 1:00:00 PM&thisTime=&thisDay="

for channel_id in range(1827, 2000):
    try:
        time.sleep(0.5)
        page_request = requests.get(channel_url.format(channel_id))
        page_request.raise_for_status()
        page = etree.fromstring(page_request.content, parser=etree.HTMLParser())
        print(u"{0} - {1}".format(channel_id, page.xpath("//body/div[@id='site-container']/table/tr/td/table/tr/td/table/tr/td/span[@class='programmeheading']")[0].text))
        time.sleep(1)
    except IndexError:
        pass
