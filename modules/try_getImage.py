#2026/8/28
#预约系统加入了WAF，导致之前的获取token方式被ban掉，随尝试了新的写法
#该代码尝试得到网页端登录验证码的图片
import requests

session = requests.Session()

headers = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://wslib.haut.edu.cn",
    "Referer": "https://wslib.haut.edu.cn/login?redirect=%2Findex",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    )
}

r = session.get(
    "https://wslib.haut.edu.cn/stage-api/captchaImage",
    headers=headers,
    timeout=10
)

print(r.status_code)
print(r.headers.get("Content-Type"))
print(r.text[:300])