/**
 * 前端渲染自检：用 jsdom 真跑一遍 app.js，验证
 *   1) 无 JS 运行时错误
 *   2) 榜单行数、KPI、筛选下拉渲染正确
 *   3) 行展开 / 「只看同配置」交互可用
 *   4) 门槛文案确实来自 data/policy.json（不是硬编码）
 *   5) 「不看异常数据」勾选能过滤掉带标记的成绩、并如实提示隐藏条数
 *
 * 用法: NODE_PATH=<workspace>/node_modules node render_check.js
 * 这是开发期工具，不随站点发布。
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const WEB = path.join(__dirname, '..', 'web');
const html = fs.readFileSync(path.join(WEB, 'index.html'), 'utf8');
const boardRaw = fs.readFileSync(path.join(WEB, 'data', 'board.json'), 'utf8');
const board = JSON.parse(boardRaw);
const policyRaw = fs.readFileSync(path.join(WEB, 'data', 'policy.json'), 'utf8');

// 给总分最高的一条注入异常标记，用来验证「数值异常」角标与详情提示块的渲染。
// 只在内存里改，不落盘 —— 演示数据本身保持干净。
const flaggedEntry = board.entries.slice()
  .sort((a, b) => b.card.score.total - a.card.score.total)[0];
flaggedEntry.suspicious = true;
flaggedEntry.sanityNotes = [
  '记录文件名含可疑字样 `modified`：`sensors-20260911-212915-824_modified_all.jsonl`',
  '帧率均值 / 1% Low / 最差 1% 三者完全相等（1000.0）——真实记录必然有梯度',
  '六项分项全部 ≥ 99.5——真实机器不可能项项满分',
];
const boardDataRaw = JSON.stringify(board);
const policy = JSON.parse(policyRaw);

const dom = new JSDOM(html, { url: 'http://localhost/', pretendToBeVisual: true, runScripts: 'outside-only' });
const w = dom.window;
const d = w.document;

const errors = [];
w.addEventListener('error', (e) => errors.push('window.onerror: ' + (e.message || e.error)));
// 按 URL 分发：app.js 会分别取 board.json 和 policy.json
w.fetch = async (url) => {
  const body = String(url).includes('policy.json') ? policyRaw : boardDataRaw;
  return { ok: true, status: 200, json: async () => JSON.parse(body) };
};

w.eval(fs.readFileSync(path.join(WEB, 'app.js'), 'utf8'));
// 注意：jsdom 解析完 HTML 会自行派发一次 DOMContentLoaded，
// 不要再手动 dispatch —— 否则 boot 会跑两次（app.js 已加防重入守卫兜底）。

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const rows = () => [...d.querySelectorAll('tr.row')];
const txt = (el) => (el ? el.textContent.trim().replace(/\s+/g, ' ') : '');

const results = [];
function check(name, ok, detail = '') {
  results.push({ name, ok, detail });
}

(async () => {
  await wait(300);

  // ---- 基本渲染 ----
  check('页面无 JS 运行时错误', errors.length === 0, errors.join(' | '));
  check(`榜单渲染 ${board.entries.length} 行`, rows().length === board.entries.length,
        `实际 ${rows().length}`);
  check('KPI 4 张磁贴', d.querySelectorAll('.kpi').length === 4, `实际 ${d.querySelectorAll('.kpi').length}`);
  check('演示角标已显示', !d.getElementById('demoFlag').hidden);

  // ---- 门槛文案来自 policy.json（不是写死在 HTML 里）----
  const mins = policy.minDurationSec / 60;
  const minTx = (Number.isInteger(mins) ? mins : mins.toFixed(1)) + ' 分钟';
  check('胶囊文案跟 policy 走',
        txt(d.getElementById('chipDur')).includes(minTx), txt(d.getElementById('chipDur')));
  check('收录条件·时长跟 policy 走',
        txt(d.getElementById('ruleDur')).includes(String(policy.minDurationSec))
        && txt(d.getElementById('ruleDur')).includes(minTx),
        txt(d.getElementById('ruleDur')));
  check('收录条件·采样间隔跟 policy 走',
        txt(d.getElementById('ruleGap')).includes(String(policy.maxSampleGapSec)),
        txt(d.getElementById('ruleGap')));

  // ---- 排序：总分降序 ----
  const totals = rows().map((r) => parseFloat(txt(r.querySelector('.total-v'))));
  const sorted = totals.every((v, i) => i === 0 || totals[i - 1] >= v);
  check('默认按总分降序', sorted, totals.join(', '));

  // ---- 数值异常角标 ----
  const flagBadge = rows()[0].querySelector('.badge.flag');
  check('异常条目标出「数值异常」角标', !!flagBadge && txt(flagBadge) === '数值异常',
        flagBadge ? txt(flagBadge) : '未找到角标');
  check('正常条目不带异常角标',
        rows().length < 2 || !rows()[1].querySelector('.badge.flag'));

  // ---- 筛选下拉 ----
  const opts = (id) => [...d.getElementById(id).options].map((o) => o.value).filter(Boolean);
  const expectScenes = new Set(board.entries.map((e) => e.scene)).size;
  check(`场景下拉有 ${expectScenes} 项`, opts('fScene').length === expectScenes, opts('fScene').join('/'));
  check('CPU 下拉 = 去重后的 CPU 数', opts('fCpu').length === new Set(board.entries.map((e) => e.cpuKey)).size,
        opts('fCpu').join(' / '));
  check('GPU 下拉 = 去重后的 GPU 数', opts('fGpu').length === new Set(board.entries.map((e) => e.gpuKey)).size,
        opts('fGpu').join(' / '));
  check('场景标签用的是 policy 里的中文名',
        d.getElementById('fScene').options[1].textContent.includes(policy.sceneLabels[d.getElementById('fScene').options[1].value]),
        d.getElementById('fScene').options[1].textContent);

  // ---- 筛选：按 CPU 过滤 ----
  const fCpu = d.getElementById('fCpu');
  const targetCpu = board.entries[0].cpuKey;
  fCpu.value = targetCpu;
  fCpu.dispatchEvent(new w.Event('change'));
  await wait(60);
  const expectCpu = board.entries.filter((e) => e.cpuKey === targetCpu).length;
  check(`按 CPU 筛选（${targetCpu}）剩 ${expectCpu} 行`, rows().length === expectCpu, `实际 ${rows().length}`);

  // ---- 同配置视图提示 ----
  const fGpu = d.getElementById('fGpu');
  fGpu.value = board.entries[0].gpuKey;
  fGpu.dispatchEvent(new w.Event('change'));
  await wait(60);
  const note = d.getElementById('poolNote');
  const expectPool = board.entries.filter((e) => e.cpuKey === targetCpu && e.gpuKey === fGpu.value).length;
  check('同配置视图提示出现', !note.hidden && note.textContent.includes(String(expectPool)),
        txt(note).slice(0, 90));
  check('标题切为「同配置榜」', txt(d.getElementById('boardTitle')) === '同配置榜',
        txt(d.getElementById('boardTitle')));
  check(`同配置筛选剩 ${expectPool} 行`, rows().length === expectPool, `实际 ${rows().length}`);

  // ---- 重置 ----
  d.getElementById('fReset').dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  await wait(60);
  check('重置后恢复全部', rows().length === board.entries.length, `实际 ${rows().length}`);

  // ---- 「不看异常数据」勾选 ----
  const fHide = d.getElementById('fHideFlag');
  check('「不看异常数据」默认未勾选', !!fHide && !fHide.checked);
  const flagTotal = board.entries.filter((e) => e.suspicious).length;
  fHide.checked = true;
  fHide.dispatchEvent(new w.Event('change'));
  await wait(60);
  check(`勾选后剩 ${board.entries.length - flagTotal} 行`,
        rows().length === board.entries.length - flagTotal, `实际 ${rows().length}`);
  check('勾选后不再出现「数值异常」角标', !d.querySelector('.badge.flag'));
  const flagMem = (() => { try { return w.localStorage.getItem('tbts-hide-flag'); } catch (_) { return '读不到'; } })();
  check('勾选状态写入本地记忆', flagMem === '1', `localStorage=${flagMem}`);
  check('计数提示写明隐藏条数',
        txt(d.getElementById('cnt')).includes(`已隐藏 ${flagTotal} 条`),
        txt(d.getElementById('cnt')));
  fHide.checked = false;
  fHide.dispatchEvent(new w.Event('change'));
  await wait(60);
  check('取消勾选后恢复全部', rows().length === board.entries.length, `实际 ${rows().length}`);

  // ---- 展开行 ----
  rows()[0].dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  await wait(60);
  const detail = d.querySelector('tr.detail');
  check('点击行后展开详情', !!detail);
  if (detail) {
    const dt = txt(detail);
    const card = board.entries.slice().sort((a, b) => b.card.score.total - a.card.score.total)[0].card;
    check('详情含趣味评价正文', dt.includes(card.flavor.text.slice(0, 18)), dt.slice(0, 120));
    check('详情含小字（feats）', detail.querySelectorAll('.df-feats li').length === card.flavor.feats.length,
          `${detail.querySelectorAll('.df-feats li').length} 条`);
    check('详情含六维分 6 条', detail.querySelectorAll('.bar-row').length === 6,
          `${detail.querySelectorAll('.bar-row').length} 条`);
    check('详情含「只看同配置」按钮', !!detail.querySelector('[data-same]'));
    check('详情含 issue 链接', !!detail.querySelector('a.link'));
    check('详情含异常提示块', !!detail.querySelector('.d-flag'));
    check('异常提示逐条列出命中项',
          detail.querySelectorAll('.dfg-l li').length === flaggedEntry.sanityNotes.length,
          `${detail.querySelectorAll('.dfg-l li').length} 条`);
  }

  // ---- 「只看同配置」按钮 ----
  const sameBtn = d.querySelector('[data-same]');
  if (sameBtn) {
    const issue = sameBtn.dataset.same;
    const src = board.entries.find((e) => String(e.issue) === issue);
    sameBtn.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
    await wait(60);
    const okCpu = d.getElementById('fCpu').value === src.cpuKey;
    const okGpu = d.getElementById('fGpu').value === src.gpuKey;
    const expect = board.entries.filter((e) => e.cpuKey === src.cpuKey && e.gpuKey === src.gpuKey).length;
    check('「只看同配置」填入筛选并过滤', okCpu && okGpu && rows().length === expect,
          `cpu=${okCpu} gpu=${okGpu} rows=${rows().length}/${expect}`);
  }

  // ---- 输出 ----
  console.log('\n=== 前端渲染自检 ===');
  let bad = 0;
  for (const r of results) {
    console.log(`${r.ok ? '  OK  ' : ' FAIL '} ${r.name}${r.detail ? `  → ${r.detail}` : ''}`);
    if (!r.ok) bad++;
  }
  console.log(`\n${results.length - bad} / ${results.length} 通过`);
  if (errors.length) console.log('运行时错误:', errors);
  process.exit(bad ? 1 : 0);
})();
