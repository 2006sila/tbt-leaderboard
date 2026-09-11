# -*- coding: utf-8 -*-
"""tbts-score v1 成绩卡：解析、规范化、自校验。

格式定义方是桌面端的 csharp/TBTAvalonia/Models/ScoreExport.cs，
本模块是 Python 侧的**参考实现**，与 C# 必须逐字节一致。

为什么必须"逐字节"
------------------
成绩卡里的 integrity.payloadSha256 是 C# 在导出时算的载荷哈希。校验器要复现它，
就得把"解析出来的对象"重新序列化成与 C# 完全相同的一串字节：

  1. 键序  —— 按 DTO 声明顺序固定（本文件的 SCHEMA 顺序即声明顺序）
  2. 数字  —— System.Text.Json 用最短往返格式：68.0 序列化成 "68"，不是 "68.0"
  3. 转义  —— UnsafeRelaxedJsonEscaping 不转义 BMP 内的非 ASCII（中文原样输出），
              但会转义 BMP 之外的字符（emoji 💻 → \\uD83D\\uDCBB）

第 3 条是最隐蔽的坑：只差一个 emoji，哈希就全错。已用真卡片 + 文档样例
逐字节比对通过（tools/selftest_card.py）。

边界（务必明确）
----------------
payloadSha256 **不是防伪**，只是防"改了数字忘改哈希"这类低级篡改：算法公开，
任何人都能自己造一份完全自洽的假卡。唯一可事后复算的锚点是 recording.sha256。
"""

import hashlib
import json
import math
import re

FORMAT_ID = "tbts-score"
FORMAT_VERSION = 1

# ── 结构定义：键序 = C# DTO 的声明顺序，改动即破坏兼容 ──────────────────────
# 标记含义：
#   s  必填字符串      s?  可空字符串（null 写成 null）
#   i  必填整数        i?  可空整数
#   n? 可空浮点（按 C# double 规则格式化）
#   b  布尔            L   字符串数组
#   o? 对象（canonical 时恒为 null，即 integrity 块）
#   dict  嵌套对象
#
# OMIT_WHEN_NULL：C# 侧标了 [JsonIgnore(WhenWritingNull)] 的字段。
# 目前只有 owner 一个 —— 空署名时整键不输出。若改成写 null，
# 早期导出的成绩卡会在回环里多出一个键、payloadSha256 全部失效。
OMIT_WHEN_NULL = {"owner"}

SCHEMA = {
    "format": "s",
    "version": "i",
    "generatedAt": "s",
    "owner": "s?",
    "generator": {
        "app": "s",
        "version": "s",
        "platform": "s",
        "sampleIntervalSec": "i",
    },
    "score": {
        "total": "n?",
        "grade": "s",
        "parts": {
            "performance": "n?",
            "smoothness": "n?",
            "thermal": "n?",
            "stability": "n?",
            "efficiency": "n?",
            "noise": "n?",
        },
    },
    "metrics": {
        k: "n?" for k in [
            "fpsAvg", "fps1LowAvg", "fpsWorst1Pct", "frametimeP99Ms", "stutterRatio",
            "stutterPct", "frametimeCv", "fpsPerWatt", "fanPeakRpm", "cpuHeadroomC",
            "gpuHeadroomC", "throttlePct", "below60Pct", "below30Pct", "below25Pct",
            "latencyP99Ms", "cpuMhzRatio", "cpuUtilAvgPct", "gpuUtilAvgPct",
            "vramUtilAvgPct", "committedUtilAvgPct", "vramTempMaxC",
            "memSlotTempMaxC", "diskTempMaxC",
        ]
    },
    "events": {
        "stutterRuns": "i",
        "dipRuns": "i",
        "throttlePct": "n?",
        "powerWall": "b",
        "powerWallDropPct": "n?",
        "eventCount": "i",
    },
    "hardware": {
        "cpu": "s",
        "cpuCores": "i?",
        "cpuThreads": "i?",
        "gpu": "s",
        "board": "s",
        "os": "s",
        "ram": "s",
        "ramModel": "s",
        "disk": "s",
        "display": "s",
        "battery": "s",
    },
    "view": {
        "range": "s",
        "rangeIndex": "i",
        "durationSec": "n?",
        "sampleCount": "i",
    },
    "recording": {
        "fileName": "s?",
        "bytes": "i?",
        "sha256": "s?",
    },
    "confidence": {
        "hasFps": "b",
        "insufficient": "b",
        "sampling": "s",
        "note": "s",
    },
    "flavor": {
        "persona": "s",
        "face": "s",
        "text": "s",
        "feats": "L",
    },
    "integrity": "o?",
}

