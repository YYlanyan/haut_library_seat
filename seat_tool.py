import argparse
import json
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import requests


BASE_URL = "https://wslib.haut.edu.cn"
LOGIN_URL = f"{BASE_URL}/stage-api/login"
BOOK_URL = f"{BASE_URL}/stage-api/api/seatbook/user/addbooking"
MY_BOOKING_URL = f"{BASE_URL}/stage-api/seat/SeatBookingResult/my"
TREE_URL = f"{BASE_URL}/stage-api/seat/SeatBookingResultAdd/treeselect"
SEAT_QUERY_URL = f"{BASE_URL}/stage-api/api/seatbook/layout/query"
LEAVE_SHORT_URL = f"{BASE_URL}/spacelink/api/seatbook/user/leave4short"
LEAVE_LONG_URL = f"{BASE_URL}/spacelink/api/seatbook/user/leave4long"
SIGNOFF_URL = f"{BASE_URL}/spacelink/api/seatbook/user/signoff"

CONFIG_FILE = Path("seat_accounts.json")
EXAMPLE_CONFIG_FILE = Path("seat_accounts.example.json")


@dataclass
class Account:
    name: str
    username: str
    password: str
    seats: list[int]
    enabled: bool = True


@dataclass
class SeatRegion:
    region_id: int
    name: str


@dataclass
class SeatInfo:
    seat_id: int
    name: str
    is_can: bool


@dataclass
class SeatRegionSeats:
    available_seats: list[SeatInfo]
    total_seats: int


def log(*message: Any, account: Optional[str] = None, write_file: bool = True) -> None:
    text = " ".join(map(str, message))
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    milliseconds = int(now.microsecond / 1000)
    prefix = f"[{timestamp}.{milliseconds:03d}]"
    if account:
        prefix = f"{prefix} [{account}]"
    final_text = f"{prefix} {text}"
    print(final_text)

    if write_file:
        log_name = now.strftime("%Y-%m-%d") + ".txt"
        with open(log_name, "a", encoding="utf-8") as f:
            f.write(final_text + "\n")


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"找不到配置文件 {path}。可先运行：python3 seat_tool.py init-config"
        )

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def init_config(path: Path, force: bool = False) -> None:
    if path.exists() and not force:
        log(f"{path} 已存在，未覆盖。", write_file=False)
        return

    shutil.copyfile(EXAMPLE_CONFIG_FILE, path)
    log(f"已生成 {path}，请填入第二个账号和密码。", write_file=False)


def build_accounts(config: dict[str, Any], selected_name: Optional[str]) -> list[Account]:
    defaults = config.get("defaults", {})
    default_seats = [int(seat) for seat in defaults.get("seats", [])]
    accounts: list[Account] = []

    for raw_account in config.get("accounts", []):
        enabled = bool(raw_account.get("enabled", True))
        name = str(raw_account.get("name") or raw_account.get("username"))

        if selected_name and name != selected_name:
            continue

        if not enabled:
            continue

        seats = raw_account.get("seats", default_seats)
        account = Account(
            name=name,
            username=str(raw_account.get("username", "")),
            password=str(raw_account.get("password", "")),
            seats=[int(seat) for seat in seats],
            enabled=enabled,
        )
        accounts.append(account)

    if selected_name and not accounts:
        raise ValueError(f"没有找到启用中的账号：{selected_name}")

    if not accounts:
        raise ValueError("配置文件中没有启用的账号。")

    return accounts


