from __future__ import annotations

import argparse
import base64
import json
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from config import get_settings
from db import connect, init_db, list_events
from lite_poll import poll_homepage_once
from runtime_settings import load_runtime_settings, save_uploaded_mp3, update_runtime_settings


_DEFAULT_MP3 = os.path.abspath(os.path.join(os.path.dirname(__file__), "default_music.mp3"))
_POLL_META_LOCK = threading.Lock()
_POLL_META: Dict[str, Any] = {"last_poll_attempt_at": None}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mark_poll_attempt() -> None:
    with _POLL_META_LOCK:
        _POLL_META["last_poll_attempt_at"] = _now_iso()


def _get_poll_meta() -> Dict[str, Any]:
    with _POLL_META_LOCK:
        return dict(_POLL_META)


_HTML = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>DeepSeekV4 Spotter</title>
  <style>
    :root {
      --bg0: #04090e;
      --bg1: #0d1620;
      --ink: #e9f8ff;
      --muted: rgba(233,248,255,0.72);
      --line: rgba(168, 209, 234, 0.25);
      --panel: rgba(12, 28, 39, 0.75);
      --ok: #66f3a6;
      --warn: #ffd166;
      --err: #ff7c8b;
      --accent: #7cf6ff;
      --mono: "IBM Plex Mono", "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
      --sans: "Space Grotesk", "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      color: var(--ink);
      font-family: var(--sans);
      background:
        radial-gradient(1100px 700px at 0% -10%, rgba(124,246,255,0.15), transparent 55%),
        radial-gradient(900px 500px at 110% -20%, rgba(102,243,166,0.18), transparent 55%),
        linear-gradient(180deg, var(--bg0), var(--bg1));
      min-height: 100vh;
    }

    .wrap {
      max-width: 1100px;
      margin: 0 auto;
      padding: 20px 16px 50px;
    }

    .hero {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 14px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px;
      background: linear-gradient(160deg, rgba(13,32,44,0.88), rgba(8,18,26,0.86));
      box-shadow: 0 12px 28px rgba(0, 0, 0, 0.3);
    }

    .brand {
      display: flex;
      gap: 12px;
      align-items: center;
    }

    .logo {
      width: 54px;
      height: 54px;
      border: 1px solid rgba(124,246,255,0.45);
      border-radius: 14px;
      display: grid;
      place-items: center;
      background: linear-gradient(140deg, rgba(124,246,255,0.22), rgba(102,243,166,0.18));
      color: var(--ink);
      font-family: var(--mono);
      font-size: 13px;
      letter-spacing: 0.5px;
      font-weight: 700;
    }

    .title {
      margin: 0;
      font-size: 24px;
      letter-spacing: 0.2px;
    }

    .subtitle {
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 13px;
    }

    .actions {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: end;
    }

    button, .btn-link {
      border: 1px solid var(--line);
      border-radius: 11px;
      padding: 9px 12px;
      color: var(--ink);
      background: rgba(124,246,255,0.14);
      cursor: pointer;
      font-family: var(--sans);
      font-weight: 700;
      text-decoration: none;
      font-size: 13px;
    }

    button:hover, .btn-link:hover {
      background: rgba(124,246,255,0.23);
    }

    button:disabled { opacity: 0.6; cursor: not-allowed; }

    .icon-link {
      width: 40px;
      height: 40px;
      border: 1px solid var(--line);
      border-radius: 11px;
      display: grid;
      place-items: center;
      background: #ffffff;
      text-decoration: none;
      box-shadow: 0 0 0 1px rgba(0,0,0,0.02) inset;
    }

    .icon-link:hover {
      text-decoration: none;
      background: #f0f6fc;
    }

    .icon-link img {
      width: 22px;
      height: 22px;
      display: block;
    }

    .status {
      margin-top: 12px;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 9px 11px;
      font-family: var(--mono);
      font-size: 12px;
      color: var(--muted);
      background: rgba(255,255,255,0.03);
    }

    .monitor {
      margin-top: 12px;
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px;
      background: var(--panel);
      position: relative;
      overflow: hidden;
    }

    .monitor::before {
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      background: repeating-linear-gradient(
        to bottom,
        rgba(124,246,255,0.04) 0,
        rgba(124,246,255,0.04) 1px,
        transparent 1px,
        transparent 6px
      );
      opacity: 0.45;
    }

    .monitor h2 {
      margin: 0;
      font-size: 14px;
      font-family: var(--mono);
      letter-spacing: 0.8px;
      color: var(--accent);
      text-transform: uppercase;
    }

    .cards {
      margin-top: 12px;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      position: relative;
      z-index: 1;
    }

    .card {
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px;
      background: rgba(255,255,255,0.03);
      min-height: 128px;
    }

    .card h3 {
      margin: 0;
      font-size: 12px;
      color: var(--muted);
      font-family: var(--mono);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .card .main {
      margin-top: 10px;
      font-size: 22px;
      font-weight: 800;
      letter-spacing: 0.2px;
    }

    .flag {
      margin-top: 6px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 3px 8px;
      font-family: var(--mono);
      font-size: 11px;
    }

    .flag.ok { color: var(--ok); border-color: rgba(102,243,166,0.42); }
    .flag.warn { color: var(--warn); border-color: rgba(255,209,102,0.42); }
    .flag.err { color: var(--err); border-color: rgba(255,124,139,0.42); }

    .small {
      margin-top: 8px;
      font-size: 12px;
      color: var(--muted);
      line-height: 1.35;
      word-break: break-word;
    }

    .repos {
      margin-top: 8px;
      display: grid;
      gap: 5px;
      font-family: var(--mono);
      font-size: 11px;
      color: var(--muted);
    }

    .repo-row {
      display: flex;
      justify-content: space-between;
      gap: 8px;
    }

    .repo-row .ok { color: var(--ok); }
    .repo-row .idle { color: var(--muted); }

    .details {
      margin-top: 14px;
    }

    .details-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }

    .details-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }

    .panel {
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px;
      background: rgba(255,255,255,0.03);
    }

    .panel h4 {
      margin: 0;
      font-size: 13px;
    }

    .kv { margin-top: 8px; display: grid; gap: 5px; }
    .kv .row {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      font-size: 12px;
      border-bottom: 1px dashed rgba(233,248,255,0.12);
      padding-bottom: 4px;
    }
    .kv .row:last-child { border-bottom: none; }
    .k { color: var(--muted); font-family: var(--mono); }
    .v { text-align: right; word-break: break-word; }

    .set-box { margin-top: 10px; display: grid; gap: 8px; }
    .set-box label { font-size: 12px; color: var(--muted); }
    .set-box input[type="text"], .set-box input[type="url"], .set-box input[type="file"] {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 8px 10px;
      background: rgba(0,0,0,0.22);
      color: var(--ink);
      font-family: var(--mono);
      font-size: 12px;
    }

    .set-actions { display: flex; gap: 8px; flex-wrap: wrap; }

    .set-msg {
      margin-top: 6px;
      font-size: 12px;
      font-family: var(--mono);
      color: var(--muted);
      min-height: 16px;
      word-break: break-word;
    }

    .events { margin-top: 8px; display: grid; gap: 8px; max-height: 420px; overflow: auto; }
    .evt {
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 9px;
      background: rgba(255,255,255,0.02);
    }
    .evt-top { display: flex; justify-content: space-between; gap: 8px; }
    .evt-title { font-size: 13px; font-weight: 700; }
    .evt-badge {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 11px;
      font-family: var(--mono);
      color: var(--muted);
      white-space: nowrap;
    }
    .evt-meta {
      margin-top: 6px;
      font-size: 12px;
      color: var(--muted);
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      word-break: break-all;
    }

    a { color: #9fffcf; text-decoration: none; }
    a:hover { text-decoration: underline; }

    @media (max-width: 980px) {
      .hero { grid-template-columns: 1fr; }
      .actions { justify-content: start; }
      .cards { grid-template-columns: 1fr; }
      .details-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class=\"wrap\">
    <header class=\"hero\">
      <div class=\"brand\">
        <div class=\"logo\">DSV4</div>
        <div>
          <h1 class=\"title\">DeepSeekV4 Spotter</h1>
          <p id=\"subtitleText\" class=\"subtitle\">Watch website and repo activity to catch DeepSeek v4 clues as early as possible.</p>
        </div>
      </div>
      <div class=\"actions\">
        <button id=\"pollBtn\">Check Now</button>
        <button id=\"toggleBtn\">Open Settings</button>
        <button id=\"langBtn\">中文 / EN</button>
        <a
          class=\"icon-link\"
          href=\"https://github.com/binichallein/deepseekv4-spotter\"
          target=\"_blank\"
          rel=\"noreferrer\"
          title=\"GitHub\"
          aria-label=\"GitHub Repository\"
        >
          <img src=\"https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png\" alt=\"GitHub\" />
        </a>
      </div>
    </header>

    <div id=\"statusLine\" class=\"status\">loading...</div>
    <div id=\"pollAttemptLine\" class=\"status\">loading...</div>

    <section class=\"monitor\">
      <h2 id=\"monitorTitle\">Monitor Overview</h2>
      <div class=\"cards\">
        <article class=\"card\">
          <h3 id=\"officialTitle\">Official Site</h3>
          <div class=\"main\" id=\"officialModel\">n/a</div>
          <div class=\"flag\" id=\"officialFlag\">waiting</div>
          <div class=\"small\" id=\"officialNote\">Baseline v3.2, last check n/a</div>
        </article>

        <article class=\"card\">
          <h3 id=\"ghTitle\">Repo Activity</h3>
          <div class=\"main\" id=\"ghMain\">0</div>
          <div class=\"flag\" id=\"ghFlag\">waiting</div>
          <div class=\"repos\" id=\"repoRows\"></div>
        </article>

        <article class=\"card\">
          <h3 id=\"alertTitle\">Alert Status</h3>
          <div class=\"main\" id=\"alertMain\">idle</div>
          <div class=\"flag\" id=\"alertFlag\">no trigger</div>
          <div class=\"small\" id=\"alertNote\">When a new clue appears, notification and sound will be triggered.</div>
        </article>
      </div>
    </section>

    <section class=\"details\" id=\"details\" hidden>
      <div class=\"details-head\">
        <strong id=\"detailPanelTitle\">Settings & Records</strong>
        <div>
          <a id=\"apiConfigLink\" class=\"btn-link\" href=\"/api/config\" target=\"_blank\" rel=\"noreferrer\">Config Data</a>
          <a id=\"apiEventsLink\" class=\"btn-link\" href=\"/api/events\" target=\"_blank\" rel=\"noreferrer\">Event Data</a>
        </div>
      </div>

      <div class=\"details-grid\">
        <section class=\"panel\">
          <h4 id=\"runtimeConfigTitle\">Current Settings</h4>
          <div class=\"kv\" id=\"cfgRows\"></div>
        </section>

        <section class=\"panel\">
          <h4 id=\"pollSnapshotTitle\">Latest Check Result</h4>
          <div class=\"kv\" id=\"pollRows\"></div>
        </section>
      </div>

      <section class=\"panel\" style=\"margin-top:10px\">
        <h4 id=\"customSettingsTitle\">Notification & Sound</h4>
        <div class=\"set-box\">
          <label id=\"webhookLabel\">Notification URL (Feishu Webhook supported)</label>
          <input type=\"url\" id=\"webhookInput\" placeholder=\"https://www.feishu.cn/flow/api/trigger-webhook/...\" />
          <div class=\"set-actions\">
            <button id=\"saveWebhookBtn\">Save Notification URL</button>
            <button id=\"clearWebhookBtn\">Clear Notification URL</button>
          </div>

          <label id=\"uploadMp3Label\">Upload alert sound and use it</label>
          <input type=\"file\" id=\"audioFile\" accept=\".mp3,audio/mpeg\" />
          <div class=\"set-actions\">
            <button id=\"uploadAudioBtn\">Upload Sound</button>
            <button id=\"useDefaultAudioBtn\">Use Default Sound</button>
          </div>

          <label id=\"audioPathLabel\">Or enter a local MP3 path</label>
          <input type=\"text\" id=\"audioPathInput\" placeholder=\"/abs/path/to/your.mp3\" />
          <div class=\"set-actions\">
            <button id=\"setAudioPathBtn\">Use This Path</button>
          </div>

          <div class=\"set-msg\" id=\"settingsMsg\"></div>
        </div>
      </section>

      <section class=\"panel\" style=\"margin-top:10px\">
        <h4 id=\"eventStreamTitle\">Latest Clues</h4>
        <div class=\"events\" id=\"events\"></div>
      </section>
    </section>
  </div>

<script>
const state = {
  cfg: null,
  poll: null,
  events: [],
  lang: (localStorage.getItem('dsv4_lang') === 'en') ? 'en' : 'zh',
  polling: false,
};

const BASELINE_MODEL = 'v3.2';

const I18N = {
  zh: {
    pageTitle: 'DeepSeekV4 Spotter',
    subtitle: '盯住官网与仓库动态，第一时间发现 DeepSeek v4 线索。',
    runPoll: '立即检查',
    polling: '正在检查...',
    openPanel: '打开设置与记录',
    hidePanel: '收起设置与记录',
    monitorTitle: '监控总览',
    officialTitle: '官网状态',
    githubTitle: '仓库动态',
    alertTitle: '提醒状态',
    detailPanelTitle: '设置与记录',
    runtimeConfigTitle: '当前设置',
    pollSnapshotTitle: '本轮检查结果',
    customSettingsTitle: '通知与铃声',
    webhookLabel: '通知地址（可填写飞书 Webhook）',
    webhookPlaceholder: 'https://your-webhook-url',
    saveWebhook: '保存通知地址',
    clearWebhook: '清空通知地址',
    uploadMp3Label: '上传提醒铃声并启用',
    uploadAudio: '上传铃声',
    useDefaultAudio: '使用默认铃声',
    audioPathLabel: '或填写本机 MP3 路径',
    audioPathPlaceholder: '/abs/path/to/your.mp3',
    setAudioPath: '使用此路径',
    eventStreamTitle: '最新线索',
    apiConfig: '配置数据',
    apiEvents: '事件数据',
    loading: '加载中...',
    waiting: '等待中',
    idle: '空闲',
    noTrigger: '未触发',
    statusLine: '监控已启动 | 已记录 {events} 条线索 | 页面刷新 {time}',
    pollAttemptLine: '最近一次检查尝试：{time}',
    officialChanged: '已偏离基线',
    officialStable: '基线稳定',
    officialNote: '当前基线 {baseline}，最近检查 {lastFetch}',
    ghSignalFound: '发现新线索',
    ghNoSignal: '暂未发现新线索',
    repoSignal: '有线索',
    repoNoChange: '暂无新线索',
    alertPreview: '发现新线索后会发送通知并播放铃声。',
    triggered: '已触发',
    alertActionDone: '提醒已执行',
    alertPartial: '提醒已触发（部分成功）',
    alertDetail: '通知={webhook}，铃声={audio}',
    webhookUpdated: '通知地址已更新。',
    webhookUpdateFailed: '更新通知地址失败',
    webhookCleared: '通知地址已清空。',
    clearWebhookFailed: '清空通知地址失败',
    chooseMp3First: '请先选择 mp3 文件。',
    uploadAudioOk: '铃声已上传并启用。',
    uploadAudioFailed: '上传铃声失败',
    provideAudioPath: '请填写铃声路径。',
    setAudioPathOk: '铃声路径已启用。',
    setAudioPathFailed: '设置铃声路径失败',
    useDefaultAudioOk: '已切换到默认铃声。',
    useDefaultAudioFailed: '切换默认铃声失败',
    eventsEmpty: '还没有线索。',
    noTitle: '(无标题)',
    publishedAt: '事件时间',
    fetchedAt: '抓取时间',
    yes: '是',
    no: '否',
    on: '开',
    off: '关',
    n_a: 'n/a',
    kv: {
      provider: '监控对象',
      poll_interval: '检查频率',
      homepage: '官网地址',
      repos: '关注仓库',
      regex: '关键词规则',
      webhook_enabled: '通知开关',
      audio_enabled: '铃声开关',
      active_audio: '当前铃声',
      audio_mode: '铃声来源',
      alert_once: '仅提醒一次',
      last_poll: '最近一次手动检查',
      homepage_prev: '官网上次模型',
      homepage_new: '官网当前模型',
      homepage_v4_transition: '是否升级到 v4',
      github_matched: '仓库命中数',
      github_new_signals: '新线索数量',
      alert_triggered: '是否触发提醒',
      alert_signal: '触发来源'
    }
  },
  en: {
    pageTitle: 'DeepSeekV4 Spotter',
    subtitle: 'Watch website and repo activity to catch DeepSeek v4 clues as early as possible.',
    runPoll: 'Check Now',
    polling: 'Checking...',
    openPanel: 'Open Settings',
    hidePanel: 'Hide Settings',
    monitorTitle: 'Monitor Overview',
    officialTitle: 'Official Site',
    githubTitle: 'Repo Activity',
    alertTitle: 'Alert Status',
    detailPanelTitle: 'Settings & Records',
    runtimeConfigTitle: 'Current Settings',
    pollSnapshotTitle: 'Latest Check Result',
    customSettingsTitle: 'Notification & Sound',
    webhookLabel: 'Notification URL (Feishu Webhook supported)',
    webhookPlaceholder: 'https://your-webhook-url',
    saveWebhook: 'Save Notification URL',
    clearWebhook: 'Clear Notification URL',
    uploadMp3Label: 'Upload alert sound and use it',
    uploadAudio: 'Upload Sound',
    useDefaultAudio: 'Use Default Sound',
    audioPathLabel: 'Or enter a local MP3 path',
    audioPathPlaceholder: '/abs/path/to/your.mp3',
    setAudioPath: 'Use This Path',
    eventStreamTitle: 'Latest Clues',
    apiConfig: 'Config Data',
    apiEvents: 'Event Data',
    loading: 'loading...',
    waiting: 'waiting',
    idle: 'idle',
    noTrigger: 'no trigger',
    statusLine: 'Monitoring is running | {events} clues saved | page refreshed {time}',
    pollAttemptLine: 'Last check attempt: {time}',
    officialChanged: 'baseline changed',
    officialStable: 'stable baseline',
    officialNote: 'Baseline {baseline}, last check {lastFetch}',
    ghSignalFound: 'new clue found',
    ghNoSignal: 'no new clue yet',
    repoSignal: 'clue found',
    repoNoChange: 'no new clue',
    alertPreview: 'When a new clue appears, notification and sound will be triggered.',
    triggered: 'triggered',
    alertActionDone: 'alert delivered',
    alertPartial: 'alert triggered (partial success)',
    alertDetail: 'notification={webhook}, sound={audio}',
    webhookUpdated: 'Notification URL updated.',
    webhookUpdateFailed: 'Update notification URL failed',
    webhookCleared: 'Notification URL cleared.',
    clearWebhookFailed: 'Clear notification URL failed',
    chooseMp3First: 'Please choose an mp3 file first.',
    uploadAudioOk: 'Sound uploaded and activated.',
    uploadAudioFailed: 'Upload sound failed',
    provideAudioPath: 'Please provide a sound path.',
    setAudioPathOk: 'Sound path activated.',
    setAudioPathFailed: 'Set sound path failed',
    useDefaultAudioOk: 'Switched to default sound.',
    useDefaultAudioFailed: 'Switch default sound failed',
    eventsEmpty: 'No clues yet.',
    noTitle: '(no title)',
    publishedAt: 'event time',
    fetchedAt: 'fetched',
    yes: 'yes',
    no: 'no',
    on: 'on',
    off: 'off',
    n_a: 'n/a',
    kv: {
      provider: 'monitor target',
      poll_interval: 'check frequency',
      homepage: 'official site',
      repos: 'watched repos',
      regex: 'keyword rule',
      webhook_enabled: 'notification',
      audio_enabled: 'sound alert',
      active_audio: 'current sound',
      audio_mode: 'sound source',
      alert_once: 'alert once only',
      last_poll: 'latest manual check',
      homepage_prev: 'previous official model',
      homepage_new: 'current official model',
      homepage_v4_transition: 'upgraded to v4',
      github_matched: 'repo matches',
      github_new_signals: 'new clues',
      alert_triggered: 'alert triggered',
      alert_signal: 'trigger source'
    }
  }
};

function t(key) {
  return I18N[state.lang]?.[key] ?? I18N.en[key] ?? key;
}

function tk(key) {
  return I18N[state.lang]?.kv?.[key] ?? I18N.en?.kv?.[key] ?? key;
}

function fmt(template, values) {
  return String(template || '').replace(/\{([a-zA-Z0-9_]+)\}/g, (_, k) => {
    const v = values?.[k];
    return (v === undefined || v === null) ? '' : String(v);
  });
}

function langToggleText() {
  return state.lang === 'zh' ? 'EN' : '中文';
}

async function getJSON(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return await r.json();
}

async function postJSON(url, payload) {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload || {}),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return await r.json();
}

function fmtTime(iso) {
  if (!iso) return 'n/a';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function findLatestHomepageModel() {
  return state.events.find((e) => e.source === 'deepseek_homepage' && e.kind === 'homepage_model') || null;
}

function githubSignals() {
  return state.events.filter((e) => e.source === 'github_watch' && e.kind === 'github_v4_signal');
}

function setSettingsMsg(msg, level) {
  const el = document.getElementById('settingsMsg');
  el.textContent = msg || '';
  if (level === 'ok') el.style.color = '#66f3a6';
  else if (level === 'err') el.style.color = '#ff7c8b';
  else el.style.color = 'rgba(233,248,255,0.72)';
}

function renderTop() {
  const s = document.getElementById('statusLine');
  const p = document.getElementById('pollAttemptLine');
  const now = new Date().toLocaleString();
  const lastAttempt = state.cfg?.last_poll_attempt_at ? fmtTime(state.cfg.last_poll_attempt_at) : t('n_a');
  s.textContent = fmt(t('statusLine'), {
    provider: state.cfg?.provider || 'deepseek',
    events: state.events.length,
    time: now,
  });
  p.textContent = fmt(t('pollAttemptLine'), { time: lastAttempt });
}

function renderOfficial() {
  const latest = findLatestHomepageModel();
  const model = latest?.payload?.chosen || t('n_a');
  const changed = model !== t('n_a') && model.toLowerCase() !== BASELINE_MODEL;
  const lastFetchIso = state.cfg?.last_poll_attempt_at || latest?.fetched_at;

  document.getElementById('officialModel').textContent = model;

  const flag = document.getElementById('officialFlag');
  flag.className = `flag ${changed ? 'err' : 'ok'}`;
  flag.textContent = changed ? t('officialChanged') : t('officialStable');

  document.getElementById('officialNote').textContent = fmt(t('officialNote'), {
    baseline: BASELINE_MODEL,
    lastFetch: fmtTime(lastFetchIso),
  });
}

function renderGithub() {
  const rows = document.getElementById('repoRows');
  rows.innerHTML = '';

  const cfgRepos = state.cfg?.watch_github_repos || [];
  const signals = githubSignals();
  const touched = new Set(signals.map((e) => e.payload?.repo).filter(Boolean));

  document.getElementById('ghMain').textContent = String(signals.length);

  const hasSignal = signals.length > 0;
  const flag = document.getElementById('ghFlag');
  flag.className = `flag ${hasSignal ? 'warn' : 'ok'}`;
  flag.textContent = hasSignal ? t('ghSignalFound') : t('ghNoSignal');

  for (const repo of cfgRepos) {
    const line = document.createElement('div');
    line.className = 'repo-row';

    const left = document.createElement('span');
    left.textContent = repo;

    const right = document.createElement('span');
    const yes = touched.has(repo);
    right.className = yes ? 'ok' : 'idle';
    right.textContent = yes ? t('repoSignal') : t('repoNoChange');

    line.appendChild(left);
    line.appendChild(right);
    rows.appendChild(line);
  }
}

function renderAlert() {
  const a = state.poll?.alert || null;

  const main = document.getElementById('alertMain');
  const flag = document.getElementById('alertFlag');
  const note = document.getElementById('alertNote');

  if (!a) {
    main.textContent = t('idle');
    flag.className = 'flag warn';
    flag.textContent = t('noTrigger');
    note.textContent = t('alertPreview');
    return;
  }

  main.textContent = a.signal || t('triggered');
  const ok = a.webhook?.ok === true || a.audio?.ok === true;
  flag.className = `flag ${ok ? 'ok' : 'warn'}`;
  flag.textContent = ok ? t('alertActionDone') : t('alertPartial');

  const wk = a.webhook?.ok === true ? 'ok' : a.webhook?.ok === false ? 'failed' : t('n_a');
  const ad = a.audio?.ok === true ? 'ok' : a.audio?.ok === false ? 'failed' : t('n_a');
  note.textContent = fmt(t('alertDetail'), { webhook: wk, audio: ad });
}

function kvRow(k, v) {
  const row = document.createElement('div');
  row.className = 'row';
  const kk = document.createElement('span');
  kk.className = 'k';
  kk.textContent = tk(k);
  const vv = document.createElement('span');
  vv.className = 'v';
  vv.textContent = String(v ?? t('n_a'));
  row.appendChild(kk);
  row.appendChild(vv);
  return row;
}

function renderDetail() {
  const cfg = document.getElementById('cfgRows');
  cfg.innerHTML = '';
  if (state.cfg) {
    cfg.appendChild(kvRow('provider', state.cfg.provider));
    cfg.appendChild(kvRow('poll_interval', `${state.cfg.poll_interval_seconds}s`));
    cfg.appendChild(kvRow('homepage', state.cfg.homepage_url));
    cfg.appendChild(kvRow('repos', (state.cfg.watch_github_repos || []).join(', ')));
    cfg.appendChild(kvRow('regex', state.cfg.watch_deepseek_v4_regex));
    cfg.appendChild(kvRow('webhook_enabled', state.cfg.feishu_webhook_enabled ? t('yes') : t('no')));
    cfg.appendChild(kvRow('audio_enabled', state.cfg.audio_enabled ? t('yes') : t('no')));
    cfg.appendChild(kvRow('active_audio', state.cfg.audio_path || t('n_a')));
    cfg.appendChild(kvRow('audio_mode', state.cfg.audio_mode || 'default'));
    cfg.appendChild(kvRow('alert_once', state.cfg.alert_once ? t('on') : t('off')));
  }

  const poll = document.getElementById('pollRows');
  poll.innerHTML = '';
  const p = state.poll;
  if (!p) {
    poll.appendChild(kvRow('last_poll', state.lang === 'zh' ? '本次会话尚未执行' : 'not run in this session'));
  } else {
    const hp = p.homepage || {};
    const gh = p.github_watch || {};
    poll.appendChild(kvRow('homepage_prev', hp.prev_model || t('n_a')));
    poll.appendChild(kvRow('homepage_new', hp.new_model || t('n_a')));
    poll.appendChild(kvRow('homepage_v4_transition', hp.v4_transition ? t('yes') : t('no')));
    poll.appendChild(kvRow('github_matched', gh.matched ?? 0));
    poll.appendChild(kvRow('github_new_signals', (gh.new_signals || []).length));
    poll.appendChild(kvRow('alert_triggered', p.alert ? t('yes') : t('no')));
    if (p.alert?.signal) poll.appendChild(kvRow('alert_signal', p.alert.signal));
  }

  const webhookInput = document.getElementById('webhookInput');
  if (state.cfg?.webhook_url) webhookInput.value = state.cfg.webhook_url;

  const audioPathInput = document.getElementById('audioPathInput');
  if (state.cfg?.audio_path) audioPathInput.value = state.cfg.audio_path;
}

function renderEvents() {
  const box = document.getElementById('events');
  box.innerHTML = '';

  if (!state.events.length) {
    const n = document.createElement('div');
    n.className = 'evt';
    n.textContent = t('eventsEmpty');
    box.appendChild(n);
    return;
  }

  for (const e of state.events) {
    const card = document.createElement('div');
    card.className = 'evt';

    const top = document.createElement('div');
    top.className = 'evt-top';

    const title = document.createElement('div');
    title.className = 'evt-title';
    title.textContent = e.title || t('noTitle');

    const badge = document.createElement('span');
    badge.className = 'evt-badge';
    badge.textContent = `${e.source || '?'}:${e.kind || '?'}`;

    top.appendChild(title);
    top.appendChild(badge);

    const meta = document.createElement('div');
    meta.className = 'evt-meta';
    meta.appendChild(document.createTextNode(`${t('publishedAt')}: ${fmtTime(e.published_at)}`));
    meta.appendChild(document.createTextNode(`${t('fetchedAt')}: ${fmtTime(e.fetched_at)}`));

    if (e.url) {
      const a = document.createElement('a');
      a.href = e.url;
      a.target = '_blank';
      a.rel = 'noreferrer';
      a.textContent = e.url;
      meta.appendChild(a);
    }

    card.appendChild(top);
    card.appendChild(meta);
    box.appendChild(card);
  }
}

function renderAll() {
  applyI18n();
  renderTop();
  renderOfficial();
  renderGithub();
  renderAlert();
  renderDetail();
  renderEvents();
}

async function loadConfig() {
  try { state.cfg = await getJSON('/api/config'); } catch (_) { state.cfg = null; }
}

async function loadEvents() {
  const data = await getJSON('/api/events?limit=80');
  state.events = data.events || [];
}

async function pollNow() {
  const btn = document.getElementById('pollBtn');
  state.polling = true;
  btn.disabled = true;
  btn.textContent = t('polling');
  try {
    state.poll = await getJSON('/api/poll', { method: 'POST' });
  } catch (_) {
    // keep previous snapshot
  } finally {
    try { await loadEvents(); } catch (_) {}
    state.polling = false;
    renderAll();
  }
}

function updateToggleBtnText() {
  const btn = document.getElementById('toggleBtn');
  const details = document.getElementById('details');
  btn.textContent = details.hidden ? t('openPanel') : t('hidePanel');
}

function setupToggle() {
  const details = document.getElementById('details');
  document.getElementById('toggleBtn').addEventListener('click', () => {
    details.hidden = !details.hidden;
    updateToggleBtnText();
  });
  updateToggleBtnText();
}

async function saveWebhook() {
  const v = document.getElementById('webhookInput').value.trim();
  try {
    const res = await postJSON('/api/settings', { webhook_url: v });
    state.cfg = res.config;
    setSettingsMsg(t('webhookUpdated'), 'ok');
    renderAll();
  } catch (err) {
    setSettingsMsg(`${t('webhookUpdateFailed')}: ${err.message}`, 'err');
  }
}

async function clearWebhook() {
  try {
    const res = await postJSON('/api/settings', { webhook_url: '' });
    state.cfg = res.config;
    document.getElementById('webhookInput').value = '';
    setSettingsMsg(t('webhookCleared'), 'ok');
    renderAll();
  } catch (err) {
    setSettingsMsg(`${t('clearWebhookFailed')}: ${err.message}`, 'err');
  }
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const txt = String(reader.result || '');
      const idx = txt.indexOf('base64,');
      if (idx < 0) {
        reject(new Error(state.lang === 'zh' ? 'base64 数据无效' : 'invalid base64 data')); return;
      }
      resolve(txt.slice(idx + 7));
    };
    reader.onerror = () => reject(new Error(state.lang === 'zh' ? '文件读取失败' : 'read file failed'));
    reader.readAsDataURL(file);
  });
}