# 分项里进总分的三项（其余只做能力剖面）
SCORED_PARTS = ("performance", "smoothness", "thermal")


class CardError(ValueError):
    """成绩卡不可用（结构错误 / 不是 tbts-score v1）。"""


# ══════════════════════════ 序列化（复刻 System.Text.Json）══════════════════════════

def _jstr(s):
    """字符串字面量。

    对齐 JavaScriptEncoder.UnsafeRelaxedJsonEscaping：
      · BMP 内的非 ASCII（中文、全角标点）原样输出，不转成 \\uXXXX
      · BMP 之外（emoji 等）转成 UTF-16 surrogate pair 的 \\uXXXX，大写十六进制
    """
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\b":
            out.append("\\b")
        elif ch == "\f":
            out.append("\\f")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif o < 0x20:
            out.append("\\u%04X" % o)
        elif o > 0xFFFF:
            v = o - 0x10000
            out.append("\\u%04X\\u%04X" % (0xD800 + (v >> 10), 0xDC00 + (v & 0x3FF)))
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _jnum(x):
    """数字字面量，对齐 System.Text.Json 的 double 输出。

    要点：整数值不带小数点（68.0 → "68"，而不是 Python 默认的 "68.0"）。
    """
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    f = float(x)
    if math.isnan(f) or math.isinf(f):
        raise CardError("数值不合法：%r" % (x,))
    if f == 0:
        return "-0" if math.copysign(1.0, f) < 0 else "0"
    if f.is_integer() and abs(f) < 1e16:
        return str(int(f))
    r = repr(f)
    if "e" in r or "E" in r:
        mant, _, exp = r.lower().partition("e")
        e = int(exp)
        return "%sE%s%02d" % (mant, "+" if e >= 0 else "-", abs(e))
    return r


def _enc(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return _jstr(v)
    if isinstance(v, (int, float)):
        return _jnum(v)
    if isinstance(v, list):
        return "[" + ",".join(_enc(i) for i in v) + "]"
    raise CardError("无法序列化的类型：%s" % type(v).__name__)


def _canon_obj(spec, src):
    parts = []
    for key, sp in spec.items():
        val = src.get(key)
        if isinstance(sp, dict):
            body = _canon_obj(sp, val) if isinstance(val, dict) else "null"
            parts.append(_jstr(key) + ":" + body)
        elif sp == "o?":
            # canonical 规则：integrity 恒为 null
            parts.append(_jstr(key) + ":null")
        elif sp == "L":
            items = val if isinstance(val, list) else []
            parts.append(_jstr(key) + ":" + _enc(items))
        else:
            if val is None:
                if key in OMIT_WHEN_NULL:
                    continue
                parts.append(_jstr(key) + ":null")
                continue
            parts.append(_jstr(key) + ":" + _enc(val))
    return "{" + ",".join(parts) + "}"


def canonical_payload(card):
    """成绩卡的规范化载荷字符串（integrity=null、无缩进、UTF-8、固定键序）。"""
    return _canon_obj(SCHEMA, card)


def payload_sha256(card):
    """按 v1 规范复算载荷哈希（小写 hex）。"""
    return hashlib.sha256(canonical_payload(card).encode("utf-8")).hexdigest()


# ══════════════════════════════ 解析与结构检查 ══════════════════════════════

_JSON_BLOCK = re.compile(r"```json\s*\n(.*?)```", re.S | re.I)
_ANY_BLOCK = re.compile(r"```(?:\w+)?\s*\n(.*?)```", re.S)


def extract_json_block(body):
    """从 issue 正文里取第一个 ```json 代码块；没有则退回第一个任意代码块。"""
    m = _JSON_BLOCK.search(body or "")
    if not m:
        m = _ANY_BLOCK.search(body or "")
    if not m:
        raise CardError(
            "正文里找不到代码块。请把成绩卡内容粘进 ```json 代码块里再提交。"
        )
    return m.group(1).strip()


def parse_card(text):
    """解析成绩卡文本，做基本结构检查。失败抛 CardError（消息面向提交者）。"""
    if not text or not text.strip():
        raise CardError("成绩卡内容是空的。")
    try:
        card = json.loads(text)
    except json.JSONDecodeError as e:
        raise CardError(
            "不是合法的 JSON（第 %d 行第 %d 列：%s）。"
            "常见原因是粘贴时被截断，或把说明文字一起粘进来了。"
            % (e.lineno, e.colno, e.msg)
        )
    if not isinstance(card, dict):
        raise CardError("成绩卡的顶层应该是一个 JSON 对象 {}。")

    fmt = card.get("format")
    if fmt != FORMAT_ID:
        raise CardError(
            'format 应为 "%s"，实际是 %r —— 这不是 TBTS 导出的成绩卡。'
            % (FORMAT_ID, fmt)
        )
    ver = card.get("version")
    if ver != FORMAT_VERSION:
        raise CardError(
            "成绩卡版本 %r 不受支持（当前只收 v%d）。请升级 TBTS 后重新导出。"
            % (ver, FORMAT_VERSION)
        )

    for block in ("generator", "score", "metrics", "events",
                  "hardware", "view", "recording", "confidence"):
        if not isinstance(card.get(block), dict):
            raise CardError("成绩卡缺少 %s 块，文件可能已损坏。" % block)

    integ = card.get("integrity")
    if not isinstance(integ, dict) or not integ.get("payloadSha256"):
        raise CardError("成绩卡缺少 integrity.payloadSha256，无法校验完整性。")

    return card


def verify_payload(card):
    """校验载荷哈希自洽。返回 (是否通过, 文件里声明的, 复算得到的)。"""
    expected = ((card.get("integrity") or {}).get("payloadSha256") or "").lower()
    actual = payload_sha256(card)
    return (expected != "" and expected == actual), expected, actual


# ══════════════════════════════ 派生与归一化 ══════════════════════════════

def norm_hw(s):
    """机型归一化 —— 用于"同 CPU + 同 GPU"分组键。

    与 web/app.js 里的 normKey() 必须保持一致，改动需同步两处。
    规则：去商标符 → 压空白 → 小写 → 去尾部「CPU @ x.xxGHz」。
    显示仍用原串，这里只产生比较用的 key。
    """
    if not s:
        return ""
    s = re.sub(r"\((?:R|TM)\)", "", s, flags=re.I)
    s = s.replace("®", "").replace("™", "")
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = re.sub(r"\s*cpu\s*@\s*[\d.]+ghz$", "", s)
    return s


def short_cpu(s):
    return re.sub(r"^(Intel Core |Intel |AMD )", "", s or "")


def short_gpu(s):
    return re.sub(r"^(NVIDIA GeForce |NVIDIA )", "", s or "")


def sample_gap_sec(card):
    """实际采样间隔 = 时长 / (样本数-1)。

    不能相信 generator.sampleIntervalSec —— 那是声明值（恒定 1），
    而采样定时器会抖：真卡片实测 944.5 / 744 ≈ 1.27 秒。
    """
    view = card.get("view") or {}
    dur = view.get("durationSec")
    n = view.get("sampleCount") or 0
    if not dur or n < 2:
        return None
    return float(dur) / (n - 1)


def build_entry(card, issue, author, submitted_at, repo):
    """把成绩卡包成 board.json 里的一条记录（卡片 + 派生索引）。"""
    hw = card.get("hardware") or {}
    view = card.get("view") or {}
    rec = card.get("recording") or {}
    cpu, gpu = hw.get("cpu", ""), hw.get("gpu", "")
    return {
        "issue": int(issue),
        "issueUrl": "%s/issues/%s" % (repo.rstrip("/"), issue),
        "author": author,
        "owner": card.get("owner") or "",
        "scene": "",
        "submittedAt": submitted_at,
        "durSec": view.get("durationSec"),
        "sampleCount": view.get("sampleCount"),
        "recordingSha256": rec.get("sha256"),
        "cpuKey": norm_hw(cpu),
        "gpuKey": norm_hw(gpu),
        "card": card,
    }
