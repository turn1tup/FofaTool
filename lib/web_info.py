import csv
import json
import queue
import re
import socket
import threading
import requests
import time
import urllib3
from openpyxl import Workbook
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_data(file):
    with open(file, 'r', encoding="utf-8") as fr:
        for line in fr:
            line = line.strip()
            yield line

def get_ip_port(url):
    if not url:
        raise Exception
    url = url.split("\t")[0]
    if "://" in url:
        match = re.search("https?://([^\:\\\/]+)(:(\d+))?", url)
        ip = match.groups()[0]
        port = 80
        if url.startswith("https"):
            port = 443
        if match.groups()[2]:
            port = match.groups()[2]

    else:
        url_s = url.split(":")
        ip = url_s[0]
        port = 80
        if len(url_s) >1:
            port = url_s[1]
    if len(url.split("\t")) > 1:
        port = int(url.split("\t")[1])
    return ip,int(port)


class WebInfo(threading.Thread):
    def __init__(self, queue_in, queue_out):
        threading.Thread.__init__(self)
        self.queue_in = queue_in
        self.queue_out = queue_out

    def run(self):
        while True:
            data = self.queue_in.get()
            seq, ip, port, proxies, timeout, stop = data
            if stop:
                break

            url = "http://%s:%d" % (ip, port)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:34.0) Gecko/20100101 Firefox/34.0",
            }
            try:
                rsp = requests.get(url=url, verify=False, proxies=proxies, timeout=timeout)
            except Exception as e:
                try:
                    if port == 80:
                        port = 443
                    url = "https://%s:%d" % (ip, port)
                    rsp = requests.get(url=url, verify=False, proxies=proxies, timeout=timeout, headers=headers)
                except Exception as e:
                    self.queue_out.put([seq, url, "","","", False])
                    # print([seq, url, "","","", False])
                    # [seq, url, rsp_ip, rsp_words, rsp_headers, stop]
                    continue
            rsp_words = None
            rsp_ip = socket.getaddrinfo(ip, None)[0][4][0]
            text = rsp.text
            match_charset = re.search("""<meta\s+charset=['"]*([\w\-]+)['"]*\s*\/?>""", rsp.text)
            if match_charset:
                charset = match_charset.groups()[0]
                try:
                    text = rsp.content.decode(encoding=charset)
                except LookupError:
                    pass

            rsp_headers = ""
            if rsp and rsp.headers:
                rsp_headers = str(rsp.headers)
                # rsp_headers = json.dumps(rsp.headers)
            if text:
                match = re.search("<title>(.+)</title>", text, re.I)
                if match:
                    rsp_words = match.groups()[0]
            if not rsp_words:
                rsp_words = rsp.text.split("\n")[0]
            if not url:
                url = ip

            self.queue_out.put((seq, url, rsp_ip, rsp_words, rsp_headers, False))
            # print([seq, url, rsp_ip, rsp_words, rsp_headers, False])


class WriteInfo(threading.Thread):
    def __init__(self, save_file, queue_out):
        threading.Thread.__init__(self)
        self.queue_out = queue_out
        self.save_file = save_file

    def run(self):
        # 创建一个Workbook对象
        #workbook = Workbook()
        # 获取当前活跃的sheet，默认是第一个sheet
        #sheet = workbook.active
        stop = False
        with open(self.save_file, 'w', encoding='utf-8') as fw:
            writer = csv.writer(fw)
            while not stop or not self.queue_out.empty():
                try:
                    data = self.queue_out.get_nowait()
                    seq, url, rsp_ip, rsp_words, rsp_headers, stop_ = data
                    # sheet.append([seq, url, rsp_ip, rsp_words, rsp_headers])
                    writer.writerow([seq, url, rsp_ip, rsp_words, rsp_headers])
                    # fw.flush()
                except Exception as e:
                    pass
                    #print(e)
                finally:
                    time.sleep(0.1)
                    stop = True
                    for t in threading.enumerate():
                        if isinstance(t, WebInfo):
                            stop = False


        #workbook.save(self.save_file)