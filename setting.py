# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：     setting.py
   Description :   配置文件
   Author :        JHao
   date：          2019/2/15
-------------------------------------------------
   Change Activity:
                   2019/2/15:
-------------------------------------------------
"""

BANNER = r"""
****************************************************************
*** ______  ********************* ______ *********** _  ********
*** | ___ \_ ******************** | ___ \ ********* | | ********
*** | |_/ / \__ __   __  _ __   _ | |_/ /___ * ___  | | ********
*** |  __/|  _// _ \ \ \/ /| | | ||  __// _ \ / _ \ | | ********
*** | |   | | | (_) | >  < \ |_| || |  | (_) | (_) || |___  ****
*** \_|   |_|  \___/ /_/\_\ \__  |\_|   \___/ \___/ \_____/ ****
****                       __ / /                          *****
************************* /___ / *******************************
*************************       ********************************
****************************************************************
"""

VERSION = "2.6.0"

# ############### server config ###############
HOST = "0.0.0.0"

PORT = 5010

# ############### database config ###################
# db connection uri
# example:
#      Redis: redis://:password@ip:port/db
#      Ssdb:  ssdb://:password@ip:port
DB_CONN = 'redis://:pwdstring@127.0.0.1:6379/0'

# proxy table name
TABLE_NAME = 'use_proxy'


# ###### config the proxy fetch function ######
# 自动扫描 fetcher/sources/ 目录，加载所有 enabled=True 的 fetcher
# 如需临时禁用某个 fetcher，在下方黑名单中添加类名（不改源文件）
PROXY_FETCHER_EXCLUDE = []

# ############# proxy validator #################
# 代理验证目标网站
HTTP_URL = "http://httpbin.org"

HTTPS_URL = "https://www.qq.com"

# 代理验证时超时时间
VERIFY_TIMEOUT = 10

# 近PROXY_CHECK_COUNT次校验中允许的最大失败次数,超过则剔除代理
MAX_FAIL_COUNT = 0

# 近PROXY_CHECK_COUNT次校验中允许的最大失败率,超过则剔除代理
# MAX_FAIL_RATE = 0.1

# proxyCheck时代理数量少于POOL_SIZE_MIN触发抓取
POOL_SIZE_MIN = 20

# ############# proxy attributes #################
# 是否启用代理地域属性
PROXY_REGION = True

# ############# proxy strategy config #################
# 默认代理更换方式，可选：random / round_robin / weighted
# random:       随机选择
# round_robin:  轮询选择
# weighted:     按校验成功率加权随机
PROXY_STRATEGY = "random"

# ############# gateway config #################
# 稳定代理池网关：客户端把 GATEWAY_HOST:GATEWAY_PORT 当作 HTTP 代理使用，
# 网关会按策略自动选择/更换上游代理。
GATEWAY_ENABLED = True

GATEWAY_HOST = "0.0.0.0"

GATEWAY_PORT = 5011

# 网关默认代理更换方式，取值同 PROXY_STRATEGY
GATEWAY_STRATEGY = "random"

# 网关认证，格式 username:password；留空表示不认证
# 开启认证后，客户端也可用 <策略名>:<password> 作为认证信息临时选择策略，
# 例如 round_robin:password，便于同一个网关地址切换不同更换方式
GATEWAY_AUTH = ""

# 单个请求在选择上游代理失败时最多尝试的次数
GATEWAY_RETRY = 3

# 连接上游代理的超时时间（秒）
GATEWAY_CONNECT_TIMEOUT = 10

# 读取请求头/上游 CONNECT 响应的超时时间（秒）
GATEWAY_HEADER_TIMEOUT = 30

# ############# WAF detect config #################
# 是否在网关转发 HTTP 响应时检测 WAF 拦截；命中后自动换下一个代理重试。
# 注意：HTTPS CONNECT 隧道内容已加密，网关无法检测目标站 WAF。
WAF_DETECT_ENABLED = True

# 指纹命中分数阈值。1=弱指纹也会命中，2=推荐，3=只命中强指纹
WAF_SCORE_THRESHOLD = 2

# 读取响应体前缀用于关键词检测的最大字节数和超时时间
WAF_BODY_PREFIX_SIZE = 32768

WAF_BODY_READ_TIMEOUT = 2

# 请求体小于该字节数时先缓存，WAF 命中后可换代理重放；
# 超过该值或使用 chunked/Expect 的请求只流式转发，不再做 WAF 重试
WAF_MAX_REPLAY_BODY = 1048576

# 自定义规则：
#   响应头：存在即命中；也可以写成 "header-name:value-substring"
#   关键词：响应体（大小写不敏感）包含即命中
#   状态码：命中后直接判定为 WAF
WAF_CUSTOM_HEADERS = []

WAF_CUSTOM_KEYWORDS = []

WAF_CUSTOM_STATUS = []

# ############# monitor config #################
# 监控工作台由 API 服务提供：http://HOST:PORT/dashboard/
MONITOR_ENABLED = True

# 指标 SQLite 文件路径，相对路径基于项目根目录
MONITOR_DB_PATH = "data/monitor.db"

# 强制登录账号；请务必修改默认密码
MONITOR_AUTH_USER = "admin"

MONITOR_AUTH_PASSWORD = "change-me"

# 登录会话有效期（秒）
MONITOR_SESSION_TTL = 86400

# 如果通过 HTTPS 访问工作台，请设置为 True
MONITOR_COOKIE_SECURE = False

# 指标保留天数
MONITOR_RETENTION_DAYS = 7

# SSE 不可用或断线时，前端回退轮询的间隔（秒）
MONITOR_REFRESH_SECONDS = 5

# ############# scheduler config #################

# Set the timezone for the scheduler forcely (optional)
# If it is running on a VM, and
#   "ValueError: Timezone offset does not match system offset"
#   was raised during scheduling.
# Please uncomment the following line and set a timezone for the scheduler.
# Otherwise it will detect the timezone from the system automatically.

TIMEZONE = "Asia/Shanghai"