async function uploadAudio() {
  const fileInput = document.getElementById('audioFile');
  const file = fileInput.files && fileInput.files[0];
  if (!file) {
    setSettingsMsg(t('chooseMp3First'), 'warn');
    return;
  }

  try {
    const b64 = await fileToBase64(file);
    const res = await postJSON('/api/upload_audio', {
      filename: file.name,
      content_base64: b64,
    });
    state.cfg = res.config;
    document.getElementById('audioPathInput').value = res.path || '';
    fileInput.value = '';
    setSettingsMsg(t('uploadAudioOk'), 'ok');
    renderAll();
  } catch (err) {
    setSettingsMsg(`${t('uploadAudioFailed')}: ${err.message}`, 'err');
  }
}

async function setAudioPath() {
  const p = document.getElementById('audioPathInput').value.trim();
  if (!p) {
    setSettingsMsg(t('provideAudioPath'), 'warn');
    return;
  }

  try {
    const res = await postJSON('/api/settings', { alert_mp3_path: p });
    state.cfg = res.config;
    setSettingsMsg(t('setAudioPathOk'), 'ok');
    renderAll();
  } catch (err) {
    setSettingsMsg(`${t('setAudioPathFailed')}: ${err.message}`, 'err');
  }
}

async function useDefaultAudio() {
  try {
    const res = await postJSON('/api/settings', { alert_mp3_mode: 'default' });
    state.cfg = res.config;
    document.getElementById('audioPathInput').value = state.cfg.audio_path || '';
    setSettingsMsg(t('useDefaultAudioOk'), 'ok');
    renderAll();
  } catch (err) {
    setSettingsMsg(`${t('useDefaultAudioFailed')}: ${err.message}`, 'err');
  }
}

