# ============================================================
# 虽然现在图书馆预约系统的验证码还是一个装饰品（随便输入答案就能通过验证），但是可能就会修改这个Bug
# 这个代码就是为了防止图书馆修改Bug后，需要输入正确的答案才能进入预约系统
# 但是现在还不完善，因为Bug还没修复，暂时没时间往这上面费精力
# ============================================================
import requests
import base64
import time
import os
import getpass
import subprocess

from datetime import datetime, timedelta


# ============================================================
# 基本配置
# ============================================================

BASE_URL = "https://wslib.haut.edu.cn"

LOGIN_URL = f"{BASE_URL}/stage-api/login"
CAPTCHA_URL = f"{BASE_URL}/stage-api/captchaImage"
BOOKING_URL = f"{BASE_URL}/stage-api/api/seatbook/user/addbooking"


# ============================================================
# 账号
# ============================================================

USERNAME = os.getenv("SEAT_USERNAME")
PASSWORD = os.getenv("SEAT_PASSWORD")


# ============================================================
# 座位(手动写入想要坐入的位置)
# ============================================================

seat_list = [
    1000,
]


# ============================================================
# Session
# ============================================================

session = requests.Session()

session.headers.update({
    "Accept": "application/json, text/plain, */*",

    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    )
})


# ============================================================
# 日志
# ============================================================

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


# ============================================================
# 获取预约时间
# ============================================================

def get_booking_time():

    now = datetime.now()

    today = now.strftime("%Y-%m-%d")

    current_time = now.time()

    t_7_00 = datetime.strptime(
        "07:00:00",
        "%H:%M:%S"
    ).time()

    t_7_30 = datetime.strptime(
        "07:30:00",
        "%H:%M:%S"
    ).time()

    t_21_00 = datetime.strptime(
        "21:00:00",
        "%H:%M:%S"
    ).time()


    # 07:00 ~ 07:30
    if t_7_00 <= current_time < t_7_30:

        start_time = f"{today} 07:30:00"

        log(
            "当前处于 07:00-07:30，"
            "预约开始时间：",
            start_time
        )

        return start_time


    # 07:30 ~ 21:00
    elif t_7_30 <= current_time <= t_21_00:

        future_time = now + timedelta(minutes=4)

        start_time = future_time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        log(
            "当前处于 07:30-21:00，"
            "预约时间 = 当前时间 + 4分钟：",
            start_time
        )

        return start_time


    # 其它时间
    else:

        log("当前不在可预约时间，等待到 07:00")

        while True:

            now = datetime.now()

            if now.time() >= t_7_00:
                break

            time.sleep(0.1)

        log("已到 07:00")

        today = datetime.now().strftime("%Y-%m-%d")

        start_time = f"{today} 07:30:00"

        return start_time


# ============================================================
# 获取验证码
# ============================================================

