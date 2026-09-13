/* ==========================================================================
   TBTS 传感器评分榜 — 前端逻辑
   纯静态：只读 web/data/board.json，无后端、无外部依赖。
   榜单 = board.json 的 entries（每条是一张完整的 tbts-score 成绩卡 + 派生索引）
   ========================================================================== */

'use strict';

/* --------------------------------- 常量与配置 -------------------------------- */

// 计分项（进总分）与参考项（只做能力剖面）—— 与桌面端 ScoreExport 语义一致
const PARTS_SCORED = ['performance', 'smoothness', 'thermal'];
const PART_LABEL = {
  performance: '性能', smoothness: '流畅', thermal: '散热',
  stability: '稳定', efficiency: '能效', noise: '静音',
};

// 场景标签 —— 运行时从 data/policy.json 载入，下面的内置值只是 fetch 失败时的兜底
let SCENE_LABEL = { S1: '游戏稳态', S2: '压力测试' };

// 收录门槛 —— 单一出处是 data/policy.json（机器人 verify_submission.py 读同一份）。
// 网页只负责把数字显示出来，判断门槛是机器人的事，两边不会漂移。
let POLICY = { minDurationSec: 600, maxSampleGapSec: 5 };

const state = {
  all: [],            // 全部 entries
  view: [],           // 当前筛选结果
  open: new Set(),    // 展开中的 issue 号
  cpuName: new Map(), // cpuKey -> 显示短名
  gpuName: new Map(),
};

const $ = (id) => document.getElementById(id);

/* --------------------------------- 工具函数 -------------------------------- */

/** 站点侧机型归一化：去商标符 + 压空白 + 小写 + 去尾部 CPU 主频。
 *  生成端 gen_demo_data.py 的 norm() 必须与此保持一致。 */