function setupSettingsActions() {
  document.getElementById('saveWebhookBtn').addEventListener('click', saveWebhook);
  document.getElementById('clearWebhookBtn').addEventListener('click', clearWebhook);
  document.getElementById('uploadAudioBtn').addEventListener('click', uploadAudio);
  document.getElementById('setAudioPathBtn').addEventListener('click', setAudioPath);
  document.getElementById('useDefaultAudioBtn').addEventListener('click', useDefaultAudio);
}

function applyI18n() {
  document.documentElement.lang = state.lang === 'zh' ? 'zh-CN' : 'en';
  document.title = t('pageTitle');

  document.getElementById('subtitleText').textContent = t('subtitle');
  document.getElementById('monitorTitle').textContent = t('monitorTitle');
  document.getElementById('officialTitle').textContent = t('officialTitle');
  document.getElementById('ghTitle').textContent = t('githubTitle');
  document.getElementById('alertTitle').textContent = t('alertTitle');
  document.getElementById('detailPanelTitle').textContent = t('detailPanelTitle');
  document.getElementById('runtimeConfigTitle').textContent = t('runtimeConfigTitle');
  document.getElementById('pollSnapshotTitle').textContent = t('pollSnapshotTitle');
  document.getElementById('customSettingsTitle').textContent = t('customSettingsTitle');
  document.getElementById('webhookLabel').textContent = t('webhookLabel');
  document.getElementById('uploadMp3Label').textContent = t('uploadMp3Label');
  document.getElementById('audioPathLabel').textContent = t('audioPathLabel');
  document.getElementById('eventStreamTitle').textContent = t('eventStreamTitle');
  document.getElementById('apiConfigLink').textContent = t('apiConfig');
  document.getElementById('apiEventsLink').textContent = t('apiEvents');

  document.getElementById('webhookInput').placeholder = t('webhookPlaceholder');
  document.getElementById('audioPathInput').placeholder = t('audioPathPlaceholder');

  document.getElementById('saveWebhookBtn').textContent = t('saveWebhook');
  document.getElementById('clearWebhookBtn').textContent = t('clearWebhook');
  document.getElementById('uploadAudioBtn').textContent = t('uploadAudio');
  document.getElementById('useDefaultAudioBtn').textContent = t('useDefaultAudio');
  document.getElementById('setAudioPathBtn').textContent = t('setAudioPath');

  const pollBtn = document.getElementById('pollBtn');
  pollBtn.disabled = state.polling;
  pollBtn.textContent = state.polling ? t('polling') : t('runPoll');

  document.getElementById('langBtn').textContent = langToggleText();
  updateToggleBtnText();
}