def get_captcha():

    log("开始获取验证码...")

    headers = {
        "Accept": "application/json, text/plain, */*",

        "Referer": (
            f"{BASE_URL}/login?redirect=%2Findex"
        ),

        "Origin": BASE_URL
    }


    try:

        resp = session.get(
            CAPTCHA_URL,
            headers=headers,
            timeout=10
        )

    except requests.RequestException as e:

        log(
            "获取验证码请求异常：",
            repr(e)
        )

        return None, None


    log(
        "验证码 HTTP 状态码：",
        resp.status_code
    )

    log(
        "验证码 Content-Type：",
        resp.headers.get("Content-Type")
    )


    if resp.status_code != 200:

        log(
            "获取验证码失败：",
            resp.text[:500]
        )

        return None, None


    try:

        result = resp.json()

    except requests.exceptions.JSONDecodeError:

        log("验证码接口返回的不是 JSON")

        log(
            "服务器响应：",
            repr(resp.text[:500])
        )

        return None, None


    if result.get("code") != 200:

        log(
            "验证码接口业务失败：",
            result
        )

        return None, None


    img = result.get("img")

    uuid = result.get("uuid")


    if not img or not uuid:

        log(
            "验证码响应缺少 img 或 uuid"
        )

        return None, None


    # ========================================================
    # 保存临时验证码
    # ========================================================

    captcha_path = os.path.abspath(
        "captcha.jpg"
    )


    try:

        image_data = base64.b64decode(img)

        with open(
            captcha_path,
            "wb"
        ) as f:

            f.write(image_data)

    except Exception as e:

        log(
            "保存验证码失败：",
            repr(e)
        )

        return None, None


    log(
        "验证码下载成功"
    )

    log(
        "UUID：",
        uuid
    )


    # ========================================================
    # 自动打开验证码
    # ========================================================

    try:

        subprocess.Popen(
            ["open", captcha_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        log(
            "已自动打开验证码图片"
        )

    except Exception as e:

        log(
            "自动打开验证码失败：",
            repr(e)
        )

        log(
            "验证码位置：",
            captcha_path
        )


    return uuid, captcha_path


# ============================================================
# 删除验证码
# ============================================================

def delete_captcha(captcha_path):

    if not captcha_path:
        return


    try:

        if os.path.exists(captcha_path):

            os.remove(captcha_path)

            log(
                "验证码图片已删除"
            )

    except Exception as e:

        log(
            "删除验证码图片失败：",
            repr(e)
        )


# ============================================================
# 登录
# ============================================================

def login(code, uuid):

    data = {
        "username": USERNAME or input("请输入账号: ").strip(),
        "password": PASSWORD or getpass.getpass("请输入密码: "),
        "code": code,
        "uuid": uuid
    }


    headers = {
        "Accept": "application/json, text/plain, */*",

        "Content-Type": (
            "application/json;charset=UTF-8"
        ),

        "Origin": BASE_URL,

        "Referer": (
            f"{BASE_URL}/login?redirect=%2Findex"
        )
    }


    log("开始登录...")


    try:

        resp = session.post(
            LOGIN_URL,
            json=data,
            headers=headers,
            timeout=10
        )

    except requests.RequestException as e:

        log(
            "登录请求异常：",
            repr(e)
        )

        return None


    log(
        "登录 HTTP 状态码：",
        resp.status_code
    )


    if resp.status_code != 200:

        log(
            "登录失败：",
            resp.text[:500]
        )

        return None


    try:

        result = resp.json()

    except requests.exceptions.JSONDecodeError:

        log(
            "登录接口返回的不是 JSON"
        )

        log(
            "服务器响应：",
            repr(resp.text[:500])
        )

        return None


    # 隐藏 token
    log(
        "登录结果：",
        {
            k: (
                "[已隐藏]"
                if k == "token"
                else v
            )
            for k, v in result.items()
        }
    )


    if result.get("code") != 200:

        log(
            "登录失败：",
            result.get("msg")
        )

        return None


    token = result.get("token")


    if not token:

        log(
            "登录成功，但是没有 token"
        )

        return None


    return token


# ============================================================
# 预约
# ============================================================

def reserve(token):

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    start_time = get_booking_time()


    headers = {
        "Authorization": "Bearer " + token,

        "Accept": (
            "application/json, text/plain, */*"
        ),

        "Referer": f"{BASE_URL}/"
    }


    log("开始预约")

    log(
        "预约开始时间：",
        start_time
    )

    log(
        "预约结束时间：",
        f"{today} 22:00:00"
    )


    start_reserve_time = time.time()


    while time.time() - start_reserve_time < 5:

        for seat_id in seat_list:

            params = {
                "channel": 1001,

                "seatid": seat_id,

                "starttime": start_time,

                "endtime": (
                    f"{today} 22:00:00"
                )
            }


            log(
                "正在尝试 seatid:",
                seat_id
            )


            try:

                r = session.get(
                    BOOKING_URL,
                    params=params,
                    headers=headers,
                    timeout=10
                )

            except requests.RequestException as e:

                log(
                    "预约请求异常：",
                    repr(e)
                )

                continue


            log(
                "预约 HTTP 状态码：",
                r.status_code
            )


            try:

                result = r.json()

            except requests.exceptions.JSONDecodeError:

                log(
                    "预约接口返回的不是 JSON"
                )

                log(
                    "服务器响应：",
                    repr(r.text[:500])
                )

                continue


            log(
                "预约结果：",
                result
            )


            if result.get("code") == 200:

                log(
                    "==================================="
                )

                log(
                    "预约成功！seatid =",
                    seat_id
                )

                log(
                    "==================================="
                )

                return True


            elif result.get("code") == 404:

                log(
                    "seatid",
                    seat_id,
                    "当前不可预约"
                )

                continue


            elif result.get("code") == 666:

                log(
                    "seatid",
                    seat_id,
                    "返回 code=666"
                )

                continue


            else:

                log(
                    "其它预约结果：",
                    result
                )


        time.sleep(0.05)


    log(
        "5秒预约时间结束，"
        "所有座位均未预约成功"
    )

    return False


# ============================================================
# 等待 06:59:30
# ============================================================

def wait_until_659():

    target_time1 = datetime.strptime(
        "06:59:30",
        "%H:%M:%S"
    ).time()

    target_time2 = datetime.strptime(
        "07:00:00",
        "%H:%M:%S"
    ).time()


    log(
        "当前不在可预约时间，"
        "等待到 06:59:30 登录..."
    )


    while True:

        now = datetime.now()

        current_time = now.time()


        if (
            target_time1
            <= current_time
            <= target_time2
        ):

            log(
                "到达 06:59:30，开始登录..."
            )

            return


        time.sleep(1)


# ============================================================
# 主程序
# ============================================================

def main():

    log("程序启动...")


    now = datetime.now().time()


    t_7_00 = datetime.strptime(
        "07:00:00",
        "%H:%M:%S"
    ).time()

    t_21_00 = datetime.strptime(
        "21:00:00",
        "%H:%M:%S"
    ).time()


    # ========================================================
    # 判断是否需要等待
    # ========================================================

    if t_7_00 <= now <= t_21_00:

        log(
            "当前处于可预约时间，"
            "开始获取验证码..."
        )

    else:

        wait_until_659()


    # ========================================================
    # 获取验证码
    # ========================================================

    uuid = None
    captcha_path = None


    try:

        uuid, captcha_path = get_captcha()


        if uuid is None:

            log(
                "获取验证码失败，程序结束"
            )

            return


        # ====================================================
        # 等待用户输入验证码
        # ====================================================

        print()
        print("======================================")
        print("验证码窗口已经自动打开")
        print("请输入验证码")
        print("======================================")
        print()


        code = input(
            "请输入验证码："
        ).strip()


        if not code:

            log(
                "没有输入验证码"
            )

            return


        # ====================================================
        # 登录
        # ====================================================

        token = login(
            code=code,
            uuid=uuid
        )


        if not token:

            log(
                "登录失败"
            )

            return


        log(
            "登录成功"
        )


        # ====================================================
        # 预约
        # ====================================================

        success = reserve(token)


        if success:

            log(
                "预约任务完成"
            )

        else:

            log(
                "预约任务结束，"
                "没有预约成功"
            )


    finally:

        # ====================================================
        # 无论登录成功、失败还是程序异常
        # 都删除验证码
        # ====================================================

        delete_captcha(
            captcha_path
        )


    log(
        "程序结束"
    )


# ============================================================
# 程序入口
# ============================================================

if __name__ == "__main__":

    main()