def request_json(
    method: str,
    url: str,
    *,
    account: str,
    timeout: int = 10,
    **kwargs: Any,
) -> Optional[dict[str, Any]]:
    try:
        response = requests.request(method, url, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        log("请求失败：", exc, account=account)
        return None


def login(account: Account) -> Optional[str]:
    if not account.username or not account.password:
        log("账号或密码为空，请检查配置。", account=account.name)
        return None

    data = {
        "username": account.username,
        "password": account.password,
    }
    result = request_json("POST", LOGIN_URL, json=data, account=account.name)
    if not result:
        return None

    token = result.get("token")
    if not token:
        log("登录失败，没有获取到 token：", result, account=account.name)
        return None

    log("登录成功", account=account.name)
    return str(token)


def get_booking_time() -> str:
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_time = now.time()

    t_7_00 = datetime.strptime("07:00:00", "%H:%M:%S").time()
    t_7_30 = datetime.strptime("07:30:00", "%H:%M:%S").time()
    t_21_00 = datetime.strptime("21:00:00", "%H:%M:%S").time()

    if t_7_00 <= current_time < t_7_30:
        return f"{today} 07:30:00"

    if t_7_30 <= current_time <= t_21_00:
        future_time = now + timedelta(minutes=4)
        return future_time.strftime("%Y-%m-%d %H:%M:%S")

    while True:
        now = datetime.now()
        if now.strftime("%H:%M:%S") >= "07:00:00":
            time.sleep(0.95)
            today = datetime.now().strftime("%Y-%m-%d")
            return f"{today} 07:30:00"

        time.sleep(0.1)


def collect_regions(nodes: list[dict[str, Any]], result: Optional[list[SeatRegion]] = None) -> list[SeatRegion]:
    if result is None:
        result = []

    for node in nodes:
        children = node.get("children")
        if children:
            collect_regions(children, result)
        else:
            result.append(SeatRegion(region_id=int(node["id"]), name=str(node["label"])))

    return result


def get_all_regions(token: str, account_name: str = "crawler") -> list[SeatRegion]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    result = request_json("GET", TREE_URL, headers=headers, account=account_name)
    if not result:
        return []

    return collect_regions(result.get("data", []))


def get_seats_by_region_with_stats(token: str, region_id: int, account_name: str = "crawler") -> SeatRegionSeats:
    now = datetime.now()
    start_time = (now + timedelta(minutes=4)).strftime("%Y-%m-%d %H:%M:%S")
    end_time = now.strftime("%Y-%m-%d 22:00:00")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    params = {
        "pageNum": 1,
        "pageSize": 1000,
        "regionid": region_id,
        "starttime": start_time,
        "endtime": end_time,
    }

    result = request_json(
        "GET",
        SEAT_QUERY_URL,
        params=params,
        headers=headers,
        account=account_name,
    )
    if not result:
        return []

    if "seatList" in result:
        raw_seats = result.get("seatList", [])
    elif isinstance(result.get("data"), dict):
        raw_seats = result["data"].get("seatList", [])
    else:
        raw_seats = []

    seats: list[SeatInfo] = []
    total_seats = 0
    for raw_seat in raw_seats:
        seat_id = raw_seat.get("id")
        seat_name = raw_seat.get("seatName")
        if seat_id and seat_name:
            total_seats += 1
        is_can = int(raw_seat.get("isCan", 0)) == 1
        if seat_id and seat_name and is_can:
            seats.append(
                SeatInfo(
                    seat_id=int(seat_id),
                    name=str(seat_name),
                    is_can=True,
                )
            )

    return SeatRegionSeats(available_seats=seats, total_seats=total_seats)


def get_seats_by_region(token: str, region_id: int, account_name: str = "crawler") -> list[SeatInfo]:
    return get_seats_by_region_with_stats(token, region_id, account_name).available_seats


def wait_until_login_window() -> None:
    target_start = datetime.strptime("06:59:30", "%H:%M:%S").time()
    target_end = datetime.strptime("07:00:00", "%H:%M:%S").time()

    while True:
        now = datetime.now()
        if target_start <= now.time() <= target_end:
            return
        time.sleep(1)


def parse_clock_time(value: str) -> datetime.time:
    text = value.strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ValueError("时间格式错误，请使用 HH:MM:SS，例如 06:59:30")


def wait_until_clock_time(value: str) -> None:
    target_time = parse_clock_time(value)
    now = datetime.now()
    target = datetime.combine(now.date(), target_time)
    if target <= now:
        target += timedelta(days=1)

    log(f"等待到 {target.strftime('%Y-%m-%d %H:%M:%S')} 发送预约指令...")
    while True:
        remaining = (target - datetime.now()).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(1, remaining))


def should_wait_for_login() -> bool:
    now = datetime.now().time()
    t_7_00 = datetime.strptime("07:00:00", "%H:%M:%S").time()
    t_21_00 = datetime.strptime("21:00:00", "%H:%M:%S").time()
    return not (t_7_00 <= now <= t_21_00)


def reserve(account: Account, token: str, config: dict[str, Any]) -> bool:
    defaults = config.get("defaults", {})
    today = datetime.now().strftime("%Y-%m-%d")
    start_time = get_booking_time()
    end_time = defaults.get("end_time", "22:00:00")
    rush_seconds = int(defaults.get("rush_seconds", 5))
    channel = int(defaults.get("channel", 1001))
    headers = {"Authorization": f"Bearer {token}"}

    log(
        f"开始预约，start={start_time}，end={today} {end_time}，候选座位={account.seats}",
        account=account.name,
    )

    started_at = time.time()
    while time.time() - started_at < rush_seconds:
        for seat_id in account.seats:
            params = {
                "channel": channel,
                "seatid": seat_id,
                "starttime": start_time,
                "endtime": f"{today} {end_time}",
            }
            result = request_json("GET", BOOK_URL, params=params, headers=headers, account=account.name)
            if not result:
                continue

            code = result.get("code")
            log(f"尝试 seatid={seat_id}，返回：{result}", account=account.name)

            if code == 200:
                log(f"预约成功，seatid={seat_id}", account=account.name)
                return True

            if code not in (404, 666):
                log(f"非占座类错误，继续尝试下一个座位。code={code}", account=account.name)

    log("本轮未预约成功", account=account.name)
    return False


