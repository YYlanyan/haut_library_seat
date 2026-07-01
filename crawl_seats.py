import getpass
import os
from datetime import datetime, timedelta

import requests


LOGIN_URL = "https://wslib.haut.edu.cn/stage-api/login"
TREE_URL = "https://wslib.haut.edu.cn/stage-api/seat/SeatBookingResultAdd/treeselect"
QUERY_URL = "https://wslib.haut.edu.cn/stage-api/api/seatbook/layout/query"
REQUEST_TIMEOUT = 10


def get_credentials():
    username = os.getenv("SEAT_USERNAME") or input("请输入账号：").strip()
    password = os.getenv("SEAT_PASSWORD") or getpass.getpass("请输入密码：")
    return username, password


def login():
    username, password = get_credentials()
    data = {
        "username": username,
        "password": password
    }

    r = requests.post(LOGIN_URL, json=data, timeout=REQUEST_TIMEOUT)
    result = r.json()

    token = result.get("token")
    if not token:
        raise Exception("登录失败，未获取到 token")

    return token


def collect_regions(nodes, result=None):
    """递归提取所有最底层区域"""
    if result is None:
        result = []

    for node in nodes:
        children = node.get("children")

        if children:
            collect_regions(children, result)
        else:
            result.append({
                "regionid": node["id"],
                "regionName": node["label"]
            })

    return result


def get_all_regions(headers):
    r = requests.get(TREE_URL, headers=headers, timeout=REQUEST_TIMEOUT)
    data = r.json()

    return collect_regions(data.get("data", []))


def get_seats_by_region(headers, regionid):
    now = datetime.now()
    starttime = (now + timedelta(minutes=4)).strftime("%Y-%m-%d %H:%M:%S")
    endtime = now.strftime("%Y-%m-%d 22:00:00")

    params = {
        "pageNum": 1,
        "pageSize": 1000,
        "regionid": regionid,
        "starttime": starttime,
        "endtime": endtime
    }

    r = requests.get(QUERY_URL, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
    data = r.json()

    # 兼容不同返回结构
    if "seatList" in data:
        return data["seatList"]

    if "data" in data and isinstance(data["data"], dict):
        return data["data"].get("seatList", [])

    return []


def main():
    token = login()

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    regions = get_all_regions(headers)

    with open("seats.txt", "w", encoding="utf-8") as f:
        for region in regions:
            regionid = region["regionid"]
            region_name = region["regionName"]

            print(f"正在爬取：{region_name} regionid={regionid}")

            seats = get_seats_by_region(headers, regionid)

            f.write(f"\n===== {region_name} | regionid={regionid} =====\n")

            for seat in seats:
                seat_id = seat.get("id")
                seat_name = seat.get("seatName")

                if seat_id and seat_name:
                    f.write(f"{seat_id}\t{seat_name}\n")

    print("爬取完成，已保存到 seats.txt")


if __name__ == "__main__":
    main()
