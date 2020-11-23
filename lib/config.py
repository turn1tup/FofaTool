from configparser import ConfigParser

from lib.log import logger


def parse_config(config_file):
    config = ConfigParser()
    fp = open(config_file, encoding="utf-8")
    keywords = list()
    is_first = True
    read_sum = 0
    for line in fp:
        # print(line)
        read_sum += 1
        line = line.strip()
        if is_first:
            is_first = False
            if line!="[keywords]":
                raise Exception("配置文件必须以[keywords]开头")
            continue
        elif line.startswith("[") and line.endswith("]"):
            read_sum -= 1
            break
        if not line:
            continue

        if line.startswith(";") or line.startswith("#"):
            continue
        if line in keywords:
            logger.warning("关键词重复，忽略该关键词%s"%line)
            continue
        keywords.append(line)
    if not len(keywords):
        raise Exception("搜索关键词不能为空")
    fp.close()
    fp = open(config_file, encoding="utf-8")
    for i in range(read_sum):
        fp.readline()

    config.read_file(fp)
    #config.read(config_file, encoding="utf-8")
    assert not config.has_section("keywords")
    assert config.has_section("conf")
    d = {}
    for section in config:
        d[section] = {}
        for k in config[section].keys():
            d[section][k] = config[section].get(k)


    # for k,v in d["keywords"].items():
    #     keywords.append(f"{k}=f{v}")
    d["keywords"] = keywords
    return d


if __name__ == '__main__':
    d = parse_config("../config.ini")
    print(d)

