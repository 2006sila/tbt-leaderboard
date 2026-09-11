# ThinkBook 传感器评分榜

用 [TBTS](../) 记录一段真实使用过程，导出成绩卡，提交上来就能上榜。

**站点**：https://2006sila.github.io/tbt-leaderboard/
**榜单**：[`BOARD.md`](BOARD.md) · [`web/data/board.json`](web/data/board.json)

---

## 这是什么榜

这里**没有固定的测试程序**。你跑什么、跑多久、开什么画质，都由你自己决定 ——
所以这份榜比的不是"谁的机器更强"，而是**同一套配置之间的调校差异**。

绝对性能由硬件决定，ThinkBook 各 SKU 之间差得太多，混在一起排总分没有意义。
**请务必用「同配置视图」比较**（榜单页把 CPU 和 GPU 同时选中）。

> ⚠️ **所有成绩均为用户自报，未经复算核验。**
> 机器人只校验成绩卡的自洽性与门槛，**不验证跑法**。请勿作为购机依据。

## 怎么提交

1. **跑一段** —— 用 TBTS 录制至少 15 分钟，建议插电 + 性能模式，跑你平时真跑的东西。
2. **导出成绩卡** —— 评分页点「导出评分」存成文件，或点「复制」把内容放进剪贴板。
3. **发 issue** —— 点 [新建提交](https://github.com/2006sila/tbt-leaderboard/issues/new?template=submit-score.md&labels=submission)，
   光标点进代码块按 <kbd>Ctrl</kbd>+<kbd>V</kbd>，补好标题，提交。
   也可以**把导出的 `.json` 文件直接拖进提交框**，机器人会自动下载解析。
4. **等机器人** —— 几十秒内回帖告知结果；通过就上榜，没过会写明原因。

提交需要 GitHub 账号。同一个人可以提交多条成绩（换机器、换场景都算），
但**同一份记录文件只能提交一次** —— 靠记录的 SHA-256 指纹去重。

## 收录门槛

门槛值定义在 [`web/data/policy.json`](web/data/policy.json)，机器人和网页都读这一份。

| 条件 | 值 | 怎么判 |
|---|---|---|
| 记录时长 | ≥ 15 分钟 | `view.durationSec` |
| 含 FPS 数据 | 必须 | `confidence.hasFps` |
| 数据充足 | 非「数据不足」 | `confidence.insufficient` |
| 实际采样间隔 | ≤ 5 秒 | `durationSec / (sampleCount - 1)` |
| 记录指纹 | 必须存在且未重复 | `recording.sha256` |

**插电 / 电源模式不做硬校验**（成绩卡里没有这两个字段），请在提交时写进「备注」。
采样间隔用**实测值**而不是成绩卡声明的 `generator.sampleIntervalSec` —— 采样定时器会抖，
声明值恒为 1 秒，实测通常在 1.2～1.3 秒之间。

## 榜单结构

- **主榜** —— 全部成绩按总分降序，可用场景 / CPU / GPU / 等级筛选。
- **同配置视图** —— 把 CPU 和 GPU 同时选中（或点行内的「只看同配置」），
  只在**归一化后 CPU + GPU 完全相同**的池子里排名。
  池内只有 1 条时会明确提示"名次没有比较意义"。

分组键是 `norm(cpu) | norm(gpu)`，归一化规则：去 `(R)`/`(TM)`/`®`/`™` → 压空白 →
转小写 → 去尾部 `CPU @ x.xxGHz`。实现在
[`tools/tbts_card.py`](tools/tbts_card.py) 的 `norm_hw()`，
[`web/app.js`](web/app.js) 的 `normKey()` 必须与它一致。

## 仓库结构

```
web/                     站点（GitHub Pages 直接发布这个目录）
  index.html  style.css  app.js
  data/board.json        榜单数据 —— 由机器人写入，请勿手工编辑
  data/policy.json       收录门槛（唯一出处）
tools/
  tbts_card.py           成绩卡解析 / 规范化 / 自校验
  verify_submission.py   机器人：校验一条提交并写榜
  gen_demo_data.py       生成本地预览用的演示数据
  render_check.js        前端回归自检（需要 jsdom）
  selftest_card.py       成绩卡模块自检（含 payloadSha256 逐字节验证）
.github/workflows/
  verify.yml             收到 submission issue → 校验 → 写榜 → 回帖
  publish.yml            发布 web/ 到 Pages
BOARD.md                 机器生成的榜单快照（给人看的，可 diff）
```

## 关于 `payloadSha256`

成绩卡里有一个 `integrity.payloadSha256`。它**不是防伪签名**，
只是防"改了数字忘改哈希"这类低级篡改 —— 算法公开，任何人都能造出一份完全自洽的假卡。

它成立的前提是"解析 → 再序列化"逐字节可复现。`tools/tbts_card.py` 复刻了桌面端
C# `System.Text.Json` 的三条规则（键序 / 最短往返数字格式 / emoji 转 surrogate pair），
已在真实成绩卡上逐字节验证。**格式已冻结，改动会作废所有历史成绩卡。**

唯一可事后复算的锚点是 `recording.sha256` —— 它指向那一段真实录制。

## 本地预览

```bash
cd web && python -m http.server 8137
# 打开 http://127.0.0.1:8137/
```

直接双击 `index.html` 会被浏览器的跨域策略拦住（页面用 `fetch` 读 `data/board.json`）。

跑一遍自检：

```bash
python tools/selftest_card.py                                  # 成绩卡模块
DRY_RUN=1 ISSUE_BODY="$(cat /tmp/card.md)" python tools/verify_submission.py
node tools/render_check.js                                     # 需要 jsdom
```

## 许可

[Mozilla Public License 2.0](LICENSE)，与桌面端 TBTS 保持一致。
