import datetime
import re

import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))


def get_ip_port(url):
    if not url:
        return url
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

def is_number(s):
    if not isinstance(s, str):
        raise Exception
    try:
        int(s)
        return True
    except:
        False

def strip_invalid_char(s):
    # 去除win非法字符
    for c in "\\/:*?\"<>|":
        s = s.replace(c, "")
    return s

def format_header(rsp_header):
    if not isinstance(rsp_header, str):
        raise Exception
    if not rsp_header.startswith("HTTP"):
        return
    ls = rsp_header.split("\n", 1)
    if len(ls) != 2:
        return
    rsp_line, headers_s = ls
    headers = dict()
    for header_filed in headers_s.split("\n"):
        sp = header_filed.split(":", 1)
        k = sp[0]
        if len(sp)>1:
            v = sp[1]
        if v:
            v = v.lstrip()
        headers[k] = v
    return (rsp_line, headers)

def record_error_page(page):
    assert isinstance(page, bytes)

    filename = "%s.html"%datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    save_path = os.path.join(BASE_DIR, "error_page")
    if not os.path.exists(save_path):
        os.makedirs(save_path)
    filename = os.path.join(save_path, filename)
    with open(filename, 'wb') as fw:
        fw.write(page)
    return filename
