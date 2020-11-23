# python38
# @Time : 2020/11/16 11:15 
# @Author : turn1tup
# @File : log.py

import logging

import os, datetime

from lib.utils import BASE_DIR

# logging.basicConfig(
#         level=logging.INFO,
#         format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
#         datefmt='%a, %d %b %Y %H:%M:%S'
#         )

import logging
from logging import handlers
# https://www.cnblogs.com/nancyzhu/p/8551506.html
class Logger(object):
    level_relations = {
        'debug':logging.DEBUG,
        'info':logging.INFO,
        'warning':logging.WARNING,
        'error':logging.ERROR,
        'crit':logging.CRITICAL
    }#日志级别关系映射

    def __init__(self,filename,level='info',when='D',backCount=3,fmt='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s'):
        self.logger = logging.getLogger(filename)
        format_str = logging.Formatter(fmt)#设置日志格式
        self.logger.setLevel(self.level_relations.get(level))#设置日志级别
        sh = logging.StreamHandler()#往屏幕上输出
        sh.setFormatter(format_str) #设置屏幕上显示的格式
        th = handlers.TimedRotatingFileHandler(filename=filename,when=when,backupCount=backCount,encoding='utf-8')#往文件里写入#指定间隔时间自动生成文件的处理器
        #实例化TimedRotatingFileHandler
        #interval是时间间隔，backupCount是备份文件的个数，如果超过这个个数，就会自动删除，when是间隔的时间单位，单位有以下几种：
        # S 秒
        # M 分
        # H 小时、
        # D 天、
        # W 每星期（interval==0时代表星期一）
        # midnight 每天凌晨
        th.setFormatter(format_str)#设置文件里写入的格式
        self.logger.addHandler(sh) #把对象加到logger里
        self.logger.addHandler(th)


save_dir = os.path.join(BASE_DIR, "log")
if not os.path.exists(save_dir):
    os.makedirs(save_dir)
file = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
file = "%s.log"%os.path.join(save_dir, file)

log = Logger(file,level='debug')
logger = log.logger
# try:
#     int("s")
# except:
#     import traceback
#     logger.error(traceback.format_exc())
#
# if __name__ == '__main__':
#     log.logger.debug('debug')
#     log.logger.info('info')
#     log.logger.warning('警告')
#     log.logger.error('报错')
#     log.logger.critical('严重')
#     Logger('error.log', level='error').logger.error('error')
