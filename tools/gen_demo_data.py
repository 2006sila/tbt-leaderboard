# -*- coding: utf-8 -*-
"""生成排行榜演示数据 web/data/board.json。

只是给网页做效果用的假数据 —— 字段结构与真实 tbts-score v1 完全一致，
方便将来把 card 换成真卡片、只保留派生索引逻辑。

用法: python gen_demo_data.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "web", "data", "board.json")

# ---------------------------------------------------------------- 人设文案素材

FLAVOR = {
    "cat": {
        "persona": "猫娘", "face": "🐱",
        "text": "喵~ 这台本本整体表现还不错嘛，主人把它照顾得挺好的说。不过 1%Low 那里有点掉链子哦，喵喵建议清一清后台进程～ 散热保持得挺好，摸摸头，奖励一个猫粮！",
        "feats": [
            "喵！风扇最高 5133 转，主人不觉得吵吗喵？耳朵都要聋掉了啦～",
            "温度余量还有 11°C，说明本本还有余力哦，喵喵觉得可以再压榨一下～",
        ],
    },
    "savage": {
        "persona": "毒舌", "face": "😏",
        "text": "还行吧，不至于扔垃圾桶。帧数看着挺唬人，可惜 1% 那档掉得厉害——平均值就是用来骗自己的，帧率曲线比我的耐心还抖。散热倒还算争气，这点得承认，虽然代价是风扇快起飞了。",
        "feats": [
            "P99 帧时间偏高，说白了就是每隔一会儿卡你一下，别跟我说你感觉不到。",
            "风扇拉满换来温度余量，这笔账算得还行，勉强给个及格。",
        ],
    },
    "praise": {
        "persona": "夸夸", "face": "🥳",
        "text": "哇这台机器很能打啊！帧率稳稳的，散热也压得住，看得出来是台好本子。1%Low 稍微有点小瑕疵，但瑕不掩瑜，整体真的相当不错，值得夸一下！",
        "feats": [
            "风扇转速上去了，但这说明散热在认真工作，不是坏事！",
            "温度余量很宽裕，安安静静就把活干了，赞！",
        ],
    },
    "snarky": {
        "persona": "阴阳怪气", "face": "🙃",
        "text": "哟，帧数真高呢，真是个了不起的数字。可惜打开帧时间曲线一看，那叫一个跌宕起伏。散热倒是没话说——风扇转成那样了当然压得住，这也能算优点的话。",
        "feats": [
            "平均值漂亮得像 PPT，分位数难看得像月底 KPI，你猜哪个是真的？",
            "P99 帧时间嘛，小场面，也就时不时卡那么一下而已。",
        ],
    },
    "butler": {
        "persona": "管家", "face": "🎩",
        "text": "先生，本次运行的各项指标已为您整理完毕。总体表现稳健，平均帧率令人满意；唯最差 1% 帧率稍显不济，或与后台任务有关，建议您闲时清理。散热状况良好，请放心使用。",
        "feats": [
            "风扇峰值已接近本机上限，建议留意积灰情况，适时维护。",
            "温度余量尚属宽裕，无需额外干预。",
        ],
    },
    "doctor": {
        "persona": "老中医", "face": "🩺",
        "text": "嗯……老夫搭脉一看，这台机器底子是好的，就是气血有点虚。脉象（帧时间）时急时缓，恐是后台有杂症缠身。温度倒是平稳，不燥不寒，调养得体。开一剂方子：清后台、少开标签页，忌装十个杀毒软件。",
        "feats": [
            "风扇转数偏旺，恐是热邪不散之气，可清灰以畅其道。",
            "温度余量可观，可视为肺活量尚可，宜常练（常跑）为宜。",
        ],
    },
    "coder": {
        "persona": "程序员", "face": "💻",
        "text": "Code review 结论：性能没问题，arch 清晰，就是有个 flaky 的测试——1%Low 时不时挂。建议加个 retry（清后台）再跑一遍。散热的实现挺 solid，就是 fan curve 写得有点激进。总体 LGTM，附一条 nit。",
        "feats": [
            "平均值绿了，P1 一塌糊涂——典型的均值掩盖了分位数。监控只看 avg 是会出人命的。",
            "风扇转速触顶、噪音告警——用蛮力补窟窿，该调调风扇曲线了。",
        ],
    },
    "savage2": {
        "persona": "毒舌", "face": "😏",
        "text": "又一台想上天的机器。帧数挺好看，可惜帧时间抖得跟我周一的心情一样。散热压住了？那是风扇拿命换的。看在你没蓝屏的份上，给你个良，谢恩吧。",
        "feats": [
            "帧时间波动这么大，你确定不是后台在下东西？",
            "显卡占用率拉满但帧数上不去，瓶颈在哪儿自己想想。",
        ],
    },
    "snarky2": {
        "persona": "阴阳怪气", "face": "🙃",
        "text": "嗯嗯，分数挺高的，真棒。就是不知道这成绩是机器的功劳还是空调的功劳。毕竟室温降两度，什么本子都能变旗舰嘛。",
        "feats": [
            "温度余量这么漂亮，建议顺便报一下室温，我好知道该夸机器还是夸空调。",
            "风扇转速这么温柔，是不是把性能模式忘了开呀？",
        ],
    },
}

# ---------------------------------------------------------------- 记录表
# (owner, author, issue, scene, cpu, cores, threads, gpu, dur, total, grade,
#  parts, metrics, events, hardware_extra, flavor_key, range_idx, note)

CPU = {
    "u7":  ("Intel Core Ultra 7 255HX", 20, 20),
    "u9":  ("Intel Core Ultra 9 275HX", 24, 24),
    "r7":  ("AMD Ryzen 7 8845H", 8, 16),
    "r9":  ("AMD Ryzen 9 8945HS", 8, 16),
    "i7":  ("Intel Core i7-13700H", 14, 20),
    "u5":  ("Intel Core Ultra 5 225H", 14, 14),
}
GPU = {
    "5060": "NVIDIA GeForce RTX 5060 Laptop GPU",
    "5070": "NVIDIA GeForce RTX 5070 Laptop GPU",
    "4060": "NVIDIA GeForce RTX 4060 Laptop GPU",
    "4070": "NVIDIA GeForce RTX 4070 Laptop GPU",
    "4050": "NVIDIA GeForce RTX 4050 Laptop GPU",
    "arc":  "Intel Arc 130T GPU",
}
SCENE_RANGE = {"S1": "全部时间", "S2": "全部时间"}

ROWS = [
    # owner, author, issue, scene, cpu, gpu, dur, total, grade, parts, metrics, events, flavor, submittedAt
    dict(owner="咕咕咕咕", author="octocat", issue=12, scene="S1", cpu="u7", gpu="5060",
         dur=944.5, total=84.5, grade="良",
         parts=dict(performance=98.9, smoothness=68.0, thermal=88.8, stability=4.1, efficiency=56.6, noise=49.3),
         m=dict(fpsAvg=162.8, ratio1=0.635, worst=31.1, cv=0.5595, fpw=1.13, fan=5133,
                ch=11.0, gh=7.8, stut=3.57, lat=158.4, cmr=0.715, cu=21.7, gu=83.0, vu=89.6,
                cm=62.3, vt=70.0, mt=54.3, dt=43.9),
         ev=dict(stutterRuns=6, dipRuns=2, throttlePct=0, powerWall=True, powerWallDropPct=39.5, eventCount=9),
         flavor="coder", submittedAt="2026-09-11T09:33:13Z",
         hw=dict(ram="31.4 GB · DDR5-7200 MT/s ×2", ramModel="SK Hynix · 16 GB · DDR5-7200 MT/s ×2",
                 disk="YMTC YMSS2ED08D25MC · 954 GB", display="2560 x 1600 · 240 Hz",
                 battery="外接电源 · 100%", os="Windows 11 专业版 24H2 · Build 26100.3624"),
         rec="sensors-20260906-210207-882.jsonl.gz", recBytes=33341,
         recSha="fea84fc8f7bfa431bd65e7ff28b92711b8ce2e5e199d2c3d1fd37f4f33291b15"),

    dict(owner="一只夜猫", author="nightcat", issue=18, scene="S1", cpu="u7", gpu="5060",
         dur=1823.0, total=88.6, grade="优",
         parts=dict(performance=99.4, smoothness=81.5, thermal=87.2, stability=72.4, efficiency=63.1, noise=51.0),
         m=dict(fpsAvg=171.2, ratio1=0.78, worst=64.2, cv=0.2140, fpw=1.38, fan=5010,
                ch=12.4, gh=8.6, stut=0.92, lat=96.3, cmr=0.884, cu=28.4, gu=88.1, vu=91.2,
                cm=66.0, vt=68.0, mt=52.8, dt=42.0),
         ev=dict(stutterRuns=1, dipRuns=0, throttlePct=0, powerWall=False, powerWallDropPct=None, eventCount=1),
         flavor="cat", submittedAt="2026-09-11T12:05:41Z",
         hw=dict(ram="31.4 GB · DDR5-7200 MT/s ×2", ramModel="SK Hynix · 16 GB · DDR5-7200 MT/s ×2",
                 disk="Samsung MZVL21T0HCLR · 953 GB", display="2560 x 1600 · 240 Hz",
                 battery="外接电源 · 100%", os="Windows 11 家庭版 24H2 · Build 26100.3624"),
         rec="sensors-20260910-223344-118.jsonl.gz", recBytes=61208,
         recSha="3c1a9f0e77b2d4a15e8c09f6d1b7a243e5f8c6d09b4a7e13f2c8d5b6a91e0f47"),

    dict(owner="老张的笔电", author="laozhang-2019", issue=21, scene="S1", cpu="u9", gpu="5070",
         dur=2104.0, total=92.1, grade="优",
         parts=dict(performance=100.0, smoothness=86.7, thermal=90.2, stability=78.9, efficiency=59.4, noise=44.8),
         m=dict(fpsAvg=198.6, ratio1=0.821, worst=88.4, cv=0.1680, fpw=1.31, fan=5620,
                ch=9.6, gh=6.4, stut=0.61, lat=78.9, cmr=0.902, cu=26.1, gu=92.4, vu=93.8,
                cm=64.0, vt=74.0, mt=57.1, dt=45.2),
         ev=dict(stutterRuns=0, dipRuns=0, throttlePct=0, powerWall=False, powerWallDropPct=None, eventCount=0),
         flavor="praise", submittedAt="2026-09-11T13:47:02Z",
         hw=dict(ram="63.2 GB · DDR5-6400 MT/s ×2", ramModel="Micron · 32 GB · DDR5-6400 MT/s ×2",
                 disk="WD PC SN810 SDCQNRY-1T00 · 954 GB", display="3200 x 2000 · 165 Hz",
                 battery="外接电源 · 100%", os="Windows 11 专业版 24H2 · Build 26100.3624"),
         rec="sensors-20260911-091502-004.jsonl.gz", recBytes=70442,
         recSha="9d4b2c7f1a8e5306cb92f7e04a1d3869b5ce07f2a4d81639e7b0c53a82df1461"),

    dict(owner="咕咕咕咕", author="octocat", issue=24, scene="S2", cpu="u7", gpu="5060",
         dur=1265.5, total=79.3, grade="良",
         parts=dict(performance=94.2, smoothness=61.8, thermal=76.4, stability=22.7, efficiency=52.0, noise=41.6),
         m=dict(fpsAvg=138.4, ratio1=0.598, worst=22.6, cv=0.6320, fpw=1.02, fan=5702,
                ch=6.2, gh=3.1, stut=5.84, lat=214.6, cmr=0.641, cu=48.2, gu=94.7, vu=95.1,
                cm=74.8, vt=79.0, mt=63.5, dt=51.8),
         ev=dict(stutterRuns=11, dipRuns=4, throttlePct=12.4, powerWall=True, powerWallDropPct=22.1, eventCount=17),
         flavor="savage2", submittedAt="2026-09-11T14:22:19Z",
         hw=dict(ram="31.4 GB · DDR5-7200 MT/s ×2", ramModel="SK Hynix · 16 GB · DDR5-7200 MT/s ×2",
                 disk="YMTC YMSS2ED08D25MC · 954 GB", display="2560 x 1600 · 240 Hz",
                 battery="外接电源 · 100%", os="Windows 11 专业版 24H2 · Build 26100.3624"),
         rec="sensors-20260911-140233-877.jsonl.gz", recBytes=42119,
         recSha="b7e02a4c6f19d835ae2c07f1b3d9e6485a1f7c20d8b6349e27f5a0c1d3e6b8a4"),

    dict(owner="Kira", author="kira-dev", issue=27, scene="S1", cpu="r7", gpu="4060",
         dur=1502.0, total=76.8, grade="良",
         parts=dict(performance=91.3, smoothness=63.2, thermal=79.1, stability=48.0, efficiency=68.4, noise=57.2),
         m=dict(fpsAvg=124.6, ratio1=0.688, worst=41.3, cv=0.3540, fpw=1.86, fan=4380,
                ch=14.2, gh=9.8, stut=2.14, lat=132.7, cmr=0.792, cu=31.6, gu=86.3, vu=81.4,
                cm=58.2, vt=64.0, mt=49.6, dt=40.1),
         ev=dict(stutterRuns=3, dipRuns=1, throttlePct=0, powerWall=False, powerWallDropPct=None, eventCount=4),
         flavor="butler", submittedAt="2026-09-11T15:10:55Z",
         hw=dict(ram="16.0 GB · LPDDR5X-7500 MT/s ×2", ramModel="Samsung · 8 GB · LPDDR5X-7500 MT/s ×2",
                 disk="SK Hynix HFS001TEJ9X101N · 954 GB", display="2560 x 1600 · 120 Hz",
                 battery="外接电源 · 98%", os="Windows 11 家庭版 24H2 · Build 26100.3624"),
         rec="sensors-20260911-101511-203.jsonl.gz", recBytes=48770,
         recSha="1f6c8d0b3a7e5924cf81d604b2e7a35904c8e1f7b3d6259a84e0c7b1f4d26a93"),

    dict(owner="散热垫信徒", author="coolfan-pro", issue=31, scene="S2", cpu="u9", gpu="5070",
         dur=2410.0, total=89.4, grade="优",
         parts=dict(performance=97.8, smoothness=79.4, thermal=92.6, stability=64.1, efficiency=57.8, noise=38.2),
         m=dict(fpsAvg=186.4, ratio1=0.762, worst=58.6, cv=0.2260, fpw=1.24, fan=5880,
                ch=8.8, gh=5.2, stut=1.34, lat=104.2, cmr=0.876, cu=42.6, gu=95.8, vu=96.2,
                cm=78.4, vt=76.0, mt=59.8, dt=47.4),
         ev=dict(stutterRuns=2, dipRuns=1, throttlePct=4.2, powerWall=True, powerWallDropPct=11.8, eventCount=5),
         flavor="doctor", submittedAt="2026-09-11T16:02:33Z",
         hw=dict(ram="63.2 GB · DDR5-6400 MT/s ×2", ramModel="Micron · 32 GB · DDR5-6400 MT/s ×2",
                 disk="WD PC SN810 SDCQNRY-1T00 · 954 GB", display="3200 x 2000 · 165 Hz",
                 battery="外接电源 · 100%", os="Windows 11 专业版 24H2 · Build 26100.3624"),
         rec="sensors-20260911-120258-331.jsonl.gz", recBytes=80720,
         recSha="6e2b9c4a1d7f8350be94c2f6a8d1735e0f8b64ca27d5913e4826fb0d7a3c95e1"),

    dict(owner="猫娘粉丝团", author="nyaa-nyaa", issue=36, scene="S1", cpu="r9", gpu="4070",
         dur=1640.0, total=90.2, grade="优",
         parts=dict(performance=96.4, smoothness=84.8, thermal=88.4, stability=74.2, efficiency=71.6, noise=62.4),
         m=dict(fpsAvg=176.8, ratio1=0.806, worst=72.4, cv=0.1880, fpw=1.94, fan=4620,
                ch=13.6, gh=10.2, stut=0.78, lat=88.6, cmr=0.914, cu=24.8, gu=89.6, vu=88.2,
                cm=61.4, vt=66.0, mt=50.2, dt=41.6),
         ev=dict(stutterRuns=0, dipRuns=0, throttlePct=0, powerWall=False, powerWallDropPct=None, eventCount=0),
         flavor="cat", submittedAt="2026-09-11T16:55:12Z",
         hw=dict(ram="31.4 GB · DDR5-5600 MT/s ×2", ramModel="Samsung · 16 GB · DDR5-5600 MT/s ×2",
                 disk="SK Hynix HFS001TEJ9X101N · 954 GB", display="2560 x 1600 · 240 Hz",
                 battery="外接电源 · 100%", os="Windows 11 家庭版 24H2 · Build 26100.3624"),
         rec="sensors-20260911-142031-997.jsonl.gz", recBytes=53244,
         recSha="2d7e4b9f0a6c1853ed92b7f40c1a8635e0db97f2c4a58361f7e9b02d6c4185a3"),

    dict(owner="隔壁老王", author="wanglao", issue=38, scene="S1", cpu="i7", gpu="4050",
         dur=1080.0, total=61.5, grade="中",
         parts=dict(performance=74.6, smoothness=52.4, thermal=68.2, stability=24.8, efficiency=61.2, noise=48.6),
         m=dict(fpsAvg=98.4, ratio1=0.542, worst=18.4, cv=0.7240, fpw=1.12, fan=5210,
                ch=9.4, gh=6.8, stut=7.42, lat=248.2, cmr=0.586, cu=38.4, gu=81.2, vu=76.8,
                cm=68.4, vt=72.0, mt=56.4, dt=44.2),
         ev=dict(stutterRuns=14, dipRuns=6, throttlePct=8.6, powerWall=True, powerWallDropPct=31.4, eventCount=21),
         flavor="savage", submittedAt="2026-09-11T17:12:40Z",
         hw=dict(ram="16.0 GB · DDR5-4800 MT/s ×2", ramModel="Kingston · 8 GB · DDR5-4800 MT/s ×2",
                 disk="KIOXIA KXG80ZNV512G · 477 GB", display="2560 x 1600 · 165 Hz",
                 battery="外接电源 · 96%", os="Windows 11 家庭版 23H2 · Build 22631.4890"),
         rec="sensors-20260911-152230-441.jsonl.gz", recBytes=34080,
         recSha="5b9c1e7a3d0f8264be75c1a9d6f2308e4a1b9c7d0e5f3182a6b4d09c7e2f5a83"),

    dict(owner="ThinkBook 全家桶", author="tb-fan", issue=40, scene="S2", cpu="u7", gpu="5060",
         dur=1990.0, total=82.4, grade="良",
         parts=dict(performance=95.8, smoothness=68.4, thermal=82.6, stability=41.2, efficiency=54.8, noise=45.2),
         m=dict(fpsAvg=152.6, ratio1=0.674, worst=38.2, cv=0.4280, fpw=1.08, fan=5460,
                ch=8.2, gh=5.6, stut=3.42, lat=168.4, cmr=0.724, cu=44.8, gu=93.2, vu=92.6,
                cm=72.6, vt=77.0, mt=61.2, dt=49.4),
         ev=dict(stutterRuns=7, dipRuns=2, throttlePct=6.8, powerWall=True, powerWallDropPct=18.6, eventCount=10),
         flavor="coder", submittedAt="2026-09-11T17:40:15Z",
         hw=dict(ram="31.4 GB · DDR5-7200 MT/s ×2", ramModel="SK Hynix · 16 GB · DDR5-7200 MT/s ×2",
                 disk="YMTC YMSS2ED08D25MC · 954 GB", display="2560 x 1600 · 240 Hz",
                 battery="外接电源 · 100%", os="Windows 11 专业版 24H2 · Build 26100.3624"),
         rec="sensors-20260911-161022-338.jsonl.gz", recBytes=66110,
         recSha="7a3d5f9b1c8e0427df96b3c05e1a2748c6db93f0a2e51749b8c0d6a3f2e9b517",
         range_idx=1, range_name="最近 7 天"),

    dict(owner="手残党", author="butter-fingers", issue=44, scene="S1", cpu="u5", gpu="arc",
         dur=990.0, total=56.8, grade="差",
         parts=dict(performance=48.2, smoothness=44.6, thermal=78.4, stability=32.4, efficiency=84.2, noise=76.8),
         m=dict(fpsAvg=42.6, ratio1=0.486, worst=14.2, cv=0.8420, fpw=3.12, fan=3120,
                ch=17.4, gh=14.8, stut=9.64, lat=286.4, cmr=0.742, cu=22.4, gu=64.8, vu=52.4,
                cm=52.8, vt=58.0, mt=44.2, dt=38.4),
         ev=dict(stutterRuns=19, dipRuns=8, throttlePct=0, powerWall=False, powerWallDropPct=None, eventCount=27),
         flavor="snarky", submittedAt="2026-09-11T18:05:36Z",
         hw=dict(ram="16.0 GB · LPDDR5X-8533 MT/s ×2", ramModel="Micron · 8 GB · LPDDR5X-8533 MT/s ×2",
                 disk="Samsung MZVL8512HELU-00BMV · 477 GB", display="2880 x 1800 · 120 Hz",
                 battery="外接电源 · 100%", os="Windows 11 家庭版 24H2 · Build 26100.3624"),
         rec="sensors-20260911-174502-115.jsonl.gz", recBytes=31204,
         recSha="3f8a1c6d0e5b9274ac81f3e06b2d9754e1ca08f6b3d2479108e5c2a7f4b1d639"),

    dict(owner="一叶知秋", author="yiyeshu", issue=46, scene="S1", cpu="r7", gpu="4060",
         dur=1408.0, total=77.9, grade="良",
         parts=dict(performance=90.6, smoothness=67.2, thermal=80.4, stability=52.6, efficiency=70.2, noise=58.4),
         m=dict(fpsAvg=128.2, ratio1=0.702, worst=44.6, cv=0.3240, fpw=1.92, fan=4260,
                ch=14.8, gh=10.4, stut=1.86, lat=124.8, cmr=0.812, cu=30.2, gu=87.4, vu=82.6,
                cm=57.6, vt=63.0, mt=48.8, dt=39.6),
         ev=dict(stutterRuns=2, dipRuns=1, throttlePct=0, powerWall=False, powerWallDropPct=None, eventCount=3),
         flavor="snarky2", submittedAt="2026-09-11T18:20:04Z",
         hw=dict(ram="16.0 GB · LPDDR5X-7500 MT/s ×2", ramModel="Samsung · 8 GB · LPDDR5X-7500 MT/s ×2",
                 disk="SK Hynix HFS001TEJ9X101N · 954 GB", display="2560 x 1600 · 120 Hz",
                 battery="外接电源 · 99%", os="Windows 11 家庭版 24H2 · Build 26100.3624"),
         rec="sensors-20260911-181530-720.jsonl.gz", recBytes=45180,
         recSha="9e1d4a7b2c6f0358bd92e4a7c1f60835a4db97c2e5f01836a7c9b3d0e6f2a481"),
]

REPO = "https://github.com/2006sila/tbt-leaderboard"


def r3(x):
    return None if x is None else round(x, 3)


def r2(x):
    return None if x is None else round(x, 2)


def r1(x):
    return None if x is None else round(x, 1)


def build_card(row):
    cpu_name, cores, threads = CPU[row["cpu"]]
    gpu_name = GPU[row["gpu"]]
    m, ev, p = row["m"], row["ev"], row["parts"]
    dur = row["dur"]
    samples = int(round(dur / 1.27))
    fps_avg = m["fpsAvg"]
    fps_1low = round(fps_avg * m["ratio1"], 1)
    rng_i = row.get("range_idx", 0)
    hw = dict(row["hw"])
    hw.pop("gpu", None)

    return {
        "format": "tbts-score",
        "version": 1,
        "generatedAt": row["submittedAt"].replace("Z", "+08:00"),
        "owner": row["owner"],
        "generator": {
            "app": "TBTSensorDashboard",
            "version": "2.0.0",
            "platform": "win-x64",
            "sampleIntervalSec": 1,
        },
        "score": {
            "total": row["total"],
            "grade": row["grade"],
            "parts": {
                "performance": r1(p["performance"]),
                "smoothness": r1(p["smoothness"]),
                "thermal": r1(p["thermal"]),
                "stability": r1(p["stability"]),
                "efficiency": r1(p["efficiency"]),
                "noise": r1(p["noise"]),
            },
        },
        "metrics": {
            "fpsAvg": r1(fps_avg),
            "fps1LowAvg": r1(fps_1low),
            "fpsWorst1Pct": r1(m["worst"]),
            "frametimeP99Ms": r2(1000.0 / m["worst"] if m["worst"] else None),
            "stutterRatio": r3(m["cv"] * 1.13),
            "stutterPct": r2(m["stut"]),
            "frametimeCv": round(m["cv"], 4),
            "fpsPerWatt": r2(m["fpw"]),
            "fanPeakRpm": int(m["fan"]),
            "cpuHeadroomC": r1(m["ch"]),
            "gpuHeadroomC": r1(m["gh"]),
            "throttlePct": r2(ev["throttlePct"]),
            "below60Pct": r2(min(m["stut"] * 0.82, 99.0)),
            "below30Pct": r2(m["stut"] * 0.118),
            "below25Pct": r2(m["stut"] * 0.045),
            "latencyP99Ms": r1(m["lat"]),
            "cpuMhzRatio": round(m["cmr"], 3),
            "cpuUtilAvgPct": r1(m["cu"]),
            "gpuUtilAvgPct": r1(m["gu"]),
            "vramUtilAvgPct": r1(m["vu"]),
            "committedUtilAvgPct": r1(m["cm"]),
            "vramTempMaxC": r1(m["vt"]),
            "memSlotTempMaxC": r1(m["mt"]),
            "diskTempMaxC": r1(m["dt"]),
        },
        "events": {
            "stutterRuns": ev["stutterRuns"],
            "dipRuns": ev["dipRuns"],
            "throttlePct": r2(ev["throttlePct"]),
            "powerWall": ev["powerWall"],
            "powerWallDropPct": r1(ev["powerWallDropPct"]),
            "eventCount": ev["eventCount"],
        },
        "hardware": {
            "cpu": cpu_name,
            "cpuCores": cores,
            "cpuThreads": threads,
            "gpu": gpu_name,
            "board": "LENOVO",
            "os": hw["os"],
            "ram": hw["ram"],
            "ramModel": hw["ramModel"],
            "disk": hw["disk"],
            "display": hw["display"],
            "battery": hw["battery"],
        },
        "view": {
            "range": row.get("range_name", SCENE_RANGE[row["scene"]]),
            "rangeIndex": rng_i,
            "durationSec": r1(dur),
            "sampleCount": samples,
        },
        "recording": {
            "fileName": row["rec"],
            "bytes": row["recBytes"],
            "sha256": row["recSha"],
        },
        "confidence": {
            "hasFps": True,
            "insufficient": False,
            "sampling": "≈1 Hz",
            "note": "记录约 1 秒/次采样：帧时间类指标（最差1% / P99 / CV / 卡顿占比）为秒级近似，非逐帧统计；逐帧口径请用 CapFrameX / PresentMon。时长与采样数见 view 块。",
        },
        "flavor": {
            "persona": FLAVOR[row["flavor"]]["persona"],
            "face": FLAVOR[row["flavor"]]["face"],
            "text": FLAVOR[row["flavor"]]["text"],
            "feats": list(FLAVOR[row["flavor"]]["feats"]),
        },
        "integrity": {
            "algorithm": "sha256",
            "canonical": "card with integrity=null | no indent | utf-8 | fixed key order (v1)",
            "payloadSha256": "",
        },
    }


def norm(s):
    """站点侧归一化：去商标符 + 压空白 + 小写 + 去尾部 CPU 主频。本脚本先算好键，
    与 web/app.js 里的 normKey() 保持一致。"""
    if not s:
        return ""
    import re
    s = s.replace("(R)", "").replace("(TM)", "").replace("(r)", "").replace("(tm)", "")
    s = s.replace("®", "").replace("™", "")
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = re.sub(r"\s*cpu\s*@\s*[\d.]+ghz$", "", s)
    return s


def main():
    entries = []
    for row in ROWS:
        card = build_card(row)
        entries.append({
            "issue": row["issue"],
            "issueUrl": f"{REPO}/issues/{row['issue']}",
            "author": row["author"],
            "owner": row["owner"],
            "scene": row["scene"],
            "submittedAt": row["submittedAt"],
            "durSec": card["view"]["durationSec"],
            "sampleCount": card["view"]["sampleCount"],
            "recordingSha256": card["recording"]["sha256"],
            "cpuKey": norm(card["hardware"]["cpu"]),
            "gpuKey": norm(card["hardware"]["gpu"]),
            "card": card,
        })

    data = {
        "version": 1,
        "demo": True,
        "generatedAt": "2026-09-11T18:40:00+08:00",
        "entries": entries,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    size = os.path.getsize(OUT)
    print(f"写入 {os.path.abspath(OUT)}")
    print(f"  {len(entries)} 条 · {size/1024:.1f} KB")
    pools = {}
    for e in entries:
        pools.setdefault((e["cpuKey"], e["gpuKey"]), []).append(e["owner"])
    print(f"  同配置池 {len(pools)} 个：")
    for (c, g), owners in sorted(pools.items(), key=lambda kv: -len(kv[1])):
        print(f"    {len(owners)} 人 · {c} | {g}")


if __name__ == "__main__":
    main()