def get_latest_booking(account: Account, token: str) -> Optional[dict[str, Any]]:
    headers = {"Authorization": f"Bearer {token}"}
    params = {"pageNum": 1, "pageSize": 10}
    result = request_json(
        "GET",
        MY_BOOKING_URL,
        params=params,
        headers=headers,
        account=account.name,
    )
    if not result:
        return None

    rows = result.get("rows", [])
    if not rows:
        log("没有预约记录", account=account.name)
        return None

    booking = rows[0]
    booking_status = str(booking.get("bookingStatus", ""))
    if booking_status in ("6", "7"):
        log("当前无预约", account=account.name)
        return None

    log(
        "当前预约：",
        f"id={booking.get('id')}",
        f"seat={booking.get('seatName')}",
        f"start={booking.get('startDate')}",
        f"status={booking_status}",
        account=account.name,
    )
    return booking


def leave(account: Account, token: str, config: dict[str, Any], mode: str) -> bool:
    booking = get_latest_booking(account, token)
    if not booking:
        return False

    booking_id = booking.get("id")
    if not booking_id:
        log("预约记录缺少 id，无法暂离。", account=account.name)
        return False

    defaults = config.get("defaults", {})
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "bookingid": booking_id,
        "channelType": int(defaults.get("leave_channel_type", 1003)),
    }
    url = LEAVE_SHORT_URL if mode == "short" else LEAVE_LONG_URL
    result = request_json("GET", url, params=params, headers=headers, account=account.name)
    if result is None:
        return False

    log(f"{'短' if mode == 'short' else '长'}暂离返回：{result}", account=account.name)
    return result.get("code") == 200


def signoff(account: Account, token: str, config: dict[str, Any]) -> bool:
    booking = get_latest_booking(account, token)
    if not booking:
        return False

    booking_id = booking.get("id")
    if not booking_id:
        log("预约记录缺少 id，无法签退。", account=account.name)
        return False

    defaults = config.get("defaults", {})
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "bookingid": booking_id,
        "channelType": int(defaults.get("leave_channel_type", 1003)),
    }
    result = request_json("GET", SIGNOFF_URL, params=params, headers=headers, account=account.name)
    if result is None:
        return False

    log(f"签退返回：{result}", account=account.name)
    return result.get("code") == 200


def run_for_accounts(args: argparse.Namespace, config: dict[str, Any]) -> int:
    accounts = build_accounts(config, args.account)

    if args.command == "book" and args.book_at:
        wait_until_clock_time(args.book_at)
    elif args.command == "book" and args.wait_login_window and should_wait_for_login():
        log("当前不在可预约时间，等待到 06:59:30 登录...")
        wait_until_login_window()

    failures = 0
    for account in accounts:
        token = login(account)
        if not token:
            failures += 1
            continue

        if args.command == "book":
            ok = reserve(account, token, config)
        elif args.command == "leave-short":
            ok = leave(account, token, config, "short")
        elif args.command == "leave-long":
            ok = leave(account, token, config, "long")
        elif args.command == "signoff":
            ok = signoff(account, token, config)
        elif args.command == "status":
            ok = get_latest_booking(account, token) is not None
        else:
            raise ValueError(f"未知命令：{args.command}")

        if not ok:
            failures += 1

        if args.interval > 0:
            time.sleep(args.interval)

    return 1 if failures else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="多账号图书馆座位预约工具")
    parser.add_argument(
        "--config",
        default=str(CONFIG_FILE),
        help="配置文件路径，默认 seat_accounts.json",
    )
    parser.add_argument(
        "--account",
        help="只操作指定账号 name；不传则操作所有 enabled=true 的账号",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0,
        help="多个账号之间的间隔秒数，默认 0",
    )
    parser.add_argument(
        "--book-at",
        help="预约命令指定发送时间，格式 HH:MM:SS；不传则直接发送",
    )
    parser.add_argument(
        "--wait-login-window",
        action="store_true",
        help="预约命令沿用旧逻辑：非预约时间等待到 06:59:30",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init-config", help="从模板生成 seat_accounts.json")
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="覆盖已有配置文件",
    )
    subparsers.add_parser("book", help="预约座位")
    subparsers.add_parser("status", help="查看最新预约")
    subparsers.add_parser("leave-short", help="短暂离开")
    subparsers.add_parser("leave-long", help="长暂离开")
    subparsers.add_parser("signoff", help="签退")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.command == "init-config":
        init_config(Path(args.config), force=args.force)
        return 0

    config = load_config(Path(args.config))
    return run_for_accounts(args, config)


if __name__ == "__main__":
    raise SystemExit(main())
