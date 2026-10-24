#2026/8/28
#预约系统加入了WAF，导致之前的获取token方式被ban掉，随尝试了新的写法
#该代码尝试加入更多信息来登录系统获取token
import requests
import getpass
import os

url = "https://wslib.haut.edu.cn/stage-api/login"

data = {
    "username": os.getenv("SEAT_USERNAME") or input("请输入账号: ").strip(),
    "password": os.getenv("SEAT_PASSWORD") or getpass.getpass("请输入密码: "),
    "code": "1",
    "uuid": "eb3501d403e14333b67509c9ca95cdbb"
}

headers = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": "https://wslib.haut.edu.cn",
    "Referer": "https://wslib.haut.edu.cn/login?redirect=%2Findex",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
}

r = requests.post(
    url,
    json=data,
    headers=headers,
    timeout=10
)

print(r.status_code)
print(r.headers.get("Content-Type"))
# 登录响应可能包含会话令牌，不直接输出响应正文。
print("登录响应已收到；请勿将令牌写入日志或源码。")
