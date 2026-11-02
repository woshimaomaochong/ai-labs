"""实测任务：每个任务有重置命令和 adb 校验（由我们自己的 adb 读系统状态判定，不看模型自己说成没成功）。"""
import re
import subprocess

DEVICE = "172.17.0.1:15555"
ADB = f"/work/platform-tools/adb -s {DEVICE}"


def sh(cmd, timeout=60):
    """在容器里执行 adb shell 命令，返回输出文本。"""
    full = f"docker exec mm-lab bash -lc '{ADB} shell \"{cmd}\"'"
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=10", "gpu-server", full],
                       capture_output=True, timeout=timeout)
    return r.stdout.decode("utf-8", "replace").strip()


def contacts():
    return sh("content query --uri content://com.android.contacts/data --projection mimetype:data1")


def contact_ok(name, number):
    """严格判定（2026-10-25 改）：名字在「姓名」栏、号码在「电话」栏；号码填进公司栏等不算。
    模拟器是美国区，号码会存成「1 (390) 013-9000」这类格式，所以电话栏只比对数字。"""
    rows = contacts().splitlines()
    name_ok = any("item/name," in r and r.split("data1=", 1)[-1].strip() == name for r in rows)
    phone_ok = any("item/phone_v2," in r and number in re.sub(r"\D", "", r.split("data1=", 1)[-1]) for r in rows)
    return name_ok and phone_ok


TASKS = [
    {"id": "dark", "goal": "把手机打开深色模式。",
     "check": lambda: sh("settings get secure ui_night_mode") == "2"},
    {"id": "alarm", "goal": "在时钟里新建一个早上 7:30 的闹钟，并保持开启。",
     # sh() 外层是单引号，命令里不能再用单引号；整段读回来在本地匹配「Next alarm clock … = 日期 07:30:00」
     "check": lambda: bool(re.search(r"Next alarm clock information:\s*\n\s*user:0[^\n]*= \d{4}-\d\d-\d\d 07:30:00",
                                     sh("dumpsys alarm")))},
    {"id": "contact_en", "goal": "在通讯录里新建联系人：名字 Tom Lee，手机号 13800138000，并保存。",
     "check": lambda: contact_ok("Tom Lee", "13800138000")},
    {"id": "timeout", "goal": "把屏幕自动锁屏（息屏）时间改成 10 分钟。",
     "check": lambda: sh("settings get system screen_off_timeout") == "600000"},
    {"id": "font", "goal": "把系统字体大小调到最大。",
     "check": lambda: float(sh("settings get system font_scale") or 1) >= 1.99},
    {"id": "dnd", "goal": "打开勿扰模式。",
     "check": lambda: sh("settings get global zen_mode") not in ("0", "", "null")},
    {"id": "contact_zh", "goal": "在通讯录里新建联系人：名字 张伟，手机号 13900139000，并保存。",
     "check": lambda: contact_ok("张伟", "13900139000")},
    {"id": "rename", "goal": "把这台手机的设备名称改成 AIZaoZhiDao。",
     "check": lambda: sh("settings get global device_name") == "AIZaoZhiDao"},
]

RESET = ";".join([
    "cmd uimode night no", "settings put secure ui_night_mode 1",
    "pm clear com.google.android.deskclock", "pm clear com.android.providers.contacts",
    "pm clear com.google.android.contacts",
    "settings put system screen_off_timeout 2147483647", "settings put system font_scale 1.0",
    "cmd notification set_dnd off", "settings put global device_name sdk_gphone64_x86_64",
    "am force-stop com.android.settings", "input keyevent KEYCODE_HOME",
])


def reset():
    sh(RESET, timeout=120)


def state():
    """当前各项状态，方便排查。"""
    return {t["id"]: _safe(t["check"]) for t in TASKS}


def _safe(f):
    try:
        return f()
    except Exception as e:
        return f"err {e}"


if __name__ == "__main__":
    reset()
    print(state())
