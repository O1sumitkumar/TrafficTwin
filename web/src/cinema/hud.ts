// HTML heads-up display over the deck canvas: title card, caption, clock, KPIs counting, legend,
// split labels and the "synthetic demand, uncalibrated" footer. Updated synchronously per frame.
// No letter-spacing anywhere (house style).
import type { Frames, Manifest, ShotSpec } from "./types";
import { CLASS_COLORS, DIFF_STOPS, HEAT_STOPS, SPEED_STOPS, gradientCss } from "./palette";

const CSS = `
.cin-root { position: absolute; inset: 0; overflow: hidden; font-family: -apple-system, "SF Pro Text", "Helvetica Neue", Arial, sans-serif; color: #f2f4f8; letter-spacing: normal; }
.cin-root * { letter-spacing: normal; box-sizing: border-box; }
.cin-hud { position: absolute; left: 0; right: 0; pointer-events: none; }
.cin-grad-top { position: absolute; left: 0; right: 0; top: 0; height: calc(var(--u) * 230px); background: linear-gradient(to bottom, rgba(0,0,0,0.62), rgba(0,0,0,0)); }
.cin-grad-bot { position: absolute; left: 0; right: 0; bottom: 0; height: calc(var(--u) * 250px); background: linear-gradient(to top, rgba(0,0,0,0.7), rgba(0,0,0,0)); }
.cin-cap { position: absolute; left: calc(var(--u) * 56px); top: calc(var(--u) * 44px); max-width: 62%; }
.cin-film { font-size: calc(var(--u) * 17px); font-weight: 600; color: #e7b75f; }
.cin-caption { font-size: calc(var(--u) * 34px); font-weight: 650; line-height: 1.15; margin-top: calc(var(--u) * 6px); text-shadow: 0 2px 12px rgba(0,0,0,0.6); }
.cin-detail { font-size: calc(var(--u) * 19px); line-height: 1.35; margin-top: calc(var(--u) * 10px); color: #cfd6e2; max-width: calc(var(--u) * 1050px); text-shadow: 0 1px 8px rgba(0,0,0,0.7); }
.cin-clock { position: absolute; right: calc(var(--u) * 56px); top: calc(var(--u) * 38px); text-align: right; }
.cin-time { font-size: calc(var(--u) * 58px); font-weight: 300; font-variant-numeric: tabular-nums; line-height: 1; }
.cin-tier { font-size: calc(var(--u) * 16px); color: #aeb7c6; margin-top: calc(var(--u) * 8px); }
.cin-kpis { position: absolute; left: calc(var(--u) * 56px); bottom: calc(var(--u) * 70px); display: flex; gap: calc(var(--u) * 44px); }
.cin-kpi-v { font-size: calc(var(--u) * 44px); font-weight: 600; font-variant-numeric: tabular-nums; line-height: 1.05; }
.cin-kpi-u { font-size: calc(var(--u) * 20px); font-weight: 500; color: #cfd6e2; margin-left: calc(var(--u) * 6px); }
.cin-kpi-l { font-size: calc(var(--u) * 16px); color: #aeb7c6; margin-top: calc(var(--u) * 6px); }
.cin-legend { position: absolute; right: calc(var(--u) * 56px); bottom: calc(var(--u) * 72px); width: calc(var(--u) * 300px); font-size: calc(var(--u) * 15px); color: #cfd6e2; }
.cin-legend-t { margin-bottom: calc(var(--u) * 7px); color: #e8ecf2; font-weight: 600; }
.cin-bar { height: calc(var(--u) * 9px); border-radius: calc(var(--u) * 5px); }
.cin-ends { display: flex; justify-content: space-between; margin-top: calc(var(--u) * 5px); }
.cin-chips { display: flex; flex-wrap: wrap; gap: calc(var(--u) * 6px) calc(var(--u) * 14px); }
.cin-chip { display: flex; align-items: center; gap: calc(var(--u) * 6px); }
.cin-dot { width: calc(var(--u) * 10px); height: calc(var(--u) * 10px); border-radius: 50%; }
.cin-footer { position: absolute; left: 0; right: 0; bottom: calc(var(--u) * 22px); text-align: center; font-size: calc(var(--u) * 15px); color: #c3cad6; }
.cin-footer b { color: #f0c46a; font-weight: 600; }
.cin-title { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; background: radial-gradient(ellipse at center, rgba(5,8,14,0.55), rgba(5,8,14,0.85)); }
.cin-title-k { font-size: calc(var(--u) * 20px); color: #e7b75f; font-weight: 600; }
.cin-title-h { font-size: calc(var(--u) * 76px); font-weight: 700; margin-top: calc(var(--u) * 12px); text-align: center; line-height: 1.05; }
.cin-title-s { font-size: calc(var(--u) * 26px); color: #cfd6e2; margin-top: calc(var(--u) * 18px); text-align: center; }
.cin-title-f { font-size: calc(var(--u) * 17px); color: #f0c46a; margin-top: calc(var(--u) * 40px); }
.cin-split { position: absolute; top: calc(var(--u) * 150px); width: 50%; text-align: center; font-size: calc(var(--u) * 24px); font-weight: 600; text-shadow: 0 2px 10px rgba(0,0,0,0.8); }
.cin-divider { position: absolute; top: 0; bottom: 0; left: 50%; width: 2px; margin-left: -1px; background: rgba(240,244,250,0.7); }
.cin-fade { position: absolute; inset: 0; background: #000; }
.cin-bars { position: absolute; left: 0; right: 0; background: #000; }
`;

