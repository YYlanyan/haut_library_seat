import time
import math
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from itertools import cycle
from datetime import datetime, timedelta

import requests


LOGIN_URL = "https://wslib.haut.edu.cn/stage-api/login"
BOOK_URL = "https://wslib.haut.edu.cn/stage-api/api/seatbook/user/addbooking"

# 在下面的引号中填写账号和密码，保存后直接运行即可
USERNAME = "xxx"  # 填写你的账号
PASSWORD = "xxx"  # 填写你的密码

DEFAULT_SEATS = [2674]   #在此处添加你要使用的座位编号
# ===== 时间设置：日常只需要修改这里，时间格式为 时:分:秒 =====
LOGIN_TIME = "06:59:30"           # 提前登录时间
BOOKING_OPEN_TIME = "7:00:00"    # 每天开放预约的时间
FIRST_START_TIME = "7:30:00"     # 早上预约的入座时间
BOOKING_CLOSE_TIME = "21:00:00"   # 当天最晚提交预约的时间，超过后等待次日
BOOKING_END_TIME = "22:00:00"     # 预约结束时间
START_AFTER_MINUTES = 4          # 已过早上入座时间时，预约“当前时间 + 几分钟”
OPEN_DELAY_SECONDS = 0.95       # 开放预约后再等待几秒，避免请求过早
RETRY_SECONDS = 6               # 尝试预约的持续时间（单次请求可能超过此时间）
# 以上钟点均为同一天，需按从早到晚排列；本脚本不支持跨夜预约。

# ===== 请求设置 =====
MAX_CONCURRENT_REQUESTS = 10000     # 最多同时等待几个预约请求；满额后等任意一个完成
REQUEST_INTERVAL_SECONDS = 0.01 # 两次发送之间至少间隔几秒
CHANNEL = 1001
REQUEST_TIMEOUT = 10           # 单次网络请求超时秒数
# RETRY_SECONDS 控制发送新请求的时长，到期后仍会收取已发请求的结果。
# 收到成功后停止新请求；已经发送到服务器的请求无法撤回。


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
    return USERNAME.strip(), PASSWORD


def at_time(day, clock):
    """将顶部配置的钟点转换成指定日期的时间。"""
    return datetime.combine(day, datetime.strptime(clock, "%H:%M:%S").time())


def validate_time_settings():
    clocks = [LOGIN_TIME, BOOKING_OPEN_TIME, FIRST_START_TIME,
              BOOKING_CLOSE_TIME, BOOKING_END_TIME]
    times = [datetime.strptime(clock, "%H:%M:%S").time() for clock in clocks]
    if times != sorted(times) or times[3] >= times[4]:
        raise ValueError("时间应满足：登录 ≤ 开放预约 ≤ 早上入座 ≤ 最晚提交 < 预约结束")
    if START_AFTER_MINUTES < 0 or OPEN_DELAY_SECONDS < 0 or RETRY_SECONDS <= 0:
        raise ValueError("入座延后分钟数、开放延迟不能为负数，重试时长必须大于 0")

    if not isinstance(MAX_CONCURRENT_REQUESTS, int) or isinstance(MAX_CONCURRENT_REQUESTS, bool) or MAX_CONCURRENT_REQUESTS < 1:
        raise ValueError("最大并发数必须是正整数")
    for value in (REQUEST_INTERVAL_SECONDS, REQUEST_TIMEOUT, RETRY_SECONDS):
        if not math.isfinite(value) or value <= 0:
            raise ValueError("请求间隔、请求超时和重试时长必须是有限的正数")
    if not DEFAULT_SEATS:
        raise ValueError("请至少填写一个座位编号")


def get_schedule(now):
    """截止前使用今天的计划，截止后使用明天的计划。"""
    day = now.date()
    if now > at_time(day, BOOKING_CLOSE_TIME):
        day += timedelta(days=1)
    return at_time(day, LOGIN_TIME), at_time(day, BOOKING_OPEN_TIME)


def wait_until(target):
    if datetime.now() < target:
        log("等待到：", target.strftime("%Y-%m-%d %H:%M:%S"))
    while True:
        remaining = (target - datetime.now()).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 1))


