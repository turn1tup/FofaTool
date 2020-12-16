"""
修改 fofa_session keywords  即可
"""
import csv
import os
from queue import Queue
from openpyxl import Workbook
from lib.core import Fofa
from lib.log import logger
from lib.web_info import WriteInfo, WebInfo
from lib.utils import strip_invalid_char
from lib.config import parse_config

root_conf = parse_config("config.ini")

def main():


    keywords = root_conf["keywords"]
    conf = root_conf["conf"]
    is_get_title = conf["is_get_title"].lower()
    is_get_title = True if is_get_title == 'true' else False

    save_path = conf["save_path"]
    if not os.path.exists(save_path):
        os.makedirs(save_path)
    for keyword in keywords:
        # 队列用于发请求去获取web标题等数据
        queue_in = None
        if is_get_title == True:
            queue_in = Queue()
            queue_out = Queue()
            queue_out.put([-1, "", "", "", "", False])
        logger.info(f"[+]关键词 {keyword}")
        valid_keyword = strip_invalid_char(keyword)
        if len(valid_keyword)>100:
            valid_keyword = valid_keyword[:100]
        file_name = "%s.csv"%(valid_keyword)
        file_name_send = "%s_req.csv"%(valid_keyword)
        file_name = os.path.join(save_path, file_name)
        file_name_send = os.path.join(save_path, file_name_send)
        fw = open(file_name, 'a', encoding="utf-8")
        writer = csv.writer(fw)

        if is_get_title == True :
            req_threads = []
            threads_count = 30
            for i in range(threads_count):
                t = WebInfo(queue_in,queue_out)
                req_threads.append(t)
            for t in req_threads:
                t.start()
            record_thread = WriteInfo(file_name_send, queue_out)
            record_thread.start()

        fofa = Fofa( keyword, queue_in, conf)
        fofa.get_page_amount()
        if not fofa.check_history_file():
            #writer.writerow(   ["seq", "host", "port", "protocol", "ssl_domain", "server", "title", "certificate",
            # "fofa_header"] )
            fw.flush()
            writer.writerow(   fofa.item_header() )
        for item in fofa.next_page():
            item = fofa.analyze_item(item)
            writer.writerow(item)
            fw.flush()

        fw.close()
        if is_get_title == True:
            logger.info("waiting 获取标题")
            for i in range(threads_count):
                queue_in.put([-1,"" ,"" ,"" ,"" , True])
            #queue_out.put([-1, "", "", "", "", True])
            for t in req_threads:
                t.join()
            record_thread.join()
            logger.info("finished 获取标题")

if __name__ == '__main__':
    # ip=101.89.95.024_req
    try:
        main()
    except:
        import traceback
        print(traceback.print_exc())
        logger.error(traceback.format_exc())