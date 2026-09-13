#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成绩提交校验机器人。

由 .github/workflows/verify.yml 在收到带 `submission` 标签的 issue 时调用。
读环境变量拿 issue 内容，校验通过就把它写进 web/data/board.json 并重建 BOARD.md。

环境变量
--------
ISSUE_BODY         issue 正文
ISSUE_NUMBER       issue 号
ISSUE_AUTHOR       提交者 GitHub 登录名（身份标识：真实账号，不可伪造）
ISSUE_TITLE        issue 标题（用来识别场景标签）
ISSUE_CREATED_AT   issue 创建时间（作为提交时间；比卡片自带的时间可信）
REPO               owner/name
REPO_OWNER         仓库所有者登录名（policy 没配 notify.mention 时，异常提醒 @ 他）
DRY_RUN            非空时只校验不落盘（本地测试用）

产物
----
verify_result.json   校验结果 + 现成的回帖 Markdown（workflow 直接贴）
GITHUB_OUTPUT        ok=true/false、stage、suspicious=true/false、notify=true/false
退出码恒为 0（除未预期异常），避免 CI 因"校验不通过"变红。

约定
----
数值合理性检查（sanity_check）**只标记、不拦截**：命中的成绩照样上榜，
额外打 suspicious 标签并在回帖里列出可疑点。它是"提高造假成本"，
不是防伪 —— 真正的核验要拿原始记录复算。

