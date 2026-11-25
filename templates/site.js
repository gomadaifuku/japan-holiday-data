"use strict";

const byId = (id) => document.getElementById(id);
const yearSelect = byId("year");
const timestamp = new Intl.DateTimeFormat("ja-JP", {
  timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});
const currentYear = Number(new Intl.DateTimeFormat("en-US", {
  timeZone: "Asia/Tokyo", year: "numeric",
}).format(new Date()));
const weekdays = new Intl.DateTimeFormat("ja-JP", {timeZone: "UTC", weekday: "short"});
const hashPattern = /^[a-f0-9]{64}$/;
const yearKey = (year) => String(year).padStart(4, "0");
let manifest;
let sequence = 0;

async function getJson(path) {
  const response = await fetch(path, {cache: "no-store"});
  if (!response.ok) throw new Error("データの取得に失敗しました（HTTP " + response.status + "）。");
  return response.json();
}

function checkManifest(data) {
  if (data?.schemaVersion !== 1 || !Number.isInteger(data.minYear) || !Number.isInteger(data.maxYear)
      || data.minYear < 1 || data.maxYear > 9999 || data.minYear > data.maxYear
      || !Number.isSafeInteger(data.recordCount) || data.recordCount < 1
      || !hashPattern.test(data.dataVersion) || !Number.isFinite(Date.parse(data.updatedAt))
      || !Number.isFinite(Date.parse(data.checkedAt)) || !data.yearVersions
      || Object.keys(data.yearVersions).length !== data.maxYear - data.minYear + 1) {
    throw new Error("配信情報の形式を確認できません。");
  }
  for (let year = data.minYear; year <= data.maxYear; year++) {
    if (!hashPattern.test(data.yearVersions[yearKey(year)])) throw new Error("年別バージョンが不正です。");
  }
}

function setStatus(message, visuallyHidden = false) {
  const status = byId("list-status");
  status.classList.toggle("sr-only", visuallyHidden);
  status.textContent = message;
}

function renderRows(year, data) {
  if (data?.schemaVersion !== 1 || data.year !== Number(year)
      || data.dataVersion !== manifest.yearVersions[year]) {
    throw new Error("配信情報と年別データのバージョンが異なります。しばらくしてから再読み込みしてください。");
  }
  if (!data.holidays || Array.isArray(data.holidays) || typeof data.holidays !== "object"
      || Object.keys(data.holidays).length === 0) throw new Error("祝日の一覧が不正です。");
  const rows = document.createDocumentFragment();
  for (const day of Object.keys(data.holidays).sort()) {
    const iso = year + "-" + day;
    const date = new Date(iso + "T00:00:00Z");
    const name = data.holidays[day];
    if (!/^\d{2}-\d{2}$/.test(day) || !Number.isFinite(date.getTime())
        || date.toISOString().slice(0, 10) !== iso || typeof name !== "string" || !name.trim()) {
      throw new Error("祝日データの日付または名称が不正です。");
    }
    const row = document.createElement("tr");
    const dateCell = document.createElement("th");
    dateCell.scope = "row";
    const time = document.createElement("time");
    time.dateTime = iso;
    time.textContent = Number(day.slice(0, 2)) + "月" + Number(day.slice(3)) + "日";
    dateCell.append(time);
    const weekday = document.createElement("td");
    weekday.textContent = weekdays.format(date);
    const holiday = document.createElement("td");
    holiday.textContent = name;
    row.append(dateCell, weekday, holiday);
    rows.append(row);
  }
  byId("rows").replaceChildren(rows);
}

async function showYear() {
  const request = ++sequence;
  const year = yearKey(yearSelect.value);
  byId("retry").hidden = true;
  byId("list").hidden = true;
  byId("download").hidden = true;
  if (!Object.hasOwn(manifest.yearVersions, year)) {
    setStatus(year + "年の祝日データはまだ収録されていません。他の年を選択できます。");
    return;
  }
  const path = "holidays/" + year + ".json";
  setStatus(year + "年の祝日を読み込んでいます。");
  try {
    const data = await getJson(path);
    // 年を素早く切り替えた場合、遅れて返った古い応答を画面に反映しない。
    if (request !== sequence) return;
    renderRows(year, data);
    byId("caption").textContent = year + "年の祝日・休日";
    byId("list").hidden = false;
    const download = byId("download");
    download.href = path;
    download.download = year + ".json";
    download.textContent = year + "年のJSONをダウンロード";
    download.hidden = false;
    setStatus(year + "年の祝日・休日を" + Object.keys(data.holidays).length + "件表示しました。", true);
  } catch (error) {
    if (request !== sequence) return;
    setStatus("年別データを表示できません。" + error.message);
    byId("retry").hidden = false;
  }
}

async function load() {
  ++sequence;
  const preferred = Number(yearSelect.value) || currentYear;
  yearSelect.disabled = true;
  byId("retry").hidden = true;
  setStatus("配信情報を読み込んでいます。");
  try {
    const data = await getJson("manifest.json");
    checkManifest(data);
    manifest = data;
    byId("period").textContent = data.minYear + "年～" + data.maxYear + "年";
    byId("count").textContent = data.recordCount.toLocaleString("ja-JP") + "件";
    byId("checked").textContent = timestamp.format(new Date(data.checkedAt));
    byId("updated").textContent = timestamp.format(new Date(data.updatedAt));
    byId("schema").textContent = data.schemaVersion;
    byId("version").textContent = data.dataVersion;
    byId("stale").hidden = Date.now() - Date.parse(data.checkedAt) <= 14 * 24 * 60 * 60 * 1000;
    const years = new Set(Object.keys(data.yearVersions).map(Number));
    years.add(currentYear);
    const options = [...years].sort((a, b) => b - a).map((year) =>
      new Option(year + "年" + (Object.hasOwn(data.yearVersions, yearKey(year)) ? "" : "（未収録）"), year));
    yearSelect.replaceChildren(...options);
    yearSelect.value = years.has(preferred) ? preferred : currentYear;
    yearSelect.disabled = false;
    await showYear();
  } catch (error) {
    yearSelect.replaceChildren(new Option("取得失敗", ""));
    setStatus("配信情報を表示できません。" + error.message);
    byId("retry").hidden = false;
  }
}

yearSelect.addEventListener("change", showYear);
byId("retry").addEventListener("click", load);
load();
