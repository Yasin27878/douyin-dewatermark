import "./style.css";

const $ = (sel) => document.querySelector(sel);

const form = $("#form");
const input = $("#input");
const statusEl = $("#status");
const resultEl = $("#result");

function setStatus(msg, kind = "") {
  if (!msg) {
    statusEl.hidden = true;
    statusEl.textContent = "";
    statusEl.className = "status";
    return;
  }
  statusEl.hidden = false;
  statusEl.textContent = msg;
  statusEl.className = `status ${kind}`.trim();
}

function clearResult() {
  resultEl.hidden = true;
  resultEl.replaceChildren();
}

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (v !== undefined && v !== null) node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    if (c) node.append(c);
  }
  return node;
}

async function copyText(text) {
  // 安全上下文（HTTPS / localhost）优先用 Clipboard API
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      /* 失败则落到下面的兜底方案 */
    }
  }
  // 兜底：HTTP 局域网 / 旧浏览器 / iOS 下用临时 textarea + execCommand
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.readOnly = true;
    ta.style.position = "fixed";
    ta.style.top = "0";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, text.length); // iOS 需要显式选区
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

async function copy(text, btn) {
  if (await copyText(text)) {
    const old = btn.textContent;
    btn.textContent = "已复制 ✓";
    setTimeout(() => (btn.textContent = old), 1500);
  } else {
    setStatus("复制失败，请手动长按链接复制", "error");
  }
}

// 可在浏览器直接打开的链接：走本服务代理（带 Referer，规避 CDN 防盗链 403），
// inline=1 让浏览器直接显示图片 / 播放视频。用绝对地址，复制到别处也能用。
function openableLink(downloadUrl) {
  return location.origin + downloadUrl + "&inline=1";
}

function metaLine(data) {
  const bits = [];
  if (data.author) bits.push(`@${data.author}`);
  if (data.duration) bits.push(`${Math.round(data.duration)}s`);
  return bits.join(" · ");
}

function renderVideo(data) {
  const card = el("div", { class: "card" });
  if (data.cover) {
    card.append(el("img", { class: "cover", src: data.cover, alt: "封面", loading: "lazy" }));
  }
  card.append(el("h2", { class: "title", text: data.title || "无标题" }));
  const meta = metaLine(data);
  if (meta) card.append(el("p", { class: "meta", text: meta }));

  const actions = el("div", { class: "actions" });
  const dl = el("a", {
    class: "btn primary",
    href: data.download_url,
    download: "",
    text: "下载无水印视频",
  });
  const copyBtn = el("button", { class: "btn ghost", type: "button", text: "复制直链" });
  copyBtn.addEventListener("click", () => copy(openableLink(data.download_url), copyBtn));
  actions.append(dl, copyBtn);
  card.append(actions);

  resultEl.replaceChildren(card);
  resultEl.hidden = false;
}

function renderImages(data) {
  const card = el("div", { class: "card" });
  card.append(el("h2", { class: "title", text: data.title || "图集" }));
  const meta = metaLine(data);
  if (meta) card.append(el("p", { class: "meta", text: meta }));

  const grid = el("div", { class: "grid" });
  data.images.forEach((img, i) => {
    const cell = el("div", { class: "cell" });
    cell.append(el("img", { src: img.url, alt: `图 ${i + 1}`, loading: "lazy" }));
    const bar = el("div", { class: "cell-actions" });
    bar.append(el("a", { class: "cell-btn", href: img.download_url, download: "", text: `下载 ${i + 1}` }));
    const cp = el("button", { class: "cell-btn", type: "button", text: "复制" });
    cp.addEventListener("click", () => copy(openableLink(img.download_url), cp));
    bar.append(cp);
    cell.append(bar);
    grid.append(cell);
  });
  card.append(grid);

  const actions = el("div", { class: "actions" });
  const all = el("button", { class: "btn primary", type: "button", text: `下载全部 (${data.images.length})` });
  all.addEventListener("click", () => {
    data.images.forEach((img, i) => {
      setTimeout(() => {
        const a = el("a", { href: img.download_url, download: "" });
        document.body.append(a);
        a.click();
        a.remove();
      }, i * 300); // 错开，避免浏览器拦截连续下载
    });
  });
  const copyAll = el("button", { class: "btn ghost", type: "button", text: "复制全部直链" });
  copyAll.addEventListener("click", () => copy(data.images.map((im) => openableLink(im.download_url)).join("\n"), copyAll));
  actions.append(all, copyAll);
  card.append(actions);

  resultEl.replaceChildren(card);
  resultEl.hidden = false;
}

async function doParse(text) {
  const value = (text || "").trim();
  if (!value) {
    setStatus("请先粘贴链接", "error");
    return;
  }
  setStatus("解析中…", "loading");
  clearResult();
  try {
    const res = await fetch(`/api/parse?url=${encodeURIComponent(value)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `解析失败 (${res.status})`);
    if (data.type === "images") renderImages(data);
    else renderVideo(data);
    setStatus("");
  } catch (e) {
    setStatus(e.message || String(e), "error");
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  doParse(input.value);
});

$("#clear").addEventListener("click", () => {
  input.value = "";
  clearResult();
  setStatus("");
  input.focus();
});

// PWA 分享目标 / 直接带参进入：?url= 或 ?text= 或 ?title=
const params = new URLSearchParams(location.search);
const shared = params.get("url") || params.get("text") || params.get("title");
if (shared) {
  input.value = shared;
  history.replaceState(null, "", location.pathname); // 清掉参数，避免刷新重复解析
  doParse(shared);
}

// 仅生产环境注册 Service Worker（开发时避免缓存干扰 HMR）
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