function el(tag: string, cls: string, parent: HTMLElement, text = ""): HTMLElement {
  const e = document.createElement(tag);
  e.className = cls;
  if (text) e.textContent = text;
  parent.appendChild(e);
  return e;
}

const TIER_TEXT: Record<string, string> = {
  A: "Tier A city, mesoscopic, 10 % population sample",
  B: "Tier B window, microscopic",
};

export class Hud {
  private m: Manifest;
  private fr: Frames;
  private root: HTMLElement;
  private cap: HTMLElement;
  private caption: HTMLElement;
  private detail: HTMLElement;
  private time: HTMLElement;
  private kpis: HTMLElement;
  private legend: HTMLElement;
  private title: HTMLElement;
  private fade: HTMLElement;
  private splitL: HTMLElement;
  private splitR: HTMLElement;
  private divider: HTMLElement;
  private shown = -1;
  private kpiEls: HTMLElement[] = [];

  constructor(parent: HTMLElement, m: Manifest, fr: Frames, area: { top: number; height: number }) {
    this.m = m;
    this.fr = fr;
    const style = document.createElement("style");
    style.textContent = CSS;
    document.head.appendChild(style);
    this.root = el("div", "cin-root", parent);
    this.root.style.setProperty("--u", String(m.height / 1080));
    const hud = el("div", "cin-hud", this.root);
    hud.style.top = `${area.top}px`;
    hud.style.height = `${area.height}px`;
    el("div", "cin-grad-top", hud);
    el("div", "cin-grad-bot", hud);
    this.divider = el("div", "cin-divider", hud);
    this.splitL = el("div", "cin-split", hud);
    this.splitL.style.left = "0";
    this.splitR = el("div", "cin-split", hud);
    this.splitR.style.left = "50%";
    this.cap = el("div", "cin-cap", hud);
    el("div", "cin-film", this.cap, m.title);
    this.caption = el("div", "cin-caption", this.cap);
    this.detail = el("div", "cin-detail", this.cap);
    const clock = el("div", "cin-clock", hud);
    this.time = el("div", "cin-time", clock);
    el("div", "cin-tier", clock, TIER_TEXT[m.tier] ?? "");
    this.kpis = el("div", "cin-kpis", hud);
    this.legend = el("div", "cin-legend", hud);
    const footer = el("div", "cin-footer", hud);
    footer.innerHTML = `TrafficTwin Jeddah &middot; <b>${m.label}</b> &middot; map data &copy; OpenStreetMap contributors (ODbL) &middot; simulated with Eclipse SUMO`;
    this.title = el("div", "cin-title", this.root);
    this.title.style.top = `${area.top}px`;
    this.title.style.height = `${area.height}px`;
    this.title.style.bottom = "auto";
    el("div", "cin-title-k", this.title, "TrafficTwin Jeddah");
    el("div", "cin-title-h", this.title, m.title);
    el("div", "cin-title-s", this.title, m.subtitle);
    el("div", "cin-title-f", this.title, m.label);
    if (m.letterbox) {
      const bar = (top: boolean) => {
        const b = el("div", "cin-bars", this.root);
        b.style.height = `${area.top}px`;
        if (top) b.style.top = "0";
        else b.style.bottom = "0";
      };
      bar(true);
      bar(false);
    }
    this.fade = el("div", "cin-fade", this.root);
  }

  private setShot(shot: ShotSpec): void {
    this.caption.textContent = shot.hud.caption;
    this.detail.textContent = shot.hud.detail;
    this.kpis.replaceChildren();
    this.kpiEls = shot.hud.kpis.map((k) => {
      const box = el("div", "cin-kpi", this.kpis);
      const v = el("div", "cin-kpi-v", box);
      el("div", "cin-kpi-l", box, k.label);
      return v;
    });
    const split = shot.layers.mode === "split" && shot.hud.split_labels;
    this.divider.style.display = shot.layers.mode === "split" ? "block" : "none";
    this.splitL.textContent = split ? shot.hud.split_labels![0] : "";
    this.splitR.textContent = split ? shot.hud.split_labels![1] : "";
    this.legend.replaceChildren();
    const kind = shot.hud.legend;
    if (kind === "none") return;
    if (kind === "class") {
      el("div", "cin-legend-t", this.legend, "Vehicles");
      const chips = el("div", "cin-chips", this.legend);
      this.m.vehicle_classes.forEach((c, i) => {
        if (c === "convoy" || c === "evacuee") {
          if (!shot.hud.caption.toLowerCase().includes(c === "convoy" ? "motorcade" : "evac")) return;
        }
        const chip = el("div", "cin-chip", chips);
        const dot = el("span", "cin-dot", chip);
        dot.style.background = `rgb(${CLASS_COLORS[i]!.join(",")})`;
        el("span", "", chip, c);
      });
      return;
    }
    const diff = kind === "diff";
    const tripsOnly = kind === "speed" && !shot.layers.heat && shot.layers.trips;
    el("div", "cin-legend-t", this.legend, diff ? "Change in speed vs comparison" : tripsOnly ? "Vehicle speed" : "Road speed / limit");
    const bar = el("div", "cin-bar", this.legend);
    bar.style.background = gradientCss(diff ? DIFF_STOPS : tripsOnly ? SPEED_STOPS : HEAT_STOPS);
    const ends = el("div", "cin-ends", this.legend);
    el("span", "", ends, diff ? "worse" : tripsOnly ? "stopped" : "congested");
    el("span", "", ends, diff ? "relief" : tripsOnly ? "fast" : "free flow");
  }

  update(i: number): void {
    const f = this.m.shots;
    const fr = this.fr;
    const s = fr.shot[i]!;
    if (s !== this.shown) {
      this.setShot(f[s]!);
      this.shown = s;
    }
    const shot = f[s]!;
    this.cap.style.opacity = String(fr.caption_alpha[i]);
    this.time.textContent = fr.clock[i]!;
    const vals = fr.kpi[i] ?? [];
    shot.hud.kpis.forEach((k, j) => {
      const v = vals[j];
      const e = this.kpiEls[j]!;
      if (v === null || v === undefined) {
        e.textContent = "-";
        return;
      }
      const sign = k.sign && v > 0 ? "+" : "";
      const txt = `${sign}${v.toLocaleString("en-US", { minimumFractionDigits: k.decimals, maximumFractionDigits: k.decimals })}`;
      e.replaceChildren(document.createTextNode(txt));
      if (k.unit) el("span", "cin-kpi-u", e, k.unit);
    });
    this.title.style.opacity = String(fr.title_alpha[i]);
    this.title.style.display = fr.title_alpha[i]! > 0 ? "flex" : "none";
    this.fade.style.opacity = String(fr.fade[i]);
  }
}
