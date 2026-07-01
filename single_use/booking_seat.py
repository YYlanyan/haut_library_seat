import getpass
import os
import time
from datetime import datetime, timedelta

import requests


LOGIN_URL = "https://wslib.haut.edu.cn/stage-api/login"
BOOK_URL = "https://wslib.haut.edu.cn/stage-api/api/seatbook/user/addbooking"

DEFAULT_SEATS = [xxx]   #在此处添加你要使用的座位编号
CHANNEL = 1001
REQUEST_TIMEOUT = 10


def log(*message):
    text = " ".join(map(str, message))
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    milliseconds = int(now.microsecond / 1000)
    final_text = f"[{timestamp}.{milliseconds:03d}] {text}"
    print(final_text)

    log_name = now.strftime("%Y-%m-%d") + ".txt"
    with open(log_name, "a", encoding="utf-8") as f:
        f.write(final_text + "\n")


def get_credentials():
    username = os.getenv("SEAT_USERNAME") or input("请输入账号：").strip()
    password = os.getenv("SEAT_PASSWORD") or getpass.getpass("请输入密码：")
    return username, password


def get_booking_time():
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_time = now.time()

    t_7_00 = datetime.strptime("07:00:00", "%H:%M:%S").time()
    t_7_30 = datetime.strptime("07:30:00", "%H:%M:%S").time()
    t_21_00 = datetime.strptime("21:00:00", "%H:%M:%S").time()

    if t_7_00 <= current_time < t_7_30:
        log("当前处于 07:00-07:30，预约 07:30")
        return f"{today} 07:30:00"

    if t_7_30 <= current_time <= t_21_00:
        future_time = now + timedelta(minutes=4)
        log("当前处于 07:30-21:00，预约时间=当前时间+4分钟")
        return future_time.strftime("%Y-%m-%d %H:%M:%S")

    log("当前不在可预约时间，等待到 07:00")
    while True:
        now = datetime.now()
        if now.strftime("%H:%M:%S") >= "07:00:00":
            log("已到 07:00:00，延迟几毫秒等待服务器开放")
            break
        time.sleep(0.1)

    time.sleep(0.95)
    today = datetime.now().strftime("%Y-%m-%d")
    log("当前时间为：", now.strftime("%H:%M:%S"))
    log("到达 07:00，开始预约")
    return f"{today} 07:30:00"


def login():
    username, password = get_credentials()
    data = {
        "username": username,
        "password": password,
    }
    log("今天是：", datetime.now().strftime("%Y-%m-%d"))

    try:
        resp = requests.post(LOGIN_URL, json=data, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        result = resp.json()
    except Exception as exc:
        log("登录请求失败：", exc)
        return None

    token = result.get("token")
    if not token:
        log("登录失败，没有获取到 token：", result)
        return None

    log("登录成功")
    return token


def wait_until_659():
    target_time1 = datetime.strptime("06:59:30", "%H:%M:%S").time()
    target_time2 = datetime.strptime("07:00:00", "%H:%M:%S").time()
    log("当前不在可预约时间，等待到 06:59:30 登录")

    while True:
        now = datetime.now()
        if target_time1 <= now.time() <= target_time2:
            log("到达 06:59:30，开始登录")
            return
        time.sleep(1)


def reserve(token):
    today = datetime.now().strftime("%Y-%m-%d")
    start_time = get_booking_time()
    headers = {
        "Authorization": "Bearer " + token,
    }

    start_time_monotonic = time.time()
    while time.time() - start_time_monotonic < 5:
        for seat_id in DEFAULT_SEATS:
            params = {
                "channel": CHANNEL,
                "seatid": seat_id,
                "starttime": start_time,
                "endtime": f"{today} 22:00:00",
            }

            try:
                response = requests.get(
                    BOOK_URL,
                    params=params,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                result = response.json()
            except Exception as exc:
                log("预约请求失败：", exc)
                continue

            log("===================================")
            log(f"正在尝试 seatid: {seat_id}")
            log(result)

            if result.get("code") == 200:
                log(f"预约成功！seatid = {seat_id}")
                return True

            if result.get("code") in (404, 666):
                continue

        log("所有座位都预约失败")

    return False


def main():
    log("程序启动")
    now_time = datetime.now().time()
    t_7_00 = datetime.strptime("07:00:00", "%H:%M:%S").time()
    t_21_00 = datetime.strptime("21:00:00", "%H:%M:%S").time()

    if not (t_7_00 <= now_time <= t_21_00):
        wait_until_659()

    token = login()
    if token:
        reserve(token)

    log("程序结束")


if __name__ == "__main__":
    main()
