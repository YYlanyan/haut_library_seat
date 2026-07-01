# Seat Project

本项目用于HAUT图书馆座位相关操作，主要由 Python 脚本组成。仓库中也保留了 App 相关目录，但普通使用者不需要关注源码，可以直接下载提供的 App 进行操作。

## 文件夹与文件总览

| 路径 | 作用 |
| --- | --- |
| `single_use/` | 单次使用脚本目录，每个脚本只完成一个具体动作 |
| `android_app/` | App 相关工程目录；普通使用者可直接下载提供的 App，无需阅读或修改该目录 |
| `seat_tool.py` | 多账号命令行工具，支持预约、查询、暂离、签退 |
| `seat_gui.py` | Python 图形界面工具，基于 PyQt5，支持爬取座位后下拉选择预约位置 |
| `crawl_seats.py` | 爬取座位区域和当前可预约座位，结果输出到 `seats.txt` |
| `seat_accounts.example.json` | 多账号配置模板 |
| `requirements.txt` | Python 依赖列表 |
| `seats.txt` | 座位爬取结果文件，由 `crawl_seats.py` 生成 |

## Python 环境

建议使用 Python 3.8 或以上版本。

安装依赖：

```bash
pip install -r requirements.txt
```

当前依赖包括：

```text
requests
PyQt5
```

其中 `PyQt5` 只用于 `seat_gui.py` 图形界面；如果只运行命令行脚本，核心依赖是 `requests`。

## 账号密码

源码中不保存真实账号和密码。脚本支持两种方式提供登录信息。

方式一：通过环境变量：

```bash
export SEAT_USERNAME="你的账号"
export SEAT_PASSWORD="你的密码"
```

方式二：不设置环境变量，运行脚本后按终端提示输入账号和密码。

不要把真实账号、密码、日志文件或本地配置提交到仓库。

## 单次使用脚本

目录：

```text
single_use/
```

这些脚本适合临时执行某一个动作。

| 文件 | 作用 |
| --- | --- |
| `single_use/booking_seat.py` | 登录并预约座位 |
| `single_use/leave_short.py` | 查询当前预约并短暂离开 |
| `single_use/leave_long.py` | 查询当前预约并长暂离开 |
| `single_use/signoff.py` | 查询当前预约并签退 |

运行示例：

```bash
python3 single_use/booking_seat.py
python3 single_use/leave_short.py
python3 single_use/leave_long.py
python3 single_use/signoff.py
```

说明：

- `booking_seat.py` 会在当前运行目录生成按日期命名的日志文件。
- 暂离和签退脚本会先查询当前预约，再对最新预约记录执行操作。

## 多账号命令行工具

文件：

```text
seat_tool.py
```

适合需要管理多个账号、批量执行命令的场景。

首次生成配置文件：

```bash
python3 seat_tool.py init-config
```

该命令会生成：

```text
seat_accounts.json
```

`seat_accounts.json` 是本地真实配置文件，不应提交到仓库。可以参考 `seat_accounts.example.json` 填写账号、密码、座位列表和启用状态。

常用命令：

```bash
python3 seat_tool.py book
python3 seat_tool.py status
python3 seat_tool.py leave-short
python3 seat_tool.py leave-long
python3 seat_tool.py signoff
```

只操作指定账号：

```bash
python3 seat_tool.py --account account_1 book
```

预约命令默认会立即发送指令。如需指定发送时间：

```bash
python3 seat_tool.py --book-at 06:59:30 book
```

如需沿用旧逻辑，在非预约时间等待到 `06:59:30`：

```bash
python3 seat_tool.py --wait-login-window book
```

## Python 图形界面

文件：

```text
seat_gui.py
```

该脚本提供图形界面，用于编辑账号配置并执行预约、查询、暂离、签退等操作。预约可选择直接发送指令，也可指定时间发送；等待指定时间时会在状态栏提示“等待到达预约时间”。界面中可以刷新座位列表，按区域下拉选择可预约座位并加入指定账号配置；刷新后会按“总座位数 - 可预约数”估算当前图书馆人数。运行日志页支持一键清空日志。

运行：

```bash
python3 seat_gui.py
```

如果提示缺少 PyQt5，请先执行：

```bash
pip install -r requirements.txt
```

## 爬取座位

文件：

```text
crawl_seats.py
```

作用：

- 登录系统
- 获取座位区域树
- 遍历每个区域
- 查询区域内座位信息
- 只将当前可预约座位的 ID 和座位名称保存到 `seats.txt`

运行：

```bash
python3 crawl_seats.py
```

输出文件：

```text
seats.txt
```

注意：每次运行 `crawl_seats.py` 都会覆盖当前目录下的 `seats.txt`。

## App 说明

仓库中包含 App 相关目录，但普通使用者不需要处理其中源码。需要移动端使用时，直接下载提供的 App 安装操作即可。App 端同样支持直接预约、按“时/分/秒”下拉选择时间定时预约、刷新座位列表、按区域下拉选择可预约座位、清空运行日志、状态栏等待提示和状态栏常驻显示运行状态。刷新座位列表后，右上角会按“总座位数 - 可预约数”估算当前图书馆人数。

## 注意事项

- 所有预约、查询、暂离、签退和爬取脚本都会访问线上接口。
- 执行前请确认账号、操作类型和目标座位。
