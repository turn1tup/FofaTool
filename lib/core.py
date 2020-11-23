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

        key_base64 = base64.b64encode(self.keyword.encode('utf-8')).decode()
        key_base64 = urllib.parse.quote(key_base64)
        url = f'https://fofa.so/result?page=1&qbase64={key_base64}'
        r = requests.get(url=url, headers=self.headers, verify=False)
        text = r.text
        while self.check_hint(text):
            logger.info("请求频率过快，休眠 %d"%self.sleep_time*3)
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
        if self.page_read >= self.page_amount:
            logger.info("已经完成搜索，如果需要重复搜索请删除tmp目录下的历史纪录")
            raise Exception("已经完成搜索，如果需要重复搜索请删除tmp目录下的历史纪录")

    def next_page(self):

        if self.is_record_page:
            self.recover_page()
        item_count = self.page_read * self.result_per_page
        self.check_page()
        while True:
            host = ''
            self.page_read += 1
            self.page_left -= 1
            logger.info(f'[+]SUM :{self.page_amount}, Read : {self.page_read}, Left : {self.page_left}, sleep time:{self.sleep_time}s')
            result = ''
            target = self.get_page_url(self.page_read)
            r = requests.get(url=target, headers=self.headers, proxies=self.proxies, verify=False)
            text = r.text
            while self.check_hint(text):
                logger.info("请求频率过快，休眠 %d" % (self.sleep_time * 3))
                time.sleep(self.sleep_time * 3)
                r = requests.get(url=target, headers=self.headers, proxies=self.proxies, verify=False)
                text = r.text
            if self.session in str(r.cookies):
                result = True
            selector = Selector(text=text)
            if not result:
                logger.warning('[!]Cookie无效，请重新获取Cookie')
                raise Exception('[!]Cookie无效，请重新获取Cookie')
            # 每页有result_per_page条数据
            for i in range(1, self.result_per_page+1):

                for j in range(1, 3):
                    host_xpath = f'normalize-space(/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[1]/div[1]/a[{j}])'
                    host_result = self.get_data(host_xpath, selector)
                    if host_result:
                        host = host_result
                port_xpath = f'normalize-space(/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[2]/div[1]/a)'
                title_xpath = f'normalize-space(/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[1]/div[2])'
                header_xpath = f'normalize-space(/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[2]/div[2]/div/div[1])'
                certificate_xpath = f'normalize-space(/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[2]/div[4])'
                server_xpath = f'normalize-space(/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[1]/div[8]/a)'
                isp_xpath = f'normalize-space(/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[1]/div[6]/a)'
                port = self.get_data(port_xpath, selector)
                title = self.get_data(title_xpath, selector)
                header = self.get_data(header_xpath, selector)
                certificate = self.get_data(certificate_xpath, selector)
                server = self.get_data(server_xpath, selector)
                isp = self.get_data(isp_xpath, selector)
                if port:
                    port = int(port)
                ssl_domain = re.findall(r'(?<=CommonName: ).*(?=Subject Public)', certificate)
                ssl_domain = " ".join(ssl_domain).strip()

                try:
                    ssl_domain = ssl_domain.split(' CommonName: ')[1]
                except:
                    ssl_domain = ''
                if not ssl_domain and 'domain=' in header:
                    ssl_domain = re.findall(r'(?<=domain=).*(?=;)', header)
                    ssl_domain = " ".join(ssl_domain).strip()
                    ssl_domain = ssl_domain.split(';')[0]

                # 获取协议标签、端口等
                protocol = []
                tag_xpath = f"/html/body/div[1]/div[6]/div[1]/div[2]/div[{i}]/div[2]/div[@class='re-port ar']/*"
                tags = selector.xpath(tag_xpath)
                for tag in tags:
                    tag = tag.xpath("text()").extract_first()
                    if is_number(tag):
                        continue
                    protocol.append(tag)
                protocol = ", ".join(protocol)
                item_count += 1
                seq = item_count
                # 这里认为到了最后一页的时候，如果只有几条就会出现空数据的情况，但代码并不是完全预期去这样处理
                if not port and not protocol and not header:
                    if self.page_read != self.page_amount:
                        logger.info(f"空结果，确认Cookie是否有效，当前第{self.page_read}页")
                    continue
                try:
                    ip,foo = get_ip_port(host)
                except:
                    ip = host
                proxies = self.proxies
                timeout = 3
                stop = False
                if self.queue_in:
                    self.queue_in.put([seq, ip, port, proxies, timeout, stop])

                if self.is_record_page:
                    self.record_page()
                yield [item_count, host, port,protocol,  ssl_domain,  server, title, certificate, header]

            if self.page_left <= 0:
                return
            time.sleep(self.sleep_time)

    def analyze_item(self, item):
        """
        根据需求，对获取到的数据进行进一步处理
        :param item:
        :return:
        """
        item_count, host, port, protocol, ssl_domain, server, title, certificate, header = item
        fmt = format_header(header)
        if fmt:
            rsp_line, headers = fmt
            print(headers)
        if not protocol:

            if host:
                if host.startswith("https://"):
                    protocol = "https"
                elif host.startswith("http://"):
                    protocol = "http"
        if not protocol:
            if header and header.startswith("HTTP"):
                protocol = "http"

        return [item_count, host, port, protocol, ssl_domain, server, title, certificate, header]

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
            pass
        self.check_page()