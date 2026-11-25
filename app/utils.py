import streamlit as st
import pandas as pd
import anywidget
import traitlets

import json
import re 

from tbs import TimeTable, report_result, date_pattern

class VisTimeline(anywidget.AnyWidget):
    _esm = """
    const VIS_URL = "https://esm.sh/vis-timeline@7.7.3/standalone";
    const CSS_URL = "https://esm.sh/vis-timeline@7.7.3/styles/vis-timeline-graph2d.min.css";

    let selectedId = null;
    let lastKey = null;

    function ensureStylesheet() {
      const id = "vis-timeline-css";
      if (document.getElementById(id)) return;
      const link = document.createElement("link");
      link.id = id;
      link.rel = "stylesheet";
      link.href = CSS_URL;
      document.head.appendChild(link);
    }

    const esc = (s) => String(s ?? "").replace(/[&<>"]/g,
      c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

    const pick = (obj, keys) => {
      for (const k of keys) {
        if (obj[k] != null && String(obj[k]).trim() !== "") return { key: k, value: obj[k] };
      }
      return null;
    };

    const fmtDate = (s) => {
      const t = Date.parse(s);
      return Number.isNaN(t) ? s : new Date(t).toLocaleDateString(undefined,
        { year: "numeric", month: "short", day: "numeric" });
    };

    const flat = (v) => (v && typeof v === "object") ? JSON.stringify(v) : v;

    function renderArticle(a) {
      if (!a || typeof a !== "object") return `<div class="vt-row"><b>${esc(a)}</b></div>`;
      const t   = pick(a, ["Title"]);
      const dt  = pick(a, ["Date"]);
      const aut = pick(a, ["Author"]);
      const pap = pick(a, ["Newspaper"]);
      const skip = new Set([t && t.key, dt && dt.key, aut && aut.key, pap && pap.key].filter(Boolean));
      const body = Object.entries(a)
        .filter(([k]) => !skip.has(k))
        .map(([k, v]) => `<div class="vt-sub"><div>${esc(flat(v))}</div></div>`)
        .join("");
      return `
        <details class="vt-article">
          <summary>
            <span class="vt-art-title">${esc(t ? t.value : "Untitled")}</span>
            ${dt ? `<span class="vt-art-date">${esc(fmtDate(dt.value))}</span>` : ""}
            <span class="vt-art-author">${esc(aut ? aut.value : "No author")}</span>
            <span class="vt-art-paper">${esc(pap ? pap.value : "No newspaper")}</span>
          </summary>
          <div class="vt-art-body">${body}</div>
        </details>`;
    }

    function renderField(k, v) {
      if (Array.isArray(v)) {
        if (v.length === 0)
          return `<div class="vt-row"><span>${esc(k)}</span><b class="vt-none">none</b></div>`;
        if (v.every((x) => x === null || typeof x !== "object"))
          return `<div class="vt-row"><span>${esc(k)}</span><b>${esc(v.join(", "))}</b></div>`;
        return `
          <div class="vt-group">
            <div class="vt-group-head"><span class="vt-count">${v.length}</span> article(s) found.</div>
            ${v.map(renderArticle).join("")}
          </div>`;
      }
      if (v && typeof v === "object")
        return `
          <div class="vt-group">
            <div class="vt-group-head">${esc(k)}</div>
            ${Object.entries(v).map(([k2, v2]) => renderField(k2, v2)).join("")}
          </div>`;
      return `<div class="vt-row"><span>${esc(k)}</span><b>${esc(v)}</b></div>`;
    }

    function render({ model, el }) {
      ensureStylesheet();
      el.classList.add("vt-widget");

      const container = document.createElement("div");
      const panel = document.createElement("div");
      panel.className = "vt-panel";
      el.appendChild(container);
      el.appendChild(panel);

      let tl = null;
      let byId = new Map();
      let disposed = false;

      const indexItems = (arr) => {
        byId = new Map((arr || []).map((it) => [it.id, it]));
      };

      function showDetail(id) {
        if (id == null) {
          panel.innerHTML = "<p class='vt-empty'>Select an event to see details.</p>";
          return;
        }
        const item = byId.get(id) || {};
        const d = item.detail || {};
        const when = item.end
          ? `${fmtDate(item.start)} \u2013 ${fmtDate(item.end)}`
          : fmtDate(item.start);
        const rows = Object.entries(d).map(([k, v]) => renderField(k, v)).join("");
        panel.innerHTML = `
          <div class="vt-when">${esc(when)}</div>
          <p class="vt-body">${esc(item.content)}</p>
          ${rows}
        `;
      }

      (async () => {
        let Timeline;
        try {
          const vis = await import(VIS_URL);
          Timeline = vis.Timeline || (vis.default && vis.default.Timeline);
          if (!Timeline) throw new Error("Timeline export not found on module namespace");
        } catch (err) {
          panel.innerHTML =
            `<p class="vt-empty">Could not load vis-timeline: ${esc(String(err))}</p>`;
          console.error("vis-timeline load failed", err);
          return;
        }
        if (disposed) return;

        const defaults = {
          height: model.get("height"),
          width: model.get("width"),
          verticalScroll: true,
          horizontalScroll: true,
          zoomKey: "ctrlKey",
          orientation: { axis: "top", item: "top" },
          stack: true,
          margin: { item: { horizontal: 10, vertical: 10 }, axis: 20 },
          tooltip: { followMouse: true, overflowMethod: "flip" },
        };
        const options = Object.assign(defaults, model.get("options"));

        const data = model.get("items") || [];
        const groups = model.get("groups") || [];
        indexItems(data);

        tl = new Timeline(container, data, groups.length ? groups : undefined, options);

        showDetail(null);

        tl.on("select", (props) => {
          selectedId = props.items.length ? props.items[0] : null;
          showDetail(selectedId);
          if (model.get("emit_selection")) {
            model.set("selected", props.items);
            model.save_changes();
          }
        });

        model.on("change:items", () => {
          const next = model.get("items") || [];
          const key = JSON.stringify(next);
          if (key === lastKey) return;
          lastKey = key
          indexItems(next);
          tl.setItems(next);
          if (selectedId != null && byId.has(selectedId)) {
            showDetail(selectedId);  
          } else {
            selectedId = null;
            showDetail(null);
          }
        });
      })();

      return () => { disposed = true; if (tl) tl.destroy(); };
    }

    export default { render };
    """

    _css = """
    .vt-widget .vis-item .vis-item-content {
      white-space: normal;
      overflow-wrap: break-word;
      padding: 4px 6px;
      line-height: 1.3;
    }
    .vt-widget .vis-item.vis-box .vis-item-content,
    .vt-widget .vis-item.vis-point .vis-item-content { max-width: 240px; }
    .vt-widget .vis-item.vis-range { overflow: hidden; }
    .vt-widget .vis-item.vis-range .vis-item-content { max-width: 100%; }

    .vt-widget { width: 100%; box-sizing: border-box; }
    .vt-widget > div { width: 100%; box-sizing: border-box; }

    .vt-widget .vt-panel {
      margin-top: 12px;
      padding: 12px 14px;
      border: 1px solid rgba(128,128,128,0.35);
      border-radius: 6px;
      font-size: 0.9rem;
      line-height: 1.45;
      min-height: 4.5rem;
      max-height: 420px;
      overflow-y: auto;
      overflow-x: hidden;
    }
    .vt-widget .vt-panel * { min-width: 0; }

    .vt-widget .vt-when {
      opacity: 0.65; font-size: 0.8rem; margin-bottom: 6px;
      overflow-wrap: anywhere;
    }
    .vt-widget .vt-body { margin: 0 0 10px; overflow-wrap: anywhere; }

    .vt-widget .vt-row {
      display: flex; justify-content: space-between;
      align-items: baseline; gap: 1rem;
      padding: 3px 0; border-bottom: 1px solid rgba(128,128,128,0.15);
    }
    .vt-widget .vt-row > span { flex: 0 0 auto; opacity: 0.7; }
    .vt-widget .vt-row > b {
      flex: 1 1 auto; text-align: right; overflow-wrap: anywhere;
    }
    .vt-widget .vt-empty { opacity: 0.55; margin: 0; }
    .vt-widget .vt-none { opacity: 0.45; font-weight: normal; }

    .vt-widget .vt-group { margin: 10px 0 4px; }
    .vt-widget .vt-group-head {
      font-size: 0.78rem; opacity: 0.6;
      display: flex; align-items: center; gap: 6px; margin-bottom: 4px;
    }
    .vt-widget .vt-count {
      font-size: 0.7rem; padding: 0 6px; border-radius: 8px;
      border: 1px solid rgba(128,128,128,0.4); flex: 0 0 auto;
    }

    .vt-widget .vt-article {
      border: 1px solid rgba(128,128,128,0.25);
      border-radius: 5px; margin-bottom: 5px; padding: 6px 9px;
    }
    .vt-widget .vt-article > summary {
      cursor: pointer;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 2px 10px;
      align-items: baseline;
      list-style: none;
    }
    .vt-widget .vt-article > summary::-webkit-details-marker { display: none; }

    .vt-widget .vt-art-title { font-weight: 600; overflow-wrap: anywhere; }
    .vt-widget .vt-art-title::before {
      content: "▸ "; opacity: 0.5; font-weight: normal;
    }
    .vt-widget .vt-article[open] .vt-art-title::before { content: "▾ "; }

    .vt-widget .vt-art-date {
      justify-self: end; opacity: 0.6; font-size: 0.78rem; white-space: nowrap;
    }
    .vt-widget .vt-art-author {
      font-size: 0.78rem; opacity: 0.6; overflow-wrap: anywhere;
    }
    .vt-widget .vt-art-paper {
      font-size: 0.78rem; opacity: 0.6; overflow-wrap: anywhere;
      justify-self: end; text-align: right;
    }

    .vt-widget .vt-art-body { margin-top: 8px; }
    .vt-widget .vt-sub { margin-bottom: 6px; }
    .vt-widget .vt-sub > span { display: block; font-size: 0.72rem; opacity: 0.55; }
    .vt-widget .vt-sub > div { white-space: pre-wrap; overflow-wrap: anywhere; }
    """

    items          = traitlets.List([]).tag(sync=True)
    width          = traitlets.Unicode("100%").tag(sync=True)
    groups         = traitlets.List([]).tag(sync=True)
    options        = traitlets.Dict({}).tag(sync=True)
    height         = traitlets.Unicode("500px").tag(sync=True)
    selected       = traitlets.List([]).tag(sync=True)
    emit_selection = traitlets.Bool(False).tag(sync=True)

months = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)'
date_pattern = r'\b(?:' \
    rf'\d{{1,2}}\s+{months}\s+\d{{4}}|' \
    rf'{months}\s+\d{{1,2}},?\s+\d{{4}}|' \
    r'(?:Early|Mid|Late)\s+\d{4}s?|' \
    rf'{months}\s+\d{{4}}' \
    r')\b'

def extract_date(text):
    """Extract the date string from text"""
    match = re.search(date_pattern, text, re.IGNORECASE)
    if match:
        return match.group(0)
    return None

def handle_ambiguous_dates(date_str):
    year = re.findall(r"(\d{4})", date_str)[0]
    if "Late" in date_str:
        year = int(year)+6
        new_date_str = f"1/1/{year}"
    elif "Early" in date_str:
        new_date_str = f"1/1/{year}"
    else:
        new_date_str = extract_date(date_str)
    return pd.to_datetime(new_date_str)

def handle_ambiguous_dates_end(date_str):
    year = re.findall(r"(\d{4})", date_str)[0]
    if "Late" in date_str:
        year = int(year)+6
        new_date_str = f"1/1/{year+3}"
        return pd.to_datetime(new_date_str) 
    elif "Early" in date_str:
        new_date_str = f"1/1/{int(year)+5}"
        return pd.to_datetime(new_date_str) 
    else:
        new_date_str = extract_date(date_str)
        return None


@st.cache_data
def load_data():
    timetable = TimeTable("Timetable-REV7 shortened-Hypotheses re press coverage of Hepatitis C in UK +color coding.docx", date_pattern)
    with open("tbs_results1020.json", "r") as json_file:
        results_by_date_key = json.load(json_file)

    events = pd.DataFrame.from_dict(timetable.grouped, orient="index").reset_index().rename(columns={"index":"timetable_entry", 0:"description"})
    topics = pd.DataFrame.from_dict({k:", ".join(v) for k,v in timetable.topics.items()}, orient="index").reset_index().rename(columns={"index":"timetable_entry", 0:"topics"})
    df = events.merge(topics, on="timetable_entry")# [:-19] # getting rid of extra data at the bottom...

    print(df)

    df["start"] = df["timetable_entry"].apply(lambda x: handle_ambiguous_dates(x.split("_")[0]))
    df["end"] = df["timetable_entry"].apply(lambda x: handle_ambiguous_dates_end(x.split("_")[0]))

    long_days = 5
    items = []
    for i, row in df.iterrows():
        if row["timetable_entry"] not in results_by_date_key:
            continue
        span = (row.end - row.start).days if row.end else 0
        item = {
            "id":i+1,
            "content":row["description"],
            "start":row["start"].strftime("%Y-%m-%dT%H:%M:%S"),
            "type": "range" if span >= long_days else "box",
            "detail": {
                "topics":row["topics"] if row["topics"] != "" else "No topic",
                "articles":results_by_date_key[row["timetable_entry"]] if results_by_date_key[row["timetable_entry"]] != "" else "No articles found for this event"
            }
        }
        if row["end"] is not pd.NaT and row["end"] is not None:
            item["end"] = row["end"].strftime("%Y-%m-%dT%H:%M:%S")
        if row.end and span >= long_days:
            item["end"] = row.end.isoformat()
        items.append(item)
    return items