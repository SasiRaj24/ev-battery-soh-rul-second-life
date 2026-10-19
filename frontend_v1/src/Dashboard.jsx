import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { getFolds, getHealth, getPredictions, getSummary } from "./api.js";

const BATTERIES = ["B0005", "B0006", "B0007", "B0018"];
const MODELS = [
  ["persistence", "Persistence"],
  ["linear_regression", "Linear regression"],
  ["xgboost", "XGBoost"],
];
const colors = { actual: "#eef4f3", predicted: "#57d3b0" };
const n = (value, digits = 3) => Number(value).toFixed(digits);

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [folds, setFolds] = useState([]);
  const [health, setHealth] = useState(null);
  const [battery, setBattery] = useState("B0005");
  const [model, setModel] = useState("persistence");
  const [points, setPoints] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getSummary(), getFolds(), getHealth()])
      .then(([s, f, h]) => { setSummary(s); setFolds(f); setHealth(h); })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    getPredictions(battery, model).then(setPoints).catch((e) => setError(e.message));
  }, [battery, model]);

  const pooled = summary?.pooled_metrics || {};
  const chartData = useMemo(() => points.map((p) => ({
    cycle: p.target_cycle_number,
    actual: p.target_soh_percent,
    predicted: p.predicted_soh_percent,
  })), [points]);
  const foldData = folds.filter((f) => f.model === "persistence");
  const selected = pooled[model];

  return <div className="shell">
    <aside className="rail">
      <div className="brand"><span className="brand-mark">C</span><span>CELL<span className="mint">SCOPE</span></span></div>
      <div className="rail-caption">RESEARCH WORKSPACE</div>
      <div className="nav active"><span className="nav-icon">◫</span>Validation</div>
      <div className="nav"><span className="nav-icon">⌁</span>Cell profiles</div>
      <div className="rail-bottom"><span className="dot"></span>Local research instance<br /><small>NASA cell study · v1</small></div>
    </aside>

    <main className="main">
      <header className="topbar">
        <div className="crumb">EV BATTERY AI <span>/</span> RESEARCH VALIDATION</div>
        <div className="status"><i className={health?.validation_data_available ? "dot" : "dot muted"}></i>{health?.validation_data_available ? "ARTIFACTS AVAILABLE" : "CONNECTING"}</div>
      </header>
      <section className="intro">
        <div><div className="eyebrow">CROSS-BATTERY STUDY <span>•</span> NASA PCOE</div>
          <h1>Cell-level validation</h1>
          <p>Leave-one-battery-out prediction of next-discharge state of health.</p>
        </div>
        <div className="study-tag"><span className="tag-label">COHORT</span><strong>B0005 · B0006 · B0007 · B0018</strong></div>
      </section>

      {error && <div className="error">API unavailable — {error}. Start the research API from <code>backend/app_v1/README.md</code>.</div>}
      <section className="metrics-row">
        <Metric label="BEST POOLED MAE" value={pooled.persistence ? n(pooled.persistence.mae_soh_percentage_points, 4) : "—"} unit="SOH pts" note="Persistence baseline" accent />
        <Metric label="LINEAR REGRESSION" value={pooled.linear_regression ? n(pooled.linear_regression.mae_soh_percentage_points, 4) : "—"} unit="SOH pts" note="Pooled leave-one-cell-out" />
        <Metric label="XGBOOST" value={pooled.xgboost ? n(pooled.xgboost.mae_soh_percentage_points, 4) : "—"} unit="SOH pts" note="Pooled leave-one-cell-out" />
        <Metric label="HELD-OUT CELLS" value="04" unit="batteries" note="Each cell held out once" />
      </section>

      <section className="content-grid">
        <article className="panel chart-panel">
          <div className="panel-head"><div><div className="eyebrow">HELD-OUT PREDICTIONS</div><h2>Measured vs predicted SOH</h2></div>
            <div className="selectors">
              <label><span>BATTERY</span><select value={battery} onChange={(e) => setBattery(e.target.value)}>{BATTERIES.map((b) => <option key={b}>{b}</option>)}</select></label>
              <label><span>MODEL</span><select value={model} onChange={(e) => setModel(e.target.value)}>{MODELS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            </div>
          </div>
          <div className="chart-legend"><span><i className="legend-line actual-line"></i>Measured target SOH</span><span><i className="legend-line predicted-line"></i>{model.replaceAll("_", " ")} prediction</span></div>
          <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><LineChart data={chartData} margin={{ top: 14, right: 18, left: 0, bottom: 10 }}>
            <CartesianGrid stroke="#25343d" strokeDasharray="3 5" vertical={false} />
            <XAxis dataKey="cycle" tick={{ fill: "#83929a", fontSize: 11 }} axisLine={{ stroke: "#34434c" }} tickLine={false} label={{ value: "Target discharge record", position: "insideBottom", offset: -2, fill: "#83929a", fontSize: 11 }} />
            <YAxis domain={([min, max]) => [Math.floor(min - 1), Math.ceil(max + 1)]} tick={{ fill: "#83929a", fontSize: 11 }} axisLine={false} tickLine={false} width={48} />
            <Tooltip contentStyle={{ background: "#17252d", border: "1px solid #34434c", borderRadius: 8, color: "#eef4f3" }} labelStyle={{ color: "#9baab0" }} />
            <Legend content={() => null} />
            <Line type="monotone" dataKey="actual" name="Measured" stroke={colors.actual} strokeWidth={2.2} dot={false} activeDot={{ r: 4 }} />
            <Line type="monotone" dataKey="predicted" name="Predicted" stroke={colors.predicted} strokeWidth={2} dot={false} activeDot={{ r: 4 }} strokeDasharray={model === "persistence" ? "5 4" : undefined} />
          </LineChart></ResponsiveContainer></div>
          <div className="chart-foot">MAE for selected model · {selected ? `${n(selected.mae_soh_percentage_points, 4)} SOH percentage points` : "—"}</div>
        </article>

        <article className="panel folds-panel"><div className="panel-head"><div><div className="eyebrow">GENERALIZATION CHECK</div><h2>Persistence by held-out cell</h2></div><span className="unit-badge">MAE · SOH PTS</span></div>
          <div className="fold-list">{foldData.map((f) => <div className="fold" key={f.held_out_battery}><div className="fold-label"><strong>{f.held_out_battery}</strong><span>{f.testing_rows} predictions</span></div><div className="bar-track"><div className="bar" style={{ width: `${Math.min(100, f.mae_soh_percentage_points / 1.2 * 100)}%` }} /></div><strong className="fold-score">{n(f.mae_soh_percentage_points, 3)}</strong></div>)}</div>
          <div className="mini-note">Each bar is a separate unseen cell. Errors vary across the four folds.</div>
        </article>
      </section>

      <section className="bottom-grid">
        <article className="panel definition"><div className="eyebrow">TARGET DEFINITION</div><h2>Next-discharge relative SOH</h2><p>Discharge capacity relative to each cell’s first valid discharge. Current-discharge measurements predict the next recorded discharge.</p><div className="formula">SOH = capacity <span>/</span> first capacity <span>×</span> 100</div></article>
        <article className="panel caution"><div className="caution-mark">!</div><div><div className="eyebrow">STUDY SCOPE</div><h2>Laboratory cells, not EV packs</h2><p>NASA accelerated-aging cells only. Cutoff voltages differ among cells; this does not establish real-world vehicle or pack performance.</p></div></article>
      </section>
      <footer>EV BATTERY AI <span>·</span> NASA PCOE CELL STUDY <span>·</span> RESULTS FROM LOCAL VALIDATION ARTIFACTS</footer>
    </main>
  </div>;
}

function Metric({ label, value, unit, note, accent }) {
  return <article className={`metric ${accent ? "metric-accent" : ""}`}><div className="metric-label">{label}</div><div className="metric-value">{value}<small>{unit}</small></div><div className="metric-note">{note}</div></article>;
}
