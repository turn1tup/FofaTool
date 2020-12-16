import base64
import json
import re
import time
import urllib.parse

import os
import requests
from math import ceil
from lib.utils import get_ip_port, is_number, format_header, record_error_page, BASE_DIR, strip_invalid_char
from lib.log import logger
requests.packages.urllib3.disable_warnings()
from scrapy.selector import Selector
class Fofa:
    def __init__(self, keyword, queue_in, conf):
        """

        :param session:
        :param keyword: 搜索词
        :param queue_in: 这里会另外对WEB站点发起请求，获取数据，这是该队列
        :param sleep_time: 避免被fofa屏蔽，每次查询的休眠时间
        :param result_per_page: 每页显示的个数，10或20
        """

        self.session = conf["fofa_session"]
        self.result_per_page = int(conf["result_per_page"])
        self.sleep_time = int(conf["sleep_time"])
        self.is_record_page = conf["is_record_page"].lower()
        self.is_record_page = True if self.is_record_page=='true' else False
        self.proxies = {}
        if conf.get("proxy"):
            self.proxies = {'http':conf['proxy'], 'https':conf['proxy']}
        self.queue_in = queue_in
        self.conf = conf
        self.keyword = keyword


        self.valid_keyword = strip_invalid_char(self.keyword)
        if len(self.valid_keyword) > 100:
            self.valid_keyword = self.valid_keyword[:100]

        self.page_amount = None
    def check_hint(self, text):
        """
        检查是否发生 <p>Retry Later. 请勿频繁刷新</p> 的错误
        :param text:
        :return:
        """
        retry_hint = "Retry Later."
        retry_hint_xpath = "/html/body/div/div/p"
        selector = Selector(text=text)
        r = selector.xpath(retry_hint_xpath)
        if r:
            hint = r.extract_first()
            if retry_hint in hint:
                return True
        return False


    def set_key_word(self, keyword):
        self.keyword = keyword

    def set_page_count(self, count):
        self.page_count = count

    @property
    def headers(self):
        return   {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36 OPR/52.0.2871.40',
            'Cookie': f'_fofapro_ars_session={self.session}; result_per_page={self.result_per_page}'
        }



    def get_page_amount(self):
        """
        获取页数
        :param key:
        :return:
        """
        if self.is_record_page:
            self.recover_page()

        if not self.check_page():
            return 'over'

        key_base64 = base64.b64encode(self.keyword.encode('utf-8')).decode()
        key_base64 = urllib.parse.quote(key_base64)
        url = f'https://fofa.so/result?page=1&qbase64={key_base64}'
        r = requests.get(url=url, headers=self.headers, verify=False)
        text = r.text
        while self.check_hint(text):
            logger.info("请求频率过快，休眠 %d"%(self.sleep_time*3))
            time.sleep(self.sleep_time*3)
            r = requests.get(url=url, headers=self.headers, verify=False)
            text = r.text

        selector = Selector(text=text)
        count_xpath = "//input[@type='hidden' and @name='total_entries' and @id='total_entries']/@value"
        try:
            self.amount_count = int(selector.xpath(count_xpath).extract_first())
            self.page_amount = ceil(self.amount_count / self.result_per_page)
            self.page_left = self.page_amount
            self.page_read = 0
        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            logger.error("[!]获取总页数错误 : %s"%record_error_page(r.content))
            exit(1)

    def get_page_url(self, count):
        key_base64 = base64.b64encode(self.keyword.encode('utf-8')).decode()
        key_base64 = urllib.parse.quote(key_base64)
        page_url = f'https://fofa.so/result?page={count}&qbase64={key_base64}'
        return page_url

    def get_data(self, xpath, selector):
        result = selector.xpath(xpath).extract()
        data = " ".join(result)
        return data

    def check_page(self):
        if self.page_amount:
            if self.page_amount==0:
                logger.info(f"无搜索结果，关键词{self.keyword}")
                return False
            elif self.page_read >= self.page_amount:
                logger.info("已经完成搜索，如果需要重复搜索，请删除或修改tmp目录下的历史纪录")
                return False
        return True

    def item_header(self):
        return ['item_count', 'host', 'ip','port','region', 'asn','org',  'time',  'title', 'link', 'server_tag',
                'protocol','ssl_domain',
                'cert', 'response']

    def next_page(self):

        # if self.is_record_page:
        #     self.recover_page()
        item_count = self.page_read * self.result_per_page
        if not self.check_page():
            return
        while True:
            host = ''
            self.page_read += 1
            self.page_left -= 1
            logger.info(f'[+]SUM :{self.page_amount}, Read : {self.page_read}, Left : {self.page_left}, sleep time:{self.sleep_time}s')
            result = ''
            target = self.get_page_url(self.page_read)
            r = requests.get(url=target, headers=self.headers, proxies=self.proxies, verify=False)
            text = r.text

            #检查是否存在发包过快
            while self.check_hint(text):
                logger.info("请求频率过快，休眠 %d s" % (self.sleep_time * 3))
                time.sleep(self.sleep_time * 3)
                r = requests.get(url=target, headers=self.headers, proxies=self.proxies, verify=False)
                text = r.text

            # 检查cookie是否有效
            if self.session not in str(r.cookies):
                logger.warning('[!]Cookie无效，请重新获取Cookie')
                return

            selector = Selector(text=text)

            # 每页有result_per_page条数据
            for i in range(1, self.result_per_page+1):
                def common_callback(xpath, selector):
                    result = selector.xpath(xpath).extract()
                    data = "\t".join(result)
                    yield data.strip()

                def time_callback(xpath, selector):
                    data = selector.xpath(xpath).extract()
                    if data:
                        data = data[-1]
                    yield data

                def port_callback(xpath, selector):
                    tags = selector.xpath(xpath)

                    for tag in tags:
                        tag = tag.xpath("text()").extract_first()
                        if is_number(tag):
                            yield tag

                def protocol_callback(xpath, selector):
                    protocol = []
                    tags = selector.xpath(xpath)
                    for tag in tags:
                        tag = tag.xpath("text()").extract_first()
                        if is_number(tag):
                            continue
                        protocol.append(tag)
                    yield ", ".join(protocol)

                def ssl_domain_callback(xpath, selector):
                    cert = selector.xpath(xpath).extract_first()
                    if not cert or not len(cert):
                        yield ''
                    else:
                        match = re.search(r'Subject:.+CommonName:\s*([^\s]+)', cert, re.S)
                        if not match:
                            yield ''
                        else:
                            yield match.groups()[0]

                def multi_callback(xpath, selector):
                    count = 0
                    while True:
                        count += 1
                        data = selector.xpath(f"{xpath}/div[{count}]")
                        if data:
                            datatype_xpath = f"{xpath}/div[{count}]/text()"
                            datatype = selector.xpath(datatype_xpath).extract_first()
                            if datatype:
                                datatype = datatype.strip()
                            value_xpath = f"{xpath}/div[{count}]/a/text()"
                            value = selector.xpath(value_xpath).extract_first()
                            if value:
                                value = value.strip()

                            if datatype == 'ASN:':
                                yield 'asn', value
                            elif datatype == '组织:':
                                yield 'org', value
                            elif datatype == None and value and re.search("\d+\.\d+\.\d+\.\d+", value):
                                yield 'ip', value
                            elif count > 1 and count <= 4 and isinstance(datatype, str) and not len(datatype):
                                yield 'region', value
                        else:
                            break

                xpath_item = [
                    ("multi", f"/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[1]", multi_callback),

                    ("time", f"/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[1]/div[@class='time']/text()",
                     time_callback),

                    ("title", f"/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[1]/div[2]/text()", common_callback),

                    (
                    "link", f"/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[1]/div[1]/a[@target='_blank']/text()",
                    common_callback),

                    ("host", f"/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[1]/div[@class='re-domain']/text()",
                     common_callback),

                    ("response", f"/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[2]/div[2]/div/div[1]/text()",
                     common_callback),
                    ("server_tag", f"/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[1]/div[8]/a/text()",
                     common_callback),
                    ("port", f"/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[2]/div[@class='re-port ar']/*",
                     port_callback),
                    ("protocol", f"/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[2]/div[@class='re-port ar']/*",
                     protocol_callback),
                    ("cert" , f"/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[2]/div[4]/text()",common_callback),
                    ("ssl_domain", f"/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[2]/div[4]/text()",
                     ssl_domain_callback),
                ]

                result_data = dict()
                for datatype, xpath, callback in xpath_item:
                    gen = callback(xpath, selector)
                    #            if isinstance(result, iterable):
                    for result in gen:
                        if isinstance(result, str):
                            result_data[datatype] = result
                        elif isinstance(result, tuple):
                            result_data[result[0]] = result[1]

                item_count += 1
                seq = item_count
                result_data['item_count'] = item_count

                # 这里认为到了最后一页的时候，如果只有几条数据才会出现空数据的情况
                if not result_data.get('port') and not result_data.get('protocol') and not result_data.get('response'):
                    if self.page_read != self.page_amount:
                        logger.info(f"空结果，如果超过一页出现该问题请确认Cookie是否有效，当前第{self.page_read}页")
                    continue


                proxies = self.proxies
                timeout = 3
                stop = False

                # 用于爬虫抓取web标题
                if self.queue_in:
                    self.queue_in.put([seq, result_data.get('ip'), result_data.get('port'), proxies, timeout, stop])

                if self.is_record_page:
                    self.record_page()

                yield  [result_data.get(i) for i in self.item_header()]

            if self.page_left <= 0:
                return
            time.sleep(self.sleep_time)

    def analyze_item(self, item):
        """
        根据需求，对获取到的数据进行进一步处理
        :param item:
        :return:
        """
        item_count, host, ip, port, region, asn, org, time, title, link, server_tag,protocol, ssl_domain,cert, \
        response = item
        fmt = format_header(response)
        if fmt:
            rsp_line, headers = fmt
        if not protocol:
            if link:
                if link.startswith("https://"):
                    protocol = "https"
                elif link.startswith("http://"):
                    protocol = "http"
        if not protocol:
            if response and response.startswith("HTTP"):
                protocol = "http"
        if not host and ip:
            host = ip
        return [item_count, host, ip, port, region, asn, org, time, title, link, server_tag,protocol, ssl_domain,cert,
                response]

    def record_page(self):
        path = os.path.join(BASE_DIR,"tmp")
        if not os.path.exists(path):
            os.mkdir(path)
        file = os.path.join(path, self.valid_keyword)
        with open(file, 'w', encoding="utf-8") as fw:
            data = {
                "page_amount":self.page_amount,
                "page_left":self.page_left,
                "page_read":self.page_read,
            }
            fw.write(json.dumps(data))

    def check_history_file(self):
        file = os.path.join(BASE_DIR, "tmp", self.valid_keyword)
        return os.path.exists(file)

    def recover_page(self):
        file = os.path.join(BASE_DIR, "tmp", self.valid_keyword)
        if not os.path.exists(file):
            return
        try:
            with open(file, 'r', encoding="utf-8") as fr:
                data = json.loads(fr.read())
                self.page_amount = data["page_amount"]
                self.page_left = data["page_left"]
                self.page_read = data["page_read"]
                logger.info(f"使用历史查询记录，总页数{self.page_amount}： ，已查询页:{self.page_read}，剩余查询页:{self.page_left}")
        except Exception:
            import traceback
            logger.warning(traceback.format_exc())
        # return self.check_page()