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

async function copy(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
    const old = btn.textContent;
    btn.textContent = "已复制 ✓";
    setTimeout(() => (btn.textContent = old), 1500);
  } catch {
    setStatus("复制失败，请手动长按链接复制", "error");
  }
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
  copyBtn.addEventListener("click", () => copy(data.video_url, copyBtn));
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
    const cell = el("a", { class: "cell", href: img.download_url, download: "" });
    cell.append(el("img", { src: img.url, alt: `图 ${i + 1}`, loading: "lazy" }));
    cell.append(el("span", { class: "cell-tag", text: `下载 ${i + 1}` }));
    grid.append(cell);
  });
  card.append(grid);

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
  card.append(all);

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
