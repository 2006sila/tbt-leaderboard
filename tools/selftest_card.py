#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tbts_card 自检 —— 重点是 payloadSha256 必须与桌面端 C# 逐字节一致。

tools/fixtures/card_vector.json 是**冻结的测试向量**，它同时覆盖了三个最容易出错的边界：

  · 整数值的 double —— C# 把 68.0 写成 "68"，Python 默认会写成 "68.0"
  · BMP 之外的 emoji —— C# 写成 \\uD83D\\uDCBB，Python 默认直出 💻
  · null 字段与含 " \\ \\t \\n 的字符串

期望哈希是用桌面端同款 System.Text.Json 配置（WriteIndented=false +
UnsafeRelaxedJsonEscaping + 同序 DTO）算出来的 —— 方向是 C# → Python，不是自证循环。

⚠️ 如果这个哈希对不上，说明序列化规则被改坏了。**不要去改期望值**：
那意味着所有已导出的历史成绩卡都会校验失败，宁可让测试红着。

用法：
    python tools/selftest_card.py [额外成绩卡.json ...]
"""

import hashlib
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tbts_card as tc  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
VECTOR = HERE / "fixtures" / "card_vector.json"

# ← 由桌面端 System.Text.Json 算出（2026-09-11）
EXPECT_SHA256 = "b0e7077a6ef10dfa0ef17c0401616c895a2657e8b037c33751d5fef785558f28"
EXPECT_BYTES = 2011

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print("%s %s%s" % ("  ok  " if cond else "  FAIL", name,
                       ("  ← " + extra) if extra and not cond else ""))


def main():
    print("== 序列化向量（与 C# 逐字节一致）==")
    raw = VECTOR.read_text(encoding="utf-8")
    card = tc.parse_card(raw)
    payload = tc.canonical_payload(card)
    got_sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    got_bytes = len(payload.encode("utf-8"))

    check("payload SHA-256 与 C# 一致", got_sha == EXPECT_SHA256,
          "\n        expect %s\n        actual %s" % (EXPECT_SHA256, got_sha))
    check("payload UTF-8 字节数一致", got_bytes == EXPECT_BYTES,
          "expect %d, actual %d" % (EXPECT_BYTES, got_bytes))

    # 逐条盯住三个坑
    check("整数值 double 不带小数点（68.0 → 68）", '"total":68' in payload)
    check("emoji 转 surrogate pair", "\\uD83D\\uDC31" in payload and "🐱" not in payload)
    check("中文原样输出（非 ASCII 不转义）", "猫娘" in payload)
    check("null 字段写成 null（不是省略）", '"gpuHeadroomC":null' in payload)
    check("integrity 在载荷里恒为 null", payload.endswith('"integrity":null}'))
    check("引号与反斜杠按 JSON 规则转义", '\\"引号\\"' in payload and "\\\\反斜杠" in payload)
    check("制表符/换行符用短转义", "\\t换行符\\n" in payload)

    print("\n== 结构校验 ==")
    for bad, why in [
        ("{}", "空的顶层对象"),
        ('{"format":"other","version":1}', "format 不对"),
        ('{"format":"tbts-score","version":2}', "版本不支持"),
        ("not json at all", "不是 JSON"),
    ]:
        try:
            tc.parse_card(bad)
            check("拒绝：%s" % why, False, "竟然通过了")
        except tc.CardError:
            check("拒绝：%s" % why, True)

    missing = json.loads(raw)
    missing["integrity"]["payloadSha256"] = "0" * 64
    ok, _exp, act = tc.verify_payload(missing)
    check("篡改后哈希校验失败", not ok and len(act) == 64)

    missing2 = json.loads(raw)
    missing2["score"]["total"] = 99.9          # 改数字但不改哈希
    ok2, _, _ = tc.verify_payload(missing2)
    check("改数字后哈希校验失败", not ok2)

    print("\n== 派生与归一化 ==")
    check("norm_hw 去 (R)/(TM)",
          tc.norm_hw("Intel(R) Core(TM) i7-13700H CPU @ 2.40GHz") == "intel core i7-13700h")
    check("norm_hw 去 ® / ™",
          tc.norm_hw("AMD Ryzen™ 9 8945HS®") == "amd ryzen 9 8945hs")
    check("norm_hw 压空白",
          tc.norm_hw("  NVIDIA   GeForce  RTX 5060  ") == "nvidia geforce rtx 5060")
    check("norm_hw 空值安全", tc.norm_hw("") == "" and tc.norm_hw(None) == "")
    check("norm_hw 大小写归一",
          tc.norm_hw("AMD Ryzen 9 8945HS") == tc.norm_hw("amd ryzen 9 8945hs"))
    check("同型号不同写法归到同一池",
          tc.norm_hw("Intel(R) Arc(TM) 140T GPU") == tc.norm_hw("intel arc 140t gpu"))

    check("short_cpu 去厂商前缀", tc.short_cpu("Intel Core Ultra 7 255HX") == "Ultra 7 255HX")
    check("short_gpu 去厂商前缀",
          tc.short_gpu("NVIDIA GeForce RTX 5060 Laptop GPU") == "RTX 5060 Laptop GPU")

    check("采样间隔用实测值（不信声明值）",
          abs(tc.sample_gap_sec(card) - 1200.5 / 945) < 1e-9)
    check("样本数不足时采样间隔为 None",
          tc.sample_gap_sec({"view": {"durationSec": 100, "sampleCount": 1}}) is None)

    print("\n== issue 正文提取 ==")
    body = "前言\n\n```json\n{\"format\":\"tbts-score\"}\n```\n\n后记"
    check("取出 json 代码块",
          tc.extract_json_block(body).strip() == '{"format":"tbts-score"}')
    check("无代码块时抛 CardError",
          _raises(lambda: tc.extract_json_block("只有文字，没有代码块")))
    check("优先取 json 块（跳过其它语言的块）",
          tc.extract_json_block("```sh\necho hi\n```\n```json\n{\"a\":1}\n```").strip() == '{"a":1}')

    print("\n== 真实成绩卡（若提供）==")
    extra = sys.argv[1:]
    if not extra:
        print("  （跳过；可传入成绩卡路径做交叉验证）")
    for p in extra:
        try:
            d = json.loads(pathlib.Path(p).read_text(encoding="utf-8-sig"))
            ok, exp, act = tc.verify_payload(d)
            check("真实卡片 %s" % pathlib.Path(p).name, ok,
                  "expect %s actual %s" % (exp, act))
        except Exception as e:
            check("真实卡片 %s" % pathlib.Path(p).name, False, repr(e))

    print("\n%s  通过 %d / 失败 %d" % ("=" * 46, len(PASS), len(FAIL)))
    return 1 if FAIL else 0


def _raises(fn):
    try:
        fn()
        return False
    except tc.CardError:
        return True


if __name__ == "__main__":
    sys.exit(main())