function setLanguage(lang) {
  if (lang !== 'zh' && lang !== 'en') return;
  state.lang = lang;
  localStorage.setItem('dsv4_lang', lang);
  renderAll();
}

function setupLanguage() {
  document.getElementById('langBtn').addEventListener('click', () => {
    setLanguage(state.lang === 'zh' ? 'en' : 'zh');
  });
}

async function boot() {
  await Promise.all([loadConfig(), loadEvents()]);
  setupLanguage();
  setupToggle();
  setupSettingsActions();
  renderAll();

  // Keep runtime metadata fresh (especially auto-poll timestamps)
  setInterval(async () => {
    try {
      await loadConfig();
      renderTop();
    } catch (_) {
      // ignore transient refresh errors
    }
  }, 10000);
}

document.getElementById('pollBtn').addEventListener('click', pollNow);
boot();
</script>
</body>
</html>"""


def _build_config_payload() -> Dict[str, Any]:
    s = get_settings()
    runtime = load_runtime_settings()
    poll_meta = _get_poll_meta()

    return {
        "provider": s.provider,
        "homepage_url": s.homepage_url,
        "poll_interval_seconds": s.poll_interval_seconds,
        "watch_github_repos": s.watch_github_repos,
        "watch_deepseek_v4_regex": s.watch_deepseek_v4_regex,
        "feishu_webhook_enabled": bool(s.feishu_webhook_url),
        "webhook_url": s.feishu_webhook_url,
        "audio_enabled": bool(s.alert_mp3_path),
        "audio_path": s.alert_mp3_path,
        "default_audio_path": _DEFAULT_MP3 if os.path.exists(_DEFAULT_MP3) else None,
        "audio_mode": "custom" if "alert_mp3_path" in runtime else "default",
        "alert_loops": s.alert_loops,
        "alert_interval_seconds": s.alert_interval_seconds,
        "alert_once": s.alert_once,
        "last_poll_attempt_at": poll_meta.get("last_poll_attempt_at"),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "DeepSeekTrackerLite/0.1"

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, data: Dict[str, Any]) -> None:
        self._send(code, json.dumps(data, ensure_ascii=True).encode("utf-8"), "application/json; charset=utf-8")

    def _read_json_body(self) -> Dict[str, Any]:
        raw_len = self.headers.get("Content-Length") or "0"
        try:
            n = int(raw_len)
        except ValueError:
            n = 0

        if n <= 0:
            return {}

        # Hard limit 25MB JSON body to avoid abuse.
        if n > 25 * 1024 * 1024:
            raise ValueError("payload_too_large")

        raw = self.rfile.read(n)
        if not raw:
            return {}

        data = json.loads(raw.decode("utf-8"))
        if isinstance(data, dict):
            return data
        return {}

    def do_GET(self) -> None:  # noqa: N802
        p = urlparse(self.path)
        if p.path == "/":
            self._send(200, _HTML.encode("utf-8"), "text/html; charset=utf-8")
            return

        if p.path == "/api/config":
            self._send_json(200, _build_config_payload())
            return

        if p.path == "/api/events":
            s = get_settings()
            qs = parse_qs(p.query or "")
            limit = 50
            try:
                if "limit" in qs:
                    limit = int(qs["limit"][0])
            except Exception:
                limit = 50

            with connect(s.db_path) as conn:
                init_db(conn)
                events = list_events(conn, provider=s.provider, limit=limit)

            self._send_json(200, {"events": events})
            return

        self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        p = urlparse(self.path)

        if p.path == "/api/poll":
            _mark_poll_attempt()
            res = poll_homepage_once()
            self._send_json(200, res)
            return

        if p.path == "/api/settings":
            try:
                body = self._read_json_body()
            except Exception as e:
                self._send_json(400, {"ok": False, "error": f"invalid_json:{type(e).__name__}"})
                return

            set_values: Dict[str, Any] = {}
            clear_keys = []

            if "webhook_url" in body:
                webhook = str(body.get("webhook_url") or "").strip()
                if webhook:
                    set_values["feishu_webhook_url"] = webhook
                else:
                    clear_keys.append("feishu_webhook_url")

            if body.get("alert_mp3_mode") == "default":
                clear_keys.append("alert_mp3_path")

            if "alert_mp3_path" in body:
                pth = str(body.get("alert_mp3_path") or "").strip()
                if not pth:
                    clear_keys.append("alert_mp3_path")
                else:
                    if not pth.lower().endswith(".mp3"):
                        self._send_json(400, {"ok": False, "error": "audio_path_must_be_mp3"})
                        return
                    if not os.path.exists(pth):
                        self._send_json(400, {"ok": False, "error": "audio_path_not_found"})
                        return
                    set_values["alert_mp3_path"] = os.path.abspath(pth)

            update_runtime_settings(set_values=set_values, clear_keys=clear_keys)
            self._send_json(200, {"ok": True, "config": _build_config_payload()})
            return

        if p.path == "/api/upload_audio":
            try:
                body = self._read_json_body()
            except Exception as e:
                self._send_json(400, {"ok": False, "error": f"invalid_json:{type(e).__name__}"})
                return

            filename = str(body.get("filename") or "custom.mp3")
            b64 = str(body.get("content_base64") or "").strip()
            if not b64:
                self._send_json(400, {"ok": False, "error": "missing_content_base64"})
                return

            try:
                content = base64.b64decode(b64, validate=True)
            except Exception:
                self._send_json(400, {"ok": False, "error": "invalid_base64"})
                return

            if len(content) > 20 * 1024 * 1024:
                self._send_json(400, {"ok": False, "error": "audio_file_too_large"})
                return

            if not filename.lower().endswith(".mp3"):
                self._send_json(400, {"ok": False, "error": "file_extension_must_be_mp3"})
                return

            out_path = save_uploaded_mp3(filename=filename, content=content)
            update_runtime_settings(set_values={"alert_mp3_path": out_path})

            self._send_json(200, {"ok": True, "path": out_path, "config": _build_config_payload()})
            return

        self._send(404, b"not found", "text/plain; charset=utf-8")

    def log_message(self, fmt: str, *args) -> None:
        return


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    s = get_settings()
    with connect(s.db_path) as conn:
        init_db(conn)

    def autopoll_loop() -> None:
        while True:
            s2 = get_settings()
            if s2.poll_interval_seconds == 0:
                return
            _mark_poll_attempt()
            try:
                poll_homepage_once()
            except Exception:
                pass
            time.sleep(s2.poll_interval_seconds)

    if s.poll_interval_seconds != 0:
        t = threading.Thread(target=autopoll_loop, name="autopoll", daemon=True)
        t.start()

    httpd = HTTPServer((host, port), Handler)
    httpd.serve_forever()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--interval-seconds", type=int, default=None, help="Auto-poll interval; default 600; 0 disables")
    ap.add_argument("--feishu-webhook-url", default=None, help="Optional webhook on startup")
    args = ap.parse_args()

    if args.interval_seconds is not None:
        os.environ["POLL_INTERVAL_SECONDS"] = str(args.interval_seconds)
    if args.feishu_webhook_url:
        os.environ["FEISHU_WEBHOOK_URL"] = args.feishu_webhook_url

    run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