命中时默认还会**提醒维护者**：回帖里 @ 一句，并由 workflow 把 issue 指派给他
（GitHub 对被指派/被 @ 的人推送站内与邮件通知）。开关与 @ 对象见
policy.sanity.notify；提交者本人就是维护者时按 unlessSelf 跳过。
"""

import datetime
import json
import os
import pathlib
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tbts_card as tc  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
BOARD_PATH = ROOT / "web" / "data" / "board.json"
POLICY_PATH = ROOT / "web" / "data" / "policy.json"
BOARD_MD_PATH = ROOT / "BOARD.md"
RESULT_PATH = ROOT / "verify_result.json"

REPO_URL = "https://github.com/" + os.environ.get("REPO", "2006sila/tbt-leaderboard")


# ────────────────────────────────── 小工具 ──────────────────────────────────

def fmt_dur(sec):
    if not sec:
        return "—"
    sec = float(sec)
    m, s = divmod(int(round(sec)), 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return "%d 小时 %d 分" % (h, m)
    return "%d 分 %d 秒" % (m, s)


def fmt_num(v, digits=1):
    if v is None:
        return "—"
    try:
        return ("%." + str(digits) + "f") % float(v)
    except (TypeError, ValueError):
        return "—"


def total_of(entry):
    try:
        return float(((entry.get("card") or {}).get("score") or {}).get("total") or 0)
    except (TypeError, ValueError):
        return 0.0


def extract_scene(title, body, policy):
    """场景只当筛选标签用，从标题优先识别；识别不到就留空（不拒收）。"""
    allowed = policy.get("scenes") or []
    for src in (title or "", body or ""):
        for s in allowed:
            if re.search(r"(?<![A-Za-z0-9])%s(?![0-9])" % re.escape(s), src):
                return s
    return ""


def fail(stage, headline, message, hint="", detail=None):
    lines = ["❌ **未通过校验：%s**" % headline, "", message]
    if hint:
        lines += ["", "**怎么改**：%s" % hint]
    if detail:
        lines += ["", "<details>", "<summary>校验详情</summary>", ""]
        lines += detail
        lines += ["", "</details>"]
    lines += ["", "> 机器人只校验成绩卡本身的自洽性与门槛，不验证跑法。"]
    return {
        "ok": False,
        "stage": stage,
        "headline": headline,
        "comment": "\n".join(lines),
    }


# ────────────────────────────────── 校验 ──────────────────────────────────

def validate(card, policy):
    """逐项校验。返回 (错误 dict | None, 明细列表)。"""
    detail = []
    view = card.get("view") or {}
    conf = card.get("confidence") or {}
    rec = card.get("recording") or {}

    detail.append("- 载荷哈希：self-consistent")

    # 1) 时长
    dur = view.get("durationSec")
    need = policy.get("minDurationSec", 600)
    detail.append("- 时长：%s（门槛 %s）" % (fmt_dur(dur), fmt_dur(need)))
    if dur is None:
        return fail(
            "duration", "缺少时长信息",
            "成绩卡里没有 `view.durationSec`，无法判断记录长度。",
            "请在 TBTS 评分页重新导出一次成绩卡。",
            detail,
        ), detail
    if float(dur) < float(need):
        return fail(
            "duration", "时长不足",
            "本次记录 **%s**（%.1f 秒），低于收录门槛 **%s**。"
            % (fmt_dur(dur), float(dur), fmt_dur(need)),
            "用 TBTS 重新录制一段至少 %s 的记录，重新导出成绩卡后再提交。" % fmt_dur(need),
            detail,
        ), detail

    # 2) 数据是否充足
    if policy.get("rejectInsufficient", True) and conf.get("insufficient"):
        return fail(
            "insufficient", "数据不足",
            "成绩卡自述 `confidence.insufficient = true`，说明采样量不够、指标不可靠。",
            "录制更长的记录（建议 20 分钟以上）再试。",
            detail,
        ), detail

    # 3) 必须含 FPS
    if policy.get("requireHasFps", True) and not conf.get("hasFps"):
        return fail(
            "hasfps", "记录里没有帧率数据",
            "成绩卡自述 `confidence.hasFps = false`。没有帧率的记录无法与其它成绩横向比较。",
            "录制时保持有画面在动（跑游戏、播视频都行），再导出一次。",
            detail,
        ), detail
    detail.append("- 含 FPS 数据：是")

    # 4) 采样密度（用实测值，不信声明值）
    gap = tc.sample_gap_sec(card)
    max_gap = policy.get("maxSampleGapSec", 5)
    n = view.get("sampleCount") or 0
    detail.append("- 样本数：%d，实际采样间隔：%s"
                  % (n, "—" if gap is None else fmt_num(gap, 2) + " 秒"))
    if gap is None or n < 2:
        return fail(
            "sampling", "采样数据不完整",
            "样本数不足（`view.sampleCount = %d`），无法确认采样密度。" % n,
            "重新录制一段记录后再导出。",
            detail,
        ), detail
    if gap > float(max_gap):
        return fail(
            "sampling", "采样间隔过大",
            "实际采样间隔 **%s 秒**（%d 个样本 / %s），超过上限 **%s 秒**。"
            "采样太稀疏时，帧时间类指标（最差 1%% / P99 / 卡顿占比）没有意义。"
            % (fmt_num(gap, 2), n, fmt_dur(dur), fmt_num(max_gap, 0)),
            "确认录制过程中 TBTS 没有被系统挂起（比如睡眠、切到独显时的驱动重启），重新录一段。",
            detail,
        ), detail

    # 5) 记录指纹
    sha = (rec.get("sha256") or "").strip().lower()
    if not sha:
        return fail(
            "recording", "成绩卡里没有记录指纹",
            "`recording.sha256` 为空，无法确认这份成绩对应哪一段真实录制，"
            "也无法防止同一份记录被重复提交。",
            "导出成绩卡前请确认 TBTS 已经加载了记录文件（评分页顶部会显示记录名）。",
            detail,
        ), detail
    if len(sha) != 64 or not re.fullmatch(r"[0-9a-f]{64}", sha):
        return fail(
            "recording", "记录指纹格式不对",
            "`recording.sha256` 不是 64 位十六进制串。",
            "重新导出成绩卡后再提交；若反复出现，请反馈。",
            detail,
        ), detail
    detail.append("- 记录：`%s`（%s）"
                  % (rec.get("fileName") or "—",
                     ("%.1f KB" % (rec["bytes"] / 1024)) if rec.get("bytes") else "—"))

    return None, detail


# ──────────────────────────── 数值合理性（异常标记）────────────────────────────

def sanity_check(card, policy):
    """数值合理性检查 —— 只标记、不拦截。

    目标是「物理不可能」级信号：真实记录必然有帧率梯度、有方差、有事件；
    而"改 tbt 输出文件 → 让 TBTS 重新导出"造出来的高分记录往往一路完美。
    命中只打标记（suspicious 标签 + 榜单角标），不影响收录。

    返回 (命中 key 列表, 中文说明列表)；没命中返回 ([], [])。
    """
    cfg = policy.get("sanity") or {}
    if not cfg.get("enabled", True):
        return [], []

    hits = []
    metrics = card.get("metrics") or {}
    events = card.get("events") or {}
    rec = card.get("recording") or {}
    parts = (card.get("score") or {}).get("parts") or {}

    def num(v):
        try:
            return None if v is None else float(v)
        except (TypeError, ValueError):
            return None

    # 1) 记录文件名：可疑字样 / 命名不合规
    fn = (rec.get("fileName") or "").strip()
    for word in cfg.get("filenameRedFlags") or []:
        if str(word).lower() in fn.lower():
            hits.append(("filename_flag",
                         "记录文件名含可疑字样 `%s`：`%s`" % (word, fn)))
            break
    pat = cfg.get("filenamePattern")
    if fn and pat:
        try:
            if not re.fullmatch(pat, fn):
                hits.append(("filename_pattern",
                             "记录文件名不符合 TBTS 默认命名规则：`%s`" % fn))
        except re.error:
            pass

    # 2) 帧率分布：三者完全相等 / 单调性违约
    avg, low, worst = (num(metrics.get("fpsAvg")),
                       num(metrics.get("fps1LowAvg")),
                       num(metrics.get("fpsWorst1Pct")))
    if avg is not None and low is not None and worst is not None and avg == low == worst:
        hits.append(("fps_identical",
                     "帧率均值 / 1%% Low / 最差 1%% 三者完全相等（%.1f）"
                     "——真实记录必然有梯度" % avg))
    if avg is not None and low is not None and low > avg:
        hits.append(("fps_monotonic",
                     "1%% Low（%.1f）高于均值（%.1f）——逻辑上不可能" % (low, avg)))
    if low is not None and worst is not None and worst > low:
        hits.append(("fps_monotonic",
                     "最差 1%%（%.1f）高于 1%% Low（%.1f）——逻辑上不可能" % (worst, low)))

    # 3) 零方差：帧时间无抖动、无卡顿、无事件
    cv = num(metrics.get("frametimeCv"))
    sp = num(metrics.get("stutterPct"))
    if cv == 0 and sp == 0 and not (events.get("eventCount") or 0):
        hits.append(("zero_variance",
                     "帧时间变异系数为 0、卡顿占比为 0、事件数为 0"
                     "——真实运行不可能毫无抖动"))

    # 4) 延迟低于物理下限
    lat = num(metrics.get("latencyP99Ms"))
    floor = cfg.get("minLatencyP99Ms", 1)
    if lat is not None and lat < float(floor):
        hits.append(("latency",
                     "P99 延迟 %.2f ms 低于物理下限 %s ms" % (lat, floor)))

    # 5) 六项分项全部满分
    part_keys = ("performance", "smoothness", "thermal",
                 "stability", "efficiency", "noise")
    vals = [num(parts.get(k)) for k in part_keys]
    threshold = float(cfg.get("allPartsHigh", 99.5))
    if all(v is not None and v >= threshold for v in vals):
        hits.append(("all_parts_max",
                     "六项分项全部 ≥ %s——真实机器不可能项项满分" % threshold))

    return [k for k, _ in hits], [msg for _, msg in hits]


def check_duplicate(board, sha):
    for e in board.get("entries") or []:
        if (e.get("recordingSha256") or "").lower() == sha:
            return e
    return None


# ────────────────────────────────── 写榜 ──────────────────────────────────

def load_policy():
    with open(POLICY_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_board():
    if BOARD_PATH.exists():
        with open(BOARD_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"version": 1, "demo": False, "generatedAt": "", "entries": []}


def now_iso():
    """当前时间（北京时间，ISO 8601 秒精度）。"""
    return datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=8))
    ).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def save_board(board):
    board["generatedAt"] = now_iso()
    BOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BOARD_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(board, f, ensure_ascii=False, indent=2)
        f.write("\n")


def render_board_md(board):
    entries = sorted(board.get("entries") or [], key=lambda e: -total_of(e))
    out = [
        "# 榜单（机器生成）",
        "",
        "> 本文件由 `.github/workflows/verify.yml` 自动重建，**请勿手工编辑**。",
        "> 网页数据在 [`web/data/board.json`](web/data/board.json)。",
        "",
        "所有成绩均为**用户自报**，未经复算核验；机器人只校验成绩卡的自洽性与门槛，不验证跑法。",
        "",
        "标有 ⚠️ 的成绩被机器人判定数值异常（详见网页端展开详情），已照常收录，仅作提示。",
        "",
        "| # | 署名 | 总分 | 等级 | CPU | GPU | 时长 | 场景 | 提交 | issue |",
        "|---:|---|---:|:--:|---|---|---:|:--:|---|---:|",
    ]
    for i, e in enumerate(entries, 1):
        card = e.get("card") or {}
        hw = card.get("hardware") or {}
        view = card.get("view") or {}
        owner = (e.get("owner") or e.get("author") or "匿名").replace("|", "\\|")
        if e.get("suspicious"):
            owner = "⚠️ " + owner
        out.append("| %d | %s | %.1f | %s | %s | %s | %s | %s | %s | [#%s](%s) |" % (
            i, owner,
            total_of(e), (card.get("score") or {}).get("grade", "—"),
            tc.short_cpu(hw.get("cpu", "")), tc.short_gpu(hw.get("gpu", "")),
            fmt_dur(view.get("durationSec")), e.get("scene") or "—",
            (e.get("submittedAt") or "")[:10], e.get("issue"), e.get("issueUrl") or "#",
        ))
    if not entries:
        out.append("| | _还没有成绩_ | | | | | | | | |")
    out.append("")
    return "\n".join(out)


# ────────────────── 附件下载（拖拽上传的成绩卡文件） ──────────────────

# GitHub 会把拖进提交框的文件转成 user-attachments 链接。只认这个域，
# 不碰正文里的其它 URL —— 机器人不该替 issue 作者去请求任意地址。
ATTACH_RE = re.compile(
    r"https://github\.com/user-attachments/(?:assets|files)/[^\s\)\]\"'<>]+")
ATTACH_MAX_BYTES = 256 * 1024    # 成绩卡只有几 KB；超限几乎肯定是拖错了文件
ATTACH_MAX_TRIES = 3


def find_attachments(body):
    return ATTACH_RE.findall(body or "")


def fetch_attachment(url):
    """下载一个附件 → (文本, None)；失败 → (None, 原因)。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "tbts-verify-bot"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read(ATTACH_MAX_BYTES + 1)
    except Exception as exc:
        return None, "%s（%s）" % (url, exc.__class__.__name__)
    if len(data) > ATTACH_MAX_BYTES:
        return None, "%s（超过 %d KB 上限）" % (url, ATTACH_MAX_BYTES // 1024)
    return data.decode("utf-8", errors="replace"), None


def card_from_attachments(body):
    """依次尝试正文里的附件 → (文本, None)；全失败 → (None, 原因列表)；没有附件 → (None, None)。"""
    urls = find_attachments(body)
    if not urls:
        return None, None
    errs = []
    for url in urls[:ATTACH_MAX_TRIES]:
        text, err = fetch_attachment(url)
        if err is None and text and text.strip():
            return text, None
        errs.append(err or "%s（内容为空）" % url)
    return None, errs


# ────────────────────────────────── 主流程 ──────────────────────────────────

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    body = os.environ.get("ISSUE_BODY", "")
    try:
        issue = int(os.environ.get("ISSUE_NUMBER", "0") or 0)
    except ValueError:
        issue = 0
    author = os.environ.get("ISSUE_AUTHOR", "") or "unknown"
    # 仓库所有者 —— 异常成绩要提醒的人（policy 没显式配 mention 时用它）
    repo_owner = (os.environ.get("REPO_OWNER", "") or "").strip().lstrip("@")
    title = os.environ.get("ISSUE_TITLE", "")
    created = os.environ.get("ISSUE_CREATED_AT", "") or datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dry = bool(os.environ.get("DRY_RUN"))

    policy = load_policy()
    board = load_board()

    # 1) 取出并解析成绩卡
    #    优先代码块；代码块缺失或还是模板占位文字时，改试拖拽上传的附件。
    raw = None
    block_err = None
    try:
        cand = tc.extract_json_block(body)
        if cand.lstrip().startswith("{"):
            raw = cand
        else:
            block_err = "代码块里不是成绩卡内容（像是没删掉的模板占位文字）。"
    except tc.CardError as e:
        block_err = str(e)

    if raw is None:
        raw, attach_errs = card_from_attachments(body)
        if raw is None:
            if attach_errs:
                detail = ("代码块里没有有效的成绩卡；尝试下载附件也没成功 —— %s。"
                          % "；".join(attach_errs))
            elif block_err:
                detail = block_err
            else:
                detail = "正文里既没有 ```json 代码块，也没有可下载的附件。"
            result = fail(
                "format", "成绩卡无法解析", detail,
                "把导出的成绩卡完整粘进 ```json 代码块（替换模板里的占位文字）；"
                "或把 .json 文件直接拖进提交框，机器人会自己下载解析。",
            )
            return finish(result)

    try:
        card = tc.parse_card(raw)
    except tc.CardError as e:
        result = fail("format", "成绩卡无法解析", str(e),
                      "成绩卡内容必须完整、未经编辑；请重新导出后再提交。")
        return finish(result)

    # 2) 载荷哈希自洽
    ok, exp, act = tc.verify_payload(card)
    if not ok:
        result = fail(
            "integrity", "完整性校验失败",
            "成绩卡内容与它自己声明的载荷哈希对不上，说明文件在导出后被改动过"
            "（哪怕只改了一个数字）。",
            "请不要手工编辑成绩卡；在 TBTS 评分页重新导出一次再提交。",
            ["- 文件声明：`%s`" % exp, "- 实际复算：`%s`" % act],
        )
        return finish(result)

    # 3) 门槛校验
    err, detail = validate(card, policy)
    if err:
        return finish(err)

    # 4) 去重（同一份记录只能提交一次）
    # 榜上还是演示数据时跳过这步：演示条目是随手编的，不能拿它当真去拦真实提交。
    rec = card.get("recording") or {}
    sha = (rec.get("sha256") or "").lower()
    dup = None if board.get("demo") else check_duplicate(board, sha)
    if dup:
        result = fail(
            "duplicate", "这份记录已经提交过了",
            "同一段录制只能上交一次（记录指纹 `%s…` 已在案）。" % sha[:16],
            "如果你是想刷新成绩，请重新录一段新的记录再提交。",
            detail + ["- 已有记录来自 issue #%s（提交者 @%s）"
                      % (dup.get("issue"), dup.get("author"))],
        )
        return finish(result)

    # 5) 数值合理性 —— 只标记、不拦截（命中照样上榜，额外打异常标签）
    flags, flag_msgs = sanity_check(card, policy)
    suspicious = bool(flags)

    # 命中时是否提醒维护者：issue 指派 + 回帖 @（配置见 policy.sanity.notify）
    notify_cfg = (policy.get("sanity") or {}).get("notify") or {}
    notify_mention = (notify_cfg.get("mention") or "").strip().lstrip("@") or repo_owner
    notify = bool(
        suspicious
        and notify_cfg.get("enabled", True)
        and notify_mention
        and not (notify_cfg.get("unlessSelf", True)
                 and notify_mention.lower() == author.lower())
    )
    notify_assign = bool(notify and notify_cfg.get("assign", True))

    # 6) 通过 —— 入榜
    entry = tc.build_entry(card, issue, author, created, REPO_URL)
    entry["scene"] = extract_scene(title, body, policy)
    entry["suspicious"] = suspicious
    if suspicious:
        entry["sanityFlags"] = flags
        entry["sanityNotes"] = flag_msgs

    was_demo = bool(board.get("demo"))
    if was_demo:
        # 第一条真实成绩上榜，撤掉演示数据
        board["entries"] = []
        board["demo"] = False
    entries = board.setdefault("entries", [])
    entries.append(entry)

    new_total = total_of(entry)
    rank = 1 + sum(1 for e in entries if e is not entry and total_of(e) > new_total)
    pool = [e for e in entries
            if e.get("cpuKey") == entry["cpuKey"] and e.get("gpuKey") == entry["gpuKey"]]
    pool_rank = 1 + sum(1 for e in pool if e is not entry and total_of(e) > new_total)
    pool_size = len(pool)
    total_n = len(entries)

    hw = card.get("hardware") or {}
    view = card.get("view") or {}
    conf = card.get("confidence") or {}
    flavor = card.get("flavor") or {}
    gap = tc.sample_gap_sec(card)

    lines = [
        "✅ **已上榜**",
        "",
        "| 总分 | 等级 | 时长 | 采样 |",
        "|---:|:--:|---:|---|",
        "| **%s** | %s | %s | %d 个样本 · 间隔 %s 秒 |" % (
            fmt_num(new_total), card["score"].get("grade", "—"),
            fmt_dur(view.get("durationSec")), view.get("sampleCount") or 0,
            fmt_num(gap, 2)),
        "",
        "- 总榜名次：**第 %d 名**（共 %d 条）" % (rank, total_n),
        "- 同配置名次：**第 %d 名**（`%s` + `%s`，池内 %d 条）"
        % (pool_rank, hw.get("cpu", "—"), hw.get("gpu", "—"), pool_size),
    ]
    if entry["scene"]:
        lines.append("- 场景标签：**%s %s**（由标题识别，只作筛选，不影响排名）"
                     % (entry["scene"], (policy.get("sceneLabels") or {}).get(entry["scene"], "")))
    if flavor.get("persona"):
        lines.append("- 趣味评价：由桌面端按当时人设（%s）生成，已一并写入榜单"
                     % flavor["persona"])
    if suspicious:
        lines += [
            "",
            "---",
            "",
            "⚠️ **数值异常提示**",
            "",
            "本成绩**已照常上榜**，但机器人检测到下列数值不符合真实记录的物理规律：",
            "",
        ] + ["- %s" % msg for msg in flag_msgs] + ([
            "",
            "@%s 这条成绩命中了数值合理性检查，请人工复核。" % notify_mention,
        ] if notify else []) + [
            "",
            "> 这是**标记**而非驳回：榜单上会显示异常角标。"
            "若你认为属于误判，请在本 issue 里说明，等待人工复核。",
        ]
    lines += [
        "",
        "榜单与详情：%s" % REPO_URL,
        "",
        "> 成绩为本机自报，未经复算核验。榜单只适合**同配置之间**横向参考。",
        "",
        "<details>",
        "<summary>校验详情</summary>",
        "",
    ] + detail + ["", "</details>"]
    if was_demo:
        lines += ["", "_演示数据已随第一条真实成绩自动撤下。_"]

    if not dry:
        save_board(board)
        BOARD_MD_PATH.write_text(render_board_md(board), encoding="utf-8", newline="\n")

    sanity_cfg = policy.get("sanity") or {}
    return finish({
        "ok": True,
        "stage": "accepted",
        "headline": "已上榜（标记为数值异常）" if suspicious else "已上榜",
        "comment": "\n".join(lines),
        "issue": issue,
        "rank": rank,
        "total": total_n,
        "poolRank": pool_rank,
        "poolSize": pool_size,
        "scene": entry["scene"],
        "recordingSha256": sha,
        "suspicious": suspicious,
        "sanityFlags": flags,
        "sanityLabel": sanity_cfg.get("label", "suspicious"),
        "sanityLabelColor": sanity_cfg.get("labelColor", "d93f0b"),
        "sanityLabelDescription": sanity_cfg.get(
            "labelDescription", "数值存在异常，建议人工复核"),
        "notify": notify,
        "notifyMention": notify_mention if notify else "",
        "notifyAssign": notify_assign,
    })


def finish(result):
    RESULT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write("ok=%s\n" % ("true" if result.get("ok") else "false"))
            f.write("stage=%s\n" % result.get("stage", ""))
            f.write("suspicious=%s\n"
                    % ("true" if result.get("suspicious") else "false"))
            f.write("notify=%s\n"
                    % ("true" if result.get("notify") else "false"))
    print("[verify] ok=%s stage=%s %s"
          % (result.get("ok"), result.get("stage"), result.get("headline", "")))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # 未预期异常：写一份可读的结果，别让 issue 静默卡住
        import traceback
        traceback.print_exc()
        finish({
            "ok": False,
            "stage": "error",
            "headline": "机器人内部错误",
            "comment": "⚠️ **机器人出错了**\n\n校验过程中出现未预期的异常，"
                       "这条提交没有被处理。请 @2006sila 看一下 Actions 日志。\n\n"
                       "```\n%s: %s\n```" % (type(exc).__name__, exc),
        })
        sys.exit(0)
