#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对榜单里的存量成绩补跑/刷新数值合理性检查，把标记字段写回 board.json。

什么时候用
----------
sanity_check() 只会作用于**新提交**。碰到下面情况，榜上的老数据不会自动带标记：

  · 判据是后加的（如 policy v3 引入数值合理性检查时，榜上已有成绩）
  · 阈值调整后想让存量按新规则重算
  · 手工编辑 board.json 后想校一遍

用法
----
    # 只看看会标哪些（不落盘，也不改 BOARD.md）
    python tools/retrofit_sanity.py --check

    # 就地刷新本仓库的 web/data/board.json 与 BOARD.md
    python tools/retrofit_sanity.py

    # 处理外部文件（例如刚从线上拉下来的副本）
    python tools/retrofit_sanity.py --input /tmp/board.json --output /tmp/board.json

注意
----
只增删本工具自己的三个标记字段（suspicious / sanityFlags / sanityNotes），
其它字段一律不动；未命中的条目**不写** suspicious: false，保持与旧数据一致。
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import verify_submission as vs  # noqa: E402


def refresh(board, policy):
    """就地为命中的条目写入标记，返回本轮标记明细。"""
    marked, cleared = [], []
    for e in board.get("entries") or []:
        flags, msgs = vs.sanity_check(e.get("card") or {}, policy)
        if flags:
            e["suspicious"] = True
            e["sanityFlags"] = flags
            e["sanityNotes"] = msgs
            marked.append((e.get("issue"), e.get("owner") or e.get("author"), flags))
        elif e.pop("suspicious", None) or e.pop("sanityFlags", None) or e.pop("sanityNotes", None):
            cleared.append((e.get("issue"), e.get("owner") or e.get("author")))
    return marked, cleared


def main(argv=None):
    ap = argparse.ArgumentParser(description="刷新榜单存量成绩的数值合理性标记")
    ap.add_argument("--input", help="输入 board.json（默认本仓库 web/data/board.json）")
    ap.add_argument("--output", help="输出路径（默认与输入相同；配 --check 时忽略）")
    ap.add_argument("--check", action="store_true", help="只报告，不写文件")
    args = ap.parse_args(argv)

    src = pathlib.Path(args.input) if args.input else vs.BOARD_PATH
    dst = pathlib.Path(args.output) if args.output else src

    policy = vs.load_policy()
    board = json.loads(src.read_text(encoding="utf-8"))

    print("数据源：%s" % src)
    print("policy：version=%s sanity.enabled=%s"
          % (policy.get("policyVersion"), (policy.get("sanity") or {}).get("enabled")))
    print("成绩条数：%d" % len(board.get("entries") or []))

    marked, cleared = refresh(board, policy)

    print("\n命中并标记：%d 条" % len(marked))
    for issue, who, flags in marked:
        print("  · #%s %s -> %s" % (issue, who, ", ".join(flags)))
    if cleared:
        print("\n清除旧标记（现已不符合判据）：%d 条" % len(cleared))
        for issue, who in cleared:
            print("  · #%s %s" % (issue, who))
    if not marked and not cleared:
        print("\n（没有需要变更的条目）")

    if args.check:
        print("\n--check 模式，未写入任何文件。")
        return 0

    board["generatedAt"] = vs.now_iso()
    dst.write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print("\n已写入 %s" % dst)

    # BOARD.md 只在本仓库就地刷新时同步（外部文件不碰镜像）
    if not args.input:
        vs.BOARD_MD_PATH.write_text(vs.render_board_md(board), encoding="utf-8", newline="\n")
        print("已重建 %s" % vs.BOARD_MD_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