def get_booking_time(now=None):
    now = now or datetime.now()
    first_start = at_time(now.date(), FIRST_START_TIME)
    if now < first_start:
        return first_start
    return now + timedelta(minutes=START_AFTER_MINUTES)


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


def send_booking_request(token, seat_id, start_time, end_time):
    """每个线程只处理一个请求，由主线程统一接收和记录结果。"""
    params = {
        "channel": CHANNEL,
        "seatid": seat_id,
        "starttime": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "endtime": end_time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with requests.get(
        BOOK_URL,
        params=params,
        headers={"Authorization": "Bearer " + token},
        timeout=REQUEST_TIMEOUT,
    ) as response:
        response.raise_for_status()
        result = response.json()
    if not isinstance(result, dict):
        raise ValueError("服务器返回的数据格式异常")
    return result


def reserve(token):
    now = datetime.now()
    cutoff = at_time(now.date(), BOOKING_CLOSE_TIME)
    if now > cutoff:
        log("已超过当天最晚提交时间，结束预约")
        return False
    start_time = get_booking_time(now)
    end_time = at_time(now.date(), BOOKING_END_TIME)
    if start_time >= end_time:
        log("预约开始时间已达到或超过结束时间，请检查顶部时间设置")
        return False

    deadline = time.monotonic() + RETRY_SECONDS
    next_send = time.monotonic()
    seats = cycle(DEFAULT_SEATS)
    pending = {}
    success = False
    sending = True
    log(f"开始预约：最多并发 {MAX_CONCURRENT_REQUESTS} 个，发送间隔 {REQUEST_INTERVAL_SECONDS} 秒")

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as pool:
        while sending or pending:
            # 先处理已返回的结果，再决定是否发送下一条。
            for future in list(pending):
                if not future.done():
                    continue
                seat_id = pending.pop(future)
                try:
                    result = future.result()
                except Exception as exc:
                    log(f"seatid={seat_id} 请求异常（不能据此确定是否预约成功）：", exc)
                    response = getattr(exc, "response", None)
                    if response is not None and response.status_code == 429:
                        log("服务器提示请求过于频繁，停止发送新请求")
                        sending = False
                    continue
                log(f"seatid={seat_id} 返回：", result)
                if result.get("code") == 200:
                    success = True
                    sending = False
                    log(f"预约成功！seatid={seat_id}，停止发送新请求")

            if sending and (time.monotonic() >= deadline or datetime.now() > cutoff):
                sending = False
                log("已停止发送新请求，等待已发请求返回")

            if sending and len(pending) < MAX_CONCURRENT_REQUESTS and time.monotonic() >= next_send:
                seat_id = next(seats)
                future = pool.submit(send_booking_request, token, seat_id, start_time, end_time)
                pending[future] = seat_id
                next_send = time.monotonic() + REQUEST_INTERVAL_SECONDS
                log(f"已提交预约请求：seatid={seat_id}，未处理结果数={len(pending)}")

            # 有空位时按间隔发送；满额时等待任意请求完成，避免无限堆积。
            pause = 0.1
            if sending:
                pause = min(pause, max(0, deadline - time.monotonic()))
                if len(pending) < MAX_CONCURRENT_REQUESTS:
                    pause = min(pause, max(0, next_send - time.monotonic()))
            if pending:
                wait(pending, timeout=pause, return_when=FIRST_COMPLETED)
            elif sending:
                time.sleep(pause)

    if not success:
        log("本轮未收到预约成功确认；若请求曾超时，请在图书馆系统中核实预约记录")
    return success


def main():
    username, password = get_credentials()
    if not username or not password:
        print("请先在代码顶部的 USERNAME 和 PASSWORD 中填写账号和密码，再运行程序。")
        return

    try:
        validate_time_settings()
    except (ValueError, TypeError) as exc:
        print("顶部配置有误：", exc)
        return

    log("程序启动")
    login_at, booking_at = get_schedule(datetime.now())
    wait_until(login_at)
    token = login()
    if token:
        wait_until(booking_at + timedelta(seconds=OPEN_DELAY_SECONDS))
        reserve(token)

    log("程序结束")


if __name__ == "__main__":
    main()