function normKey(s) {
  if (!s) return '';
  return String(s)
    .replace(/\((?:R|TM)\)/gi, '')
    .replace(/[®™]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
    .replace(/\s*cpu\s*@\s*[\d.]+ghz$/, '');
}

/** 表格里显示用的短名（全名太长会撑破列宽） */
const shortCpu = (s) => (s || '').replace(/^Intel Core /, '').replace(/^Intel /, '').replace(/^AMD /, '');
const shortGpu = (s) => (s || '').replace(/^NVIDIA GeForce /, '').replace(/^NVIDIA /, '');

const gcls = (g) => ({ '优': 'gs', '良': 'ga', '中': 'gb', '差': 'gd' }[g] || 'gother');

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const num = (v, digits = 1, suffix = '') =>
  (v === null || v === undefined || Number.isNaN(v)) ? '—' : Number(v).toFixed(digits) + suffix;

const int = (v, suffix = '') =>
  (v === null || v === undefined || Number.isNaN(v)) ? '—' : Math.round(Number(v)) + suffix;

/** 时长 → "15.7 分"（表格窄，用分钟；精确秒数放 tooltip） */
const fmtDur = (sec) => (sec || 0) / 60 >= 100 ? Math.round(sec / 60) + ' 分' : (sec / 60).toFixed(1) + ' 分';

function fmtAbs(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso || '';
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

function fmtRel(iso) {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '—';
  const m = (Date.now() - t) / 60000;
  if (m < 0) return '刚刚';
  if (m < 1) return '刚刚';
  if (m < 60) return Math.floor(m) + ' 分钟前';
  const h = m / 60;
  if (h < 24) return Math.floor(h) + ' 小时前';
  const d = h / 24;
  if (d < 30) return Math.floor(d) + ' 天前';
  return fmtAbs(iso).slice(0, 10);
}

/* --------------------------------- 数据加载 -------------------------------- */

/** 门槛与场景标签来自 data/policy.json —— 与机器人读的是同一个文件。
 *  改门槛只改那一个文件，网页文案跟着变，不会出现三处各写一份的漂移。 */
async function loadPolicy() {
  try {
    const res = await fetch('data/policy.json', { cache: 'no-store' });
    if (res.ok) {
      const p = await res.json();
      if (typeof p.minDurationSec === 'number') POLICY.minDurationSec = p.minDurationSec;
      if (typeof p.maxSampleGapSec === 'number') POLICY.maxSampleGapSec = p.maxSampleGapSec;
      if (p.sceneLabels) SCENE_LABEL = p.sceneLabels;
    }
  } catch (_) { /* 读不到就用内置兜底值 */ }
  applyPolicyText();
}

const fmtMin = (sec) => {
  const m = sec / 60;
  return (Number.isInteger(m) ? m : m.toFixed(1)) + ' 分钟';
};

function applyPolicyText() {
  const set = (id, tx) => { const el = $(id); if (el) el.textContent = tx; };
  set('chipDur', `时长 ≥ ${fmtMin(POLICY.minDurationSec)}`);
  set('ruleDur', `时长 ≥ ${POLICY.minDurationSec} 秒（${fmtMin(POLICY.minDurationSec)}）`);
  set('ruleGap', `实际采样间隔 ≤ ${POLICY.maxSampleGapSec} 秒`);
}

let booted = false;

async function boot() {
  if (booted) return;   // 防重入：DOMContentLoaded 若被派发多次，避免事件重复绑定
  booted = true;

  await loadPolicy();

  let data;
  try {
    const res = await fetch('data/board.json', { cache: 'no-store' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    data = await res.json();
  } catch (err) {
    $('tbody').innerHTML = `<tr><td colspan="10" class="empty">
      读不到 <code>data/board.json</code>。<br>
      本地预览请用 <code>python -m http.server</code> 起一个静态服务再打开，直接双击 html 会被浏览器的跨域策略拦住。
      </td></tr>`;
    console.error(err);
    return;
  }

  state.all = (data.entries || []).map(prep);
  if (data.demo) $('demoFlag').hidden = false;

  const repo = data.repo || guessRepo(state.all);
  if (repo) {
    $('repoLink').href = repo + (repo.endsWith('/') ? '' : '/');
    $('repoLink2').href = repo;
  } else {
    $('repoLink').hidden = true;
    $('repoLink2').hidden = true;
  }
  document.title = (data.title || 'ThinkBook 传感器评分榜') + ' · TBTS';

  buildFilters();
  bindEvents();
  renderKpis();
  render();
}

function guessRepo(entries) {
  const u = (entries.find((e) => e.issueUrl) || {}).issueUrl || '';
  const m = u.match(/^(https?:\/\/[^/]+\/[^/]+\/[^/]+)/);
  return m ? m[1] : '';
}

/** 预计算每条记录要用的东西，避免渲染时反复算 */
function prep(e) {
  const card = e.card || {};
  const hw = card.hardware || {};
  const view = card.view || {};
  const conf = card.confidence || {};
  const cpuKey = e.cpuKey || normKey(hw.cpu);
  const gpuKey = e.gpuKey || normKey(hw.gpu);

  if (!state.cpuName.has(cpuKey) && hw.cpu) state.cpuName.set(cpuKey, shortCpu(hw.cpu));
  if (!state.gpuName.has(gpuKey) && hw.gpu) state.gpuName.set(gpuKey, shortGpu(hw.gpu));

  const durSec = view.durationSec ?? e.durSec ?? 0;
  const sampleCount = view.sampleCount ?? e.sampleCount ?? 0;
  const gap = sampleCount > 1 ? durSec / (sampleCount - 1) : 0;

  return {
    ...e, card, hw, view, conf, cpuKey, gpuKey, durSec, sampleCount, gap,
    total: (card.score || {}).total ?? 0,
    grade: (card.score || {}).grade || '—',
    parts: (card.score || {}).parts || {},
    metrics: card.metrics || {},
    events: card.events || {},
    flavor: card.flavor || {},
    recording: card.recording || {},
    fullTime: (view.rangeIndex ?? 0) === 0,
    suspicious: !!e.suspicious,
    sanityNotes: e.sanityNotes || [],
  };
}

/* --------------------------------- 筛选器 --------------------------------- */

function fillSelect(sel, pairs, keepValue) {
  const all = `<option value="">全部</option>`;
  sel.innerHTML = all + pairs.map(([v, t]) => `<option value="${esc(v)}">${esc(t)}</option>`).join('');
  sel.value = keepValue ?? '';
  sel.classList.toggle('on', !!sel.value);
}

function buildFilters() {
  const scenes = [...new Set(state.all.map((e) => e.scene).filter(Boolean))].sort();
  fillSelect($('fScene'), scenes.map((s) => [s, `${s} ${SCENE_LABEL[s] || ''}`.trim()]), $('fScene').value);

  const cpus = [...state.cpuName.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  fillSelect($('fCpu'), cpus, $('fCpu').value);

  const gpus = [...state.gpuName.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  fillSelect($('fGpu'), gpus, $('fGpu').value);

  const grades = [...new Set(state.all.map((e) => e.grade))];
  const order = ['优', '良', '中', '差'];
  grades.sort((a, b) => order.indexOf(a) - order.indexOf(b));
  fillSelect($('fGrade'), grades.map((g) => [g, g]), $('fGrade').value);
}

function bindEvents() {
  ['fScene', 'fCpu', 'fGpu', 'fGrade'].forEach((id) => {
    $(id).addEventListener('change', () => {
      $(id).classList.toggle('on', !!$(id).value);
      render();
    });
  });

  $('fReset').addEventListener('click', () => {
    ['fScene', 'fCpu', 'fGpu', 'fGrade'].forEach((id) => {
      $(id).value = '';
      $(id).classList.remove('on');
    });
    render();
  });

  $('tbody').addEventListener('click', (ev) => {
    const sameBtn = ev.target.closest('[data-same]');
    if (sameBtn) {
      const e = state.all.find((x) => String(x.issue) === sameBtn.dataset.same);
      if (e) {
        $('fCpu').value = e.cpuKey;
        $('fGpu').value = e.gpuKey;
        $('fCpu').classList.add('on');
        $('fGpu').classList.add('on');
        render();
        $('board').scrollIntoView?.({ block: 'start' });
      }
      return;
    }
    const row = ev.target.closest('tr.row');
    if (!row) return;
    const key = row.dataset.issue;
    state.open.has(key) ? state.open.delete(key) : state.open.add(key);
    render();
  });
}

function match(e) {
  return (!$('fScene').value || e.scene === $('fScene').value)
    && (!$('fCpu').value || e.cpuKey === $('fCpu').value)
    && (!$('fGpu').value || e.gpuKey === $('fGpu').value)
    && (!$('fGrade').value || e.grade === $('fGrade').value);
}

/* ---------------------------------- KPI ---------------------------------- */

function renderKpis() {
  const n = state.all.length;
  const people = new Set(state.all.map((e) => e.author || e.owner)).size;
  const pools = new Set(state.all.map((e) => e.cpuKey + '|' + e.gpuKey)).size;
  const avg = n ? state.all.reduce((s, e) => s + e.total, 0) / n : 0;

  $('kpis').innerHTML = [
    ['收录成绩', n, '条'],
    ['提交者', people, '人'],
    ['配置组合', pools, '组'],
    ['平均总分', avg.toFixed(1), ''],
  ].map(([k, v, u]) => `<div class="kpi"><div class="kpi-k">${k}</div>
      <div class="kpi-v">${v}${u ? `<small>${u}</small>` : ''}</div></div>`).join('');
}

/* --------------------------------- 榜单渲染 -------------------------------- */

function render() {
  const list = state.all.filter(match).sort((a, b) => b.total - a.total || a.submittedAt.localeCompare(b.submittedAt));
  state.view = list;

  const total = state.all.length;
  $('cnt').innerHTML = `显示 <b>${list.length}</b> / ${total} 条`;

  const cpuOn = $('fCpu').value, gpuOn = $('fGpu').value;
  const samePool = cpuOn && gpuOn;

  $('boardTitle').textContent = samePool ? '同配置榜' : '主榜';
  $('boardMeta').textContent = samePool
    ? `${state.cpuName.get(cpuOn)} + ${state.gpuName.get(gpuOn)}`
    : `全部成绩按总分降序 · 共 ${total} 条`;

  const note = $('poolNote');
  if (samePool) {
    const poolSize = state.all.filter((e) => e.cpuKey === cpuOn && e.gpuKey === gpuOn).length;
    note.hidden = false;
    note.classList.toggle('warn', poolSize <= 1);
    note.innerHTML = poolSize <= 1
      ? `同配置视图：<b>${esc(state.cpuName.get(cpuOn))} + ${esc(state.gpuName.get(gpuOn))}</b> —— 该组合目前只有 <b>1</b> 条成绩，名次没有比较意义，等更多人提交后才有参考价值。`
      : `同配置视图：<b>${esc(state.cpuName.get(cpuOn))} + ${esc(state.gpuName.get(gpuOn))}</b> —— 该组合共 <b>${poolSize}</b> 条成绩，下面只在池内排名。`;
  } else if (cpuOn || gpuOn) {
    note.hidden = false;
    note.classList.remove('warn');
    note.innerHTML = `已按单个维度筛选。想只在同一台机器的配置之间比较，把 <b>CPU 和 GPU 同时选中</b>（或点任意一行里的「只看同配置」）即可。`;
  } else {
    note.hidden = true;
  }

  $('empty').hidden = list.length > 0;
  $('tbody').innerHTML = list.map((e, i) => rowHtml(e, i + 1)).join('');
}

function rowHtml(e, rank) {
  const open = state.open.has(String(e.issue));
  const top = rank <= 3 ? ` top${rank}` : '';
  const badges = [
    !e.fullTime ? `<span class="badge part" title="导出时用的不是「全部时间」区间">非全时段</span>` : '',
    e.suspicious ? `<span class="badge flag" title="机器人检测到数值不符合真实记录的物理规律，建议人工复核">数值异常</span>` : '',
  ].join('');

  return `
  <tr class="row${top}${open ? ' open' : ''}" data-issue="${esc(String(e.issue))}">
    <td class="c-rank"><span class="rank${rank <= 3 ? ' r' + rank : ''}">${rank}</span></td>
    <td class="c-owner">
      <span class="owner-n">${esc(e.owner || e.author || '匿名')}</span>
      ${e.owner && e.author ? `<span class="owner-a">${esc(e.author)}</span>` : ''}
      ${badges}
    </td>
    <td class="c-total"><span class="total-v ${gcls(e.grade)}">${e.total.toFixed(1)}</span></td>
    <td class="c-grade"><span class="grade ${gcls(e.grade)}">${esc(e.grade)}</span></td>
    <td class="c-cpu"><span class="hw-n"><span class="hw-short" title="${esc(e.hw.cpu || '')}">${esc(shortCpu(e.hw.cpu))}</span></span></td>
    <td class="c-gpu"><span class="hw-n"><span class="hw-short" title="${esc(e.hw.gpu || '')}">${esc(shortGpu(e.hw.gpu))}</span></span></td>
    <td class="c-dur" title="${num(e.durSec, 1)} 秒 · ${int(e.sampleCount)} 个样本">${fmtDur(e.durSec)}</td>
    <td class="c-scene"><span class="scene-tag" title="${esc(SCENE_LABEL[e.scene] || '')}">${esc(e.scene || '—')}</span></td>
    <td class="c-time"><span class="t" title="${esc(fmtAbs(e.submittedAt))}">${fmtRel(e.submittedAt)}</span></td>
    <td class="c-x"><span class="chev">▾</span></td>
  </tr>
  ${open ? `<tr class="detail"><td colspan="10"><div class="detail-in">${detailHtml(e)}</div></td></tr>` : ''}`;
}

/* --------------------------------- 展开详情 -------------------------------- */

function detailHtml(e) {
  const m = e.metrics, ev = e.events, f = e.flavor, r = e.recording;

  return `
    ${e.suspicious ? `<div class="d-flag">
      <div class="dfg-h">机器人检测到数值异常</div>
      <ul class="dfg-l">${(e.sanityNotes.length ? e.sanityNotes : ['数值特征不符合真实记录']).map((t) => `<li>${esc(t)}</li>`).join('')}</ul>
      <div class="dfg-f">这条成绩已照常上榜，异常标记仅作提示 —— 榜单成绩均为自报，未经复算核验。</div>
    </div>` : ''}

    <div class="d-flavor">
      <div class="df-head">
        <span class="df-face">${esc(f.face || '💬')}</span>
        <span class="df-name">${esc(f.persona || '评价')}</span>
        <span class="df-sub">· 由桌面端按当时的人设生成，导出时一并写入成绩卡</span>
      </div>
      <div class="df-text">${esc(f.text || '（无）')}</div>
      ${(f.feats && f.feats.length)
        ? `<ul class="df-feats">${f.feats.map((t) => `<li>${esc(t)}</li>`).join('')}</ul>` : ''}
    </div>

    <div class="d-grid">
      <div class="d-card">
        <div class="dc-t">六维分 <em>前三项计分</em></div>
        ${PARTS_SCORED.concat(['stability', 'efficiency', 'noise']).map((k) => {
          const v = e.parts[k];
          const scored = PARTS_SCORED.includes(k);
          return `<div class="bar-row${v !== undefined && v < 50 ? ' low' : ''}">
            <div class="bar-k">${PART_LABEL[k]}${scored ? '' : '<i>参考</i>'}</div>
            <div class="bar-track"><div class="bar-fill" style="width:${Math.max(0, Math.min(100, v ?? 0))}%"></div></div>
            <div class="bar-v">${v === undefined || v === null ? '—' : v.toFixed(1)}</div>
          </div>`;
        }).join('')}
      </div>

      <div class="d-card">
        <div class="dc-t">性能与流畅</div>
        <div class="mlist">
          ${mi('平均帧率', num(m.fpsAvg, 1, ' fps'))}
          ${mi('1% Low 均值', num(m.fps1LowAvg, 1, ' fps'))}
          ${mi('最差 1%', num(m.fpsWorst1Pct, 1, ' fps'), m.fpsWorst1Pct < 30 ? 'warn' : '')}
          ${mi('帧时间 P99', num(m.frametimeP99Ms, 1, ' ms'), m.frametimeP99Ms > 25 ? 'warn' : '')}
          ${mi('帧时间波动 CV', num(m.frametimeCv, 3), m.frametimeCv > 0.4 ? 'warn' : m.frametimeCv < 0.2 ? 'ok' : '')}
          ${mi('卡顿占比', num(m.stutterPct, 2, ' %'), m.stutterPct > 3 ? 'warn' : m.stutterPct < 1 ? 'ok' : '')}
          ${mi('低于 60 帧', num(m.below60Pct, 2, ' %'))}
          ${mi('输入延迟 P99', num(m.latencyP99Ms, 0, ' ms'), m.latencyP99Ms > 200 ? 'warn' : '')}
        </div>
      </div>

      <div class="d-card">
        <div class="dc-t">功耗 · 散热 · 占用</div>
        <div class="mlist">
          ${mi('每瓦帧率', num(m.fpsPerWatt, 2, ' fps/W'), m.fpsPerWatt >= 2 ? 'ok' : '')}
          ${mi('风扇峰值', int(m.fanPeakRpm, ' rpm'))}
          ${mi('CPU 温度余量', num(m.cpuHeadroomC, 1, ' °C'), m.cpuHeadroomC < 5 ? 'warn' : m.cpuHeadroomC > 15 ? 'ok' : '')}
          ${mi('GPU 温度余量', num(m.gpuHeadroomC, 1, ' °C'), m.gpuHeadroomC < 5 ? 'warn' : m.gpuHeadroomC > 15 ? 'ok' : '')}
          ${mi('降频占比', num(m.throttlePct, 2, ' %'), m.throttlePct > 0 ? 'warn' : 'ok')}
          ${mi('CPU 频率比', num(m.cpuMhzRatio, 3))}
          ${mi('CPU 占用均值', num(m.cpuUtilAvgPct, 1, ' %'))}
          ${mi('GPU 占用均值', num(m.gpuUtilAvgPct, 1, ' %'))}
          ${mi('显存占用', num(m.vramUtilAvgPct, 1, ' %'))}
          ${mi('显存温度峰值', num(m.vramTempMaxC, 1, ' °C'))}
          ${mi('内存温度峰值', num(m.memSlotTempMaxC, 1, ' °C'))}
          ${mi('硬盘温度峰值', num(m.diskTempMaxC, 1, ' °C'))}
        </div>
      </div>

      <div class="d-card w2">
        <div class="dc-t">硬件与环境 <em>共 ${Object.keys(e.hw).length} 项</em></div>
        <div class="mlist">
          ${mi('处理器', esc(e.hw.cpu || '—'))}
          ${mi('核心 / 线程', `${e.hw.cpuCores ?? '—'} / ${e.hw.cpuThreads ?? '—'}`)}
          ${mi('显卡', esc(shortGpu(e.hw.gpu) || '—'))}
          ${mi('主板厂牌', esc(e.hw.board || '—'))}
          ${mi('内存', esc(e.hw.ram || '—'))}
          ${mi('内存条', esc(e.hw.ramModel || '—'))}
          ${mi('硬盘', esc(e.hw.disk || '—'))}
          ${mi('屏幕', esc(e.hw.display || '—'))}
          ${mi('电源', esc(e.hw.battery || '—'))}
          ${mi('系统', esc(e.hw.os || '—'))}
        </div>
      </div>

      <div class="d-card">
        <div class="dc-t">事件与溯源</div>
        <div class="ev-list">
          <div class="ev"><span>卡顿次数</span><b>${int(ev.stutterRuns)}</b></div>
          <div class="ev"><span>掉帧次数</span><b>${int(ev.dipRuns)}</b></div>
          <div class="ev"><span>功耗墙触发</span><b>${
            ev.powerWall ? `<span class="pill warn">是 · 掉 ${num(ev.powerWallDropPct, 1, '%')}</span>`
                         : '<span class="pill ok">未触发</span>'}</b></div>
          <div class="ev"><span>可信度</span><b>${
            e.conf.insufficient ? '<span class="pill bad">数据不足</span>'
              : e.conf.hasFps ? '<span class="pill ok">含 FPS 数据</span>'
                              : '<span class="pill mute">无 FPS</span>'}</b></div>
          <div class="ev"><span>实际采样间隔</span><b>${e.gap ? num(e.gap, 2, ' 秒') : '—'}</b></div>
        </div>
        <div class="src" style="margin-top:12px">
          <div class="src-row"><span>记录文件</span><code>${esc(r.fileName || '—')}</code></div>
          <div class="src-row"><span>文件大小</span><code>${r.bytes ? (r.bytes / 1024).toFixed(1) + ' KB' : '—'}</code></div>
          <div class="src-row"><span>记录校验</span><code title="${esc(r.sha256 || '')}">${esc((r.sha256 || '—').slice(0, 24))}…</code></div>
        </div>
      </div>
    </div>

    <div class="d-actions">
      <button class="btn tiny" type="button" data-same="${esc(String(e.issue))}">只看同配置</button>
      <span class="src-row" style="font-size:12px;color:var(--tx-3)">成绩卡 SHA-256 记录在案，重复提交同一份记录会被拦下</span>
      <span class="spacer"></span>
      <a class="link" href="${esc(e.issueUrl || '#')}" target="_blank" rel="noopener">
        查看提交的 issue #${esc(String(e.issue))} →
      </a>
    </div>`;
}

function mi(k, v, cls = '') {
  return `<div class="mitem"><span>${k}</span><b class="${cls}">${v}</b></div>`;
}

/* ---------------------------------- 启动 ---------------------------------- */

document.addEventListener('DOMContentLoaded', boot);
