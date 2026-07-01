import getpass
import os
from datetime import datetime

import requests


MY_BOOKING_URL = "https://wslib.haut.edu.cn/stage-api/seat/SeatBookingResult/my"
LOGIN_URL = "https://wslib.haut.edu.cn/stage-api/login"
LEAVE_URL = "https://wslib.haut.edu.cn/spacelink/api/seatbook/user/leave4long"

REQUEST_TIMEOUT = 10
CHANNEL_TYPE = 1003


def log(*message):
    text = " ".join(map(str, message))
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    milliseconds = int(now.microsecond / 1000)
    print(f"[{timestamp}.{milliseconds:03d}] {text}")


def get_credentials():
    username = os.getenv("SEAT_USERNAME") or input("请输入账号：").strip()
    password = os.getenv("SEAT_PASSWORD") or getpass.getpass("请输入密码：")
    return username, password


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
        log("登录失败：", exc)
        return None

    token = result.get("token")
    if not token:
        log("登录失败，没有获取到 token：", result)
        return None

    log("登录成功")
    return token


def get_booking_id(token):
    headers = {
        "Authorization": f"Bearer {token}",
    }
    params = {
        "pageNum": 1,
        "pageSize": 10,
    }

    try:
        response = requests.get(
            MY_BOOKING_URL,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()
    except Exception as exc:
        log("查询预约失败：", exc)
        return None

    rows = result.get("rows", [])
    if not rows:
        log("没有预约记录")
        return None

    booking = rows[0]
    booking_id = booking.get("id")

    log("当前 bookingid：", booking_id)
    log("座位：", booking.get("seatName"))
    log("开始时间：", booking.get("startDate"))
    log("状态：", booking.get("bookingStatus"))

    return booking_id


def leave(token, booking_id):
    headers = {
        "Authorization": f"Bearer {token}",
    }
    params = {
        "bookingid": booking_id,
        "channelType": CHANNEL_TYPE,
    }

    try:
        response = requests.get(
            LEAVE_URL,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        print(response.json())
    except Exception as exc:
        log("长暂离开失败：", exc)


def main():
    token = login()
    if not token:
        return

    booking_id = get_booking_id(token)
    if booking_id is not None:
        leave(token, booking_id)


if __name__ == "__main__":
    main()
