import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { analyzeCsv, analyzeParameters, analyzeCollectiveParameters, getDatasetCatalog, getModelManifest, getResearchEvaluation, getRulValidation, getSohValidation } from "./api.js";
import { readLearningLog, writeLearningLog } from "./learningStore.js";

const fmt = (x, digits = 2) => Number(x).toFixed(digits);
const LearningLog = lazy(() => import("./LearningLog.jsx"));
const SoHHistoryChart = lazy(() => import("./SoHHistoryChart.jsx"));

export default function Dashboard() {
  const [soh, setSoh] = useState(null);
  const [rul, setRul] = useState(null);
  const [researchEvaluation, setResearchEvaluation] = useState(null);
  const [datasets, setDatasets] = useState(null);
  const [modelManifest, setModelManifest] = useState(null);
  const [file, setFile] = useState(null);
  const [parameters, setParameters] = useState({
    reference_capacity_Ah: "", previous_cycle_number: "", previous_capacity_Ah: "",
    current_cycle_number: "", current_capacity_Ah: "", ambient_temperature_C: "",
    forecast_cycle_number: "", dataset_source: "NASA",
  });
  const [analysis, setAnalysis] = useState(null);
  const [analysisContext, setAnalysisContext] = useState(null);
  const [learningState, setLearningState] = useState(() => readLearningLog());
  const [savedPredictionId, setSavedPredictionId] = useState(null);
  const [saveError, setSaveError] = useState("");
  const [tracking, setTracking] = useState({ cell_id: "", provenance: "", test_conditions: "" });
  const [busy, setBusy] = useState(false);
  const [rulScopeConfirmed, setRulScopeConfirmed] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("overview");

  useEffect(() => {
    Promise.all([getSohValidation(), getRulValidation(), getDatasetCatalog(), getModelManifest()])
      .then(([s, r, d, m]) => { setSoh(s); setRul(r); setDatasets(d); setModelManifest(m); })
      .catch((e) => setError(`Could not load project results: ${e.message}`));
    getResearchEvaluation().then(setResearchEvaluation).catch(() => {});
  }, []);

  const bestRul = rul?.pooled_metrics_cycles?.xgboost;
  const eolCells = useMemo(() => Object.entries(rul?.battery_status || {}), [rul]);

  function updateLearningRecords(records) {
    if (learningState.error) return false;
    try {
      writeLearningLog(records);
      setLearningState({ records, error: "" });
      return true;
    } catch {
      setLearningState((old) => ({ ...old, error: "The browser could not save this entry (storage may be full or disabled). Existing records remain untouched." }));
      return false;
    }
  }

  function savePrediction() {
    if (!analysis || !analysisContext) return false;
    const logMetadata = analysisContext.tracking;
    if (!logMetadata.cell_id.trim() || !logMetadata.provenance.trim()) {
      setSaveError("Enter the cell ID and measurement provenance, then run the analysis again so those details are captured with its inputs.");
      return false;
    }
    const predictionValue = analysis.next_discharge_soh?.predicted_soh_percent;
    if (!Number.isFinite(predictionValue)) {
      setSaveError("This model withheld its SOH estimate, so there is no numerical prediction to score.");
      return false;
    }
    const id = globalThis.crypto?.randomUUID?.() || `prediction-${Date.now()}`;
    const predictedPoint = (analysis.history_chart || []).find((point) => point.predicted_next_soh_percent != null);
    const record = {
      id,
      created_at: new Date().toISOString(),
      cell_id: logMetadata.cell_id.trim(),
      dataset_source: analysis.dataset_source || analysisContext.dataset_source,
      measurement_provenance: logMetadata.provenance.trim(),
      test_conditions: logMetadata.test_conditions.trim(),
      model_release: analysis.model_release || modelManifest?.model_version || "unknown",
      model_version: analysis.model_version || "unknown",
      model_name: analysis.model_name || analysis.next_discharge_soh?.explanation?.model || "unknown",
      input_mode: analysis.input_mode || "manual_parameters",
      inputs: analysisContext.inputs,
      prediction: {
        soh_percent: predictionValue,
        target_cycle_number: analysis.forecast_cycle_number ?? predictedPoint?.cycle ?? (analysis.current_cycle_number + 1),
        current_cycle_number: analysis.current_cycle_number,
        rul_cycles: analysis.remaining_useful_life?.estimated_remaining_discharge_cycles ?? null,
        rul_endpoint: analysis.remaining_useful_life?.eol_definition || null,
        second_life_screening: analysis.second_life_screening?.code || null,
      },
      follow_ups: [],
      second_life_assessments: [],
    };
    const next = [record, ...learningState.records];
    if (!updateLearningRecords(next)) {
      setSaveError(learningState.error || "The learning log could not be saved.");
      return false;
    }
    setSavedPredictionId(id);
    setSaveError("");
    return true;
  }

  async function submit(event) {
    event.preventDefault();
    if (!file) return;
    setBusy(true); setError(""); setAnalysis(null); setAnalysisContext(null); setSavedPredictionId(null); setSaveError("");
    try { setAnalysis(await analyzeCsv(await file.text(), rulScopeConfirmed)); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function submitParameters(event) {
    event.preventDefault();
    setBusy(true); setError(""); setAnalysis(null); setAnalysisContext(null); setSavedPredictionId(null); setSaveError("");
    try {
      const values = Object.fromEntries(Object.entries(parameters).map(([key, value]) => [key, Number(value)]));
      const payload = {...values, dataset_source: parameters.dataset_source, compatible_with_nasa_rul_scope: rulScopeConfirmed};
      if (parameters.dataset_source !== "NASA") delete payload.ambient_temperature_C;
      if (!parameters.forecast_cycle_number) delete payload.forecast_cycle_number;
      const result = await analyzeParameters(payload);
      setAnalysis(result);
      setAnalysisContext({ dataset_source: parameters.dataset_source, inputs: payload, tracking: { ...tracking } });
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><b className="brand-symbol"><span/></b><span>EV BATTERY<br/><i>HEALTH &amp; LIFE AI</i></span></div>
      <div className="side-label">PROJECT WORKSPACE</div>
      <button className={`nav-item ${tab === "overview" ? "selected" : ""}`} onClick={() => setTab("overview")}><span>◫</span> Health &amp; life overview</button>
      <button className={`nav-item ${tab === "datasets" ? "selected" : ""}`} onClick={() => setTab("datasets")}><span>▦</span> Research datasets</button>
      <button className={`nav-item ${tab === "analyze" ? "selected" : ""}`} onClick={() => setTab("analyze")}><span>⌁</span> Analyze a battery</button>
      <button className={`nav-item ${tab === "collective" ? "selected" : ""}`} onClick={() => setTab("collective")}><span>◉</span> Collective assessment</button>
      <button className={`nav-item ${tab === "learning" ? "selected" : ""}`} onClick={() => setTab("learning")}><span>↻</span> Prediction log</button>
      <div className="sidebar-bottom"><span className="pulse"/>RESEARCH PROTOTYPE<br/><small>Model release · {modelManifest?.model_version || "loading"}</small></div>
    </aside>
    <main className="main-area">
      <header className="header"><div className="breadcrumb">EV BATTERY PROJECT <span>/</span> SOH · RUL · SECOND LIFE</div><div className="version-chip">MODEL RELEASE <b>{modelManifest?.model_version || "loading"}</b></div></header>
      <section className="hero"><div className="hero-copy"><div className="kicker">AI-BASED BATTERY CONDITION &amp; LIFETIME</div><h1>AI-Based State of Health and Remaining Useful Life Prediction for EV Batteries</h1><div className="title-extension">WITH <b>SECOND-LIFE RECOMMENDATION</b></div><p>Cell-level research insights for battery health, useful life, and reuse screening.</p><div className="project-flow"><span><b>01</b> State of Health</span><i/><span><b>02</b> Remaining Life</span><i/><span><b>03</b> Second Life</span></div></div><div className="cohort"><div className="research-tag"><span className="pulse"/>LAB-CELL RESEARCH</div><small>CURRENT COMPARISON COHORT</small><div className="dataset-pills"><span>NASA</span><span>OXFORD</span><span>CALCE CS2</span></div><b>26 independent cells</b><small>Across available scored cohorts</small><div className="cohort-scope">EV pack and field validation not established</div></div></section>
      <div className="tabs"><button className={tab === "overview" ? "tab-active" : ""} onClick={() => setTab("overview")}>Health &amp; life overview</button><button className={tab === "datasets" ? "tab-active" : ""} onClick={() => setTab("datasets")}>Research datasets</button><button className={tab === "analyze" ? "tab-active" : ""} onClick={() => setTab("analyze")}>Analyze a battery</button><button className={tab === "collective" ? "tab-active" : ""} onClick={() => setTab("collective")}>Collective assessment</button><button className={tab === "learning" ? "tab-active" : ""} onClick={() => setTab("learning")}>Prediction log</button></div>
      {error && <div className="error-box">{error}</div>}
      {tab === "overview" ? <Overview soh={soh} rul={rul} research={researchEvaluation} eolCells={eolCells}/> : tab === "datasets" ? <DatasetSources data={datasets}/> : tab === "collective" ? <CollectiveAnalysis/> : tab === "learning" ? <Suspense fallback={<section className="panel dataset-loading">Loading prediction log…</section>}><LearningLog records={learningState.records} storageError={learningState.error} onChange={updateLearningRecords}/></Suspense> : <>
        <section className="panel tracking-panel"><div className="kicker">OPTIONAL PREDICTION TRACEABILITY</div><h2>Identify the cell for follow-up</h2><p>Enter these before analysis if you may save its prediction. Details are stored in this browser and are not sent to the analysis API.</p><div className="tracking-grid"><label>Cell ID<input value={tracking.cell_id} onChange={(e)=>setTracking({...tracking,cell_id:e.target.value})} placeholder="e.g. B0005"/></label><label>Measurement provenance<input value={tracking.provenance} onChange={(e)=>setTracking({...tracking,provenance:e.target.value})} placeholder="Dataset file, sheet/record, protocol or instrument"/></label><label className="tracking-wide">Test conditions / notes <span>(optional)</span><textarea value={tracking.test_conditions} onChange={(e)=>setTracking({...tracking,test_conditions:e.target.value})} placeholder="Chemistry, temperature, charge/discharge rates, equipment, or other protocol details"/></label></div></section>
        <section className="panel parameter-panel">
          <div className="kicker">MANUAL BATTERY INPUT</div><h2>Enter measured parameters</h2>
          <p>Select the laboratory dataset family that best matches the cell and measurement protocol. The app routes SOH to that family’s model; these remain research estimates.</p>
          <form onSubmit={submitParameters} className="parameter-form">
            <label>Reference dataset<select required value={parameters.dataset_source} onChange={(e)=>{setParameters({...parameters,dataset_source:e.target.value});setRulScopeConfirmed(false);}}><option value="NASA">NASA PCoE cells</option><option value="Oxford">Oxford cells</option><option value="CALCE_CS2">CALCE CS2 cells</option></select></label>
            <div className="upload-note">{parameters.dataset_source === "NASA" ? "Uses the existing NASA-trained SOH and RUL models." : parameters.dataset_source === "Oxford" ? "Uses an Oxford-specific SOH model (8-cell leave-one-cell-out validation). RUL is withheld." : "Uses a CALCE CS2-specific SOH model (6-cell validation); it was effectively tied with persistence. RUL is withheld."}</div>
            <label>SOH reference capacity <span>(Ah)</span><input required type="number" min="0.0001" step="any" value={parameters.reference_capacity_Ah} onChange={(e)=>setParameters({...parameters,reference_capacity_Ah:e.target.value})} placeholder="e.g. 2.0"/></label>
            <label>Previous cycle number<input required type="number" min={parameters.dataset_source === "Oxford" ? "0" : "1"} step="1" value={parameters.previous_cycle_number} onChange={(e)=>setParameters({...parameters,previous_cycle_number:e.target.value})} placeholder={parameters.dataset_source === "Oxford" ? "e.g. 0 or 100" : "e.g. 100"}/></label>
            <label>Previous discharge capacity <span>(Ah)</span><input required type="number" min="0.0001" step="any" value={parameters.previous_capacity_Ah} onChange={(e)=>setParameters({...parameters,previous_capacity_Ah:e.target.value})} placeholder="e.g. 1.82"/></label>
            <label>Current cycle number<input required type="number" min={parameters.dataset_source === "NASA" ? "2" : "1"} step="1" value={parameters.current_cycle_number} onChange={(e)=>setParameters({...parameters,current_cycle_number:e.target.value})} placeholder={parameters.dataset_source === "Oxford" ? "e.g. 100" : "e.g. 101"}/></label>
            <label>Current discharge capacity <span>(Ah)</span><input required type="number" min="0.0001" step="any" value={parameters.current_capacity_Ah} onChange={(e)=>setParameters({...parameters,current_capacity_Ah:e.target.value})} placeholder="e.g. 1.81"/></label>
            {parameters.dataset_source === "Oxford" && <label>Next scheduled measurement cycle<input required type="number" min="3" step="1" value={parameters.forecast_cycle_number} onChange={(e)=>setParameters({...parameters,forecast_cycle_number:e.target.value})} placeholder="e.g. 300 for 200 → 300"/></label>}
            {parameters.dataset_source === "NASA" && <label>Ambient temperature <span>(°C)</span><input required type="number" min="-80" max="150" step="any" value={parameters.ambient_temperature_C} onChange={(e)=>setParameters({...parameters,ambient_temperature_C:e.target.value})} placeholder="e.g. 24"/></label>}
            {parameters.dataset_source === "NASA" && <label className="scope-confirm"><input type="checkbox" checked={rulScopeConfirmed} onChange={(e)=>setRulScopeConfirmed(e.target.checked)}/><span>I confirm this is a single cell under conditions compatible with the NASA model and uses its 1.4 Ah RUL endpoint. Otherwise RUL will be withheld.</span></label>}
            <button className="primary-button" disabled={busy}>{busy ? "Analyzing…" : "Analyze parameters →"}</button>
          </form>
          <div className="upload-note">Use measurements from a compatible cell and test protocol. The reference capacity must come from an actual baseline measurement; entering numbers does not make them measured data. RUL and second-life outputs are experimental screening estimates, not pack or safety validation.</div>
        </section>
        <details className="panel optional-upload"><summary>Prefer a history file? CSV upload is still available</summary>
          <div className="upload-panel"><div><div className="kicker">OPTIONAL CSV HISTORY</div><h2>Analyze a cell trajectory</h2><p>CSV columns: cycle_number, discharge_capacity_Ah, ambient_temperature_C.</p></div>
            <form onSubmit={submit} className="upload-form"><label className="file-picker"><input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] || null)}/><span className="file-button">Choose CSV</span><span className="file-name">{file ? file.name : "No file selected"}</span></label><button className="primary-button" disabled={!file || busy}>{busy ? "Analyzing…" : "Analyze CSV →"}</button></form>
            <label className="scope-confirm csv-scope-confirm"><input type="checkbox" checked={rulScopeConfirmed} onChange={(e)=>setRulScopeConfirmed(e.target.checked)}/><span>Confirm NASA-compatible single-cell protocol and the same 1.4 Ah RUL endpoint to enable RUL estimate.</span></label>
            <div className="upload-note">Files are analyzed locally and are not added to the training set.</div>
          </div>
        </details>
        {analysis && <><AnalysisResult result={analysis}/>{analysisContext && <section className="panel save-prediction-panel"><div><div className="kicker">PRESERVE THIS MODEL OUTPUT</div><h2>Save prediction for later comparison</h2><p>SOH is scored only when the measured follow-up matches the predicted target cycle. This save does not retrain or change the active model.</p>{saveError && <div className="error-box">{saveError}</div>}</div><button className="primary-button" disabled={Boolean(savedPredictionId) || Boolean(learningState.error)} onClick={savePrediction}>{savedPredictionId ? "Prediction saved ✓" : "Save prediction to log →"}</button></section>}</>}
      </>}
      <footer>SOH <span>·</span> RUL <span>·</span> SECOND-LIFE SCREENING <span>·</span> LAB-CELL RESEARCH <span>·</span> NOT EV PACK VALIDATION</footer>
    </main>
  </div>;
}

function CollectiveAnalysis() {
  const [values, setValues] = useState({reference_capacity_Ah:"",previous_cycle_number:"",previous_capacity_Ah:"",current_cycle_number:"",current_capacity_Ah:"",forecast_cycle_number:""});
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (key, value) => setValues((old) => ({...old, [key]: value}));
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError(""); setResult(null);
    try {
      const payload = Object.fromEntries(Object.entries(values).filter(([,v])=>v !== "").map(([k,v])=>[k,Number(v)]));
      setResult(await analyzeCollectiveParameters(payload));
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <section className="collective-page">
    <article className="panel dataset-intro"><div className="kicker">MULTI-DATASET BATTERY CONDITION</div><h2>Collective evidence assessment</h2><p>Enter two measured discharge checkpoints and a beginning-of-life reference capacity. This view uses findings from NASA, Oxford, and CALCE together to contextualize a capacity-based condition estimate and second-life pre-screen.</p><div className="dataset-notice"><b>Scientific limitation:</b> validation found negative transfer when pooling across families, especially Oxford. This tab therefore does not blend incompatible model predictions: it computes measured relative SOH, uses a clearly marked two-point trend baseline, and displays the measured cross-dataset comparison evidence below.</div></article>
    <section className="panel parameter-panel"><div className="kicker">TYPE BATTERY MEASUREMENTS</div><h2>Cell capacity history</h2><form className="parameter-form" onSubmit={submit}>
      <label>Reference capacity <span>(Ah, initial measured)</span><input required min="0.0001" step="any" type="number" value={values.reference_capacity_Ah} onChange={e=>set("reference_capacity_Ah",e.target.value)} placeholder="e.g. 2.0"/></label>
      <label>Previous cycle<input required min="0" step="1" type="number" value={values.previous_cycle_number} onChange={e=>set("previous_cycle_number",e.target.value)} placeholder="e.g. 100"/></label>
      <label>Previous discharge capacity <span>(Ah)</span><input required min="0.0001" step="any" type="number" value={values.previous_capacity_Ah} onChange={e=>set("previous_capacity_Ah",e.target.value)} placeholder="e.g. 1.82"/></label>
      <label>Current cycle<input required min="1" step="1" type="number" value={values.current_cycle_number} onChange={e=>set("current_cycle_number",e.target.value)} placeholder="e.g. 120"/></label>
      <label>Current discharge capacity <span>(Ah)</span><input required min="0.0001" step="any" type="number" value={values.current_capacity_Ah} onChange={e=>set("current_capacity_Ah",e.target.value)} placeholder="e.g. 1.80"/></label>
      <label>Forecast checkpoint cycle <span>(optional)</span><input min="2" step="1" type="number" value={values.forecast_cycle_number} onChange={e=>set("forecast_cycle_number",e.target.value)} placeholder="defaults to same interval"/></label>
      <button className="primary-button" disabled={busy}>{busy ? "Assessing…" : "Assess condition →"}</button>
    </form><div className="upload-note">Relative SOH is calculated as current capacity ÷ reference capacity. Forecast uses a straight-line extension of only the two latest measurements; it is not a validated AI forecast. RUL is not provided in collective mode.</div></section>
    {error && <div className="error-box">{error}</div>}
    {result && <div className="analysis-stack">
      <section className="result-cards"><Metric label="CURRENT RELATIVE SOH" value={fmt(result.relative_soh_percent,2)} unit="%" note="Calculated from typed capacity values"/><Metric label="NEXT CHECKPOINT BASELINE" value={fmt(result.predicted_next_soh_percent,2)} unit="% SOH" note={`Cycle ${result.forecast_cycle_number} · linear two-point extrapolation`}/><Metric label="RUL" value="Withheld" note="Collective cross-dataset evidence does not support a reliable shared RUL estimate" accent/></section>
      <section className="analysis-grid"><article className="panel recommendation-panel"><div className="kicker">CAPACITY-ONLY SECOND-LIFE PRE-SCREEN</div><h2>{result.second_life_screening.category}</h2><p>{result.second_life_screening.rationale} These cutoffs are project assumptions.</p><div className="confidence-pill">LOW CONFIDENCE · ENGINEERING REVIEW REQUIRED</div><p className="red-line">This is not a reuse application approval, safety decision, or certification. No EV pack or field validation is established.</p></article><article className="panel"><div className="kicker">MEASURED LEAVE-ONE-CELL-OUT EVIDENCE</div><h2>Why collective predictions are cautious</h2><div className="collective-evidence">{result.dataset_evidence.map(x=><div key={x.family}><b>{x.family}</b><span>Collective: {fmt(x.collective_model_mae_soh_pp,3)} SOH pp</span><span>{x.within_family_model_mae_soh_pp == null ? `Persistence: ${fmt(x.persistence_mae_soh_pp,3)} pp` : `Within-family: ${fmt(x.within_family_model_mae_soh_pp,3)} pp`}</span><small>{x.interpretation}</small></div>)}</div></article></section>
      <article className="panel collective-scope"><div className="kicker">SCOPE</div><p>{result.scope}</p><p>{result.validation_context}</p></article>
    </div>}
  </section>;
}

function DatasetSources({ data }) {
  if (!data) return <section className="panel dataset-loading">Loading local dataset catalog…</section>;
  const oxfordSoh = data.oxford?.soh_pooled_macro_cell_metrics || {};
  const oxfordRul = data.oxford?.rul_pooled_macro_cell_metrics?.xgboost;
  const countStatuses = (statusMap, status) => Object.values(statusMap || {}).filter((x) => x.status === status).length;
  return <section className="dataset-page">
    <article className="panel dataset-intro"><div className="kicker">LOCAL DATA INVENTORY</div><h2>Battery sources in this project</h2><p>Source files are kept in their original folders. In Analyze, NASA, Oxford, and six quality-screened CALCE CS2 cells route to separate SOH models; RUL remains NASA-specific.</p><div className="dataset-notice"><b>Inference model status:</b> source-specific SOH models are experimental. CALCE CS2 performance was effectively tied with persistence in six-cell validation; none of these laboratory-cell results establishes pack validation.</div></article>
    <div className="dataset-grid">
      <article className="panel dataset-card"><div className="dataset-card-head"><div><div className="kicker">NASA PCoE</div><h3>Battery MAT collection</h3></div><span className="dataset-status status-pending">QUALITY REVIEW</span></div><div className="dataset-count">{data.nasa?.processed_cells || 0}<small> cells parsed</small></div><p className="dataset-note">A pooled score is withheld: the collection mixes test protocols and several cells have implausible first-capacity baselines. Two four-cell groups have separate exploratory next-record SOH results below; neither supplies an RUL score.</p><div className="dataset-stats">{Object.entries(data.nasa?.cohort_specific_exploratory_next_record_soh || {}).map(([cohort, scores])=><div key={cohort}><span>{cohort} · LOBO MAE (persistence / linear / XGBoost)</span><b>{fmt(scores.persistence,2)} / {fmt(scores.linear_regression,2)} / {fmt(scores.xgboost,2)} pp</b></div>)}</div><p className="dataset-note">These are measured exploratory cell-held-out results within the listed cohorts only. Other NASA files remain inventoried pending protocol-specific baseline review; no broad-cohort validation is claimed.</p></article>
      <article className="panel dataset-card"><div className="dataset-card-head"><div><div className="kicker">OXFORD BATTERY DEGRADATION DATASET 1</div><h3>Characterization checkpoints</h3></div><span className="dataset-status status-pending">EXPLORATORY</span></div><div className="dataset-count">{data.oxford?.processed_cells || 0}<small> cells parsed</small></div><div className="dataset-stats"><div><span>Next-checkpoint SOH · persistence</span><b>{fmt(oxfordSoh.persistence?.macro_cell_mae, 3)} pp</b></div><div><span>Next-checkpoint SOH · linear</span><b>{fmt(oxfordSoh.linear_regression?.macro_cell_mae, 3)} pp</b></div><div><span>Next-checkpoint SOH · XGBoost</span><b>{fmt(oxfordSoh.xgboost?.macro_cell_mae, 3)} pp</b></div><div><span>RUL to 70% first observation · 2 crossings only</span><b>{oxfordRul ? `${fmt(oxfordRul.macro_cell_mae, 0)} cycles` : "—"}</b></div></div><p className="dataset-note">SOH predicts the next recorded checkpoint (nominally 100-cycle spacing), not the next cycle. The RUL value is exploratory and based on only {countStatuses(data.oxford?.rul_status_by_cell, "threshold_crossed")} crossed cells; it is not a dependable performance claim.</p></article>
      <article className="panel dataset-card"><div className="dataset-card-head"><div><div className="kicker">CALCE CS2</div><h3>Excel test workbooks</h3></div><span className="dataset-status status-model">6-CELL SOH MODEL</span></div><div className="dataset-count">{data.calce?.cs2_excel_workbooks || 0}<small> workbooks · {data.calce?.cs2_identifiers?.length || 0} identifiers</small></div><div className="dataset-stats"><div><span>Statistics sheets / rows inventoried</span><b>{data.calce?.cs2_workbooks_with_statistics_sheets} / {data.calce?.cs2_statistics_rows}</b></div><div><span>Cells included in SOH validation</span><b>CS2_33–CS2_38</b></div><div><span>Cells excluded by capacity quality gate</span><b>CS2_3, CS2_9</b></div><div><span>SOH LOBO model vs persistence</span><b>0.991 / 0.994 pp</b></div></div><p className="dataset-note">Per-cycle capacity uses the within-cycle range of the cumulative raw channel counter. CS2 model performance is effectively tied with persistence; no CALCE RUL estimate is exposed.</p></article>
      <article className="panel dataset-card"><div className="dataset-card-head"><div><div className="kicker">CALCE PL</div><h3>PL11 and PL13</h3></div><span className="dataset-status status-pending">PARSER PENDING</span></div><div className="dataset-count">{data.calce?.pl_unique_cells?.length || 0}<small> unique cells</small></div><div className="dataset-stats"><div><span>Verified duplicate copies</span><b>{data.calce?.pl_verified_duplicate_file_copies || 0}</b></div></div><p className="dataset-note">MATLAB table payloads need a table-aware parser. Exact duplicate files are counted once; no PL validation result is claimed.</p></article>
    </div>
    <article className="panel dataset-method-note"><div className="kicker">COMPARABILITY</div><h2>Why results stay separated</h2><p>{data.validation_design}</p><p>{data.scope}</p></article>
  </section>;
}

function Overview({ soh, rul, research, eolCells }) {
  const pooledSoh = soh?.pooled_metrics || {};
  const pooledRul = rul?.pooled_metrics_cycles || {};
  const xgbRul = pooledRul.xgboost;
  const evaluations = research?.summary_by_dataset_and_task || {};
  const nasaSoh = evaluations.NASA_B0005_B0018_next_discharge_SOH || {};
  const nasaRul = evaluations.NASA_complete_cell_RUL_to_1p4_Ah || {};
  const heldCellSoh = nasaSoh.linear_regression?.observed_cell_maes || {};
  const heldCellPersistence = nasaSoh.persistence?.observed_cell_maes || {};
  const sohLinearMae = nasaSoh.linear_regression?.macro_cell_mae;
  const sohPersistenceMae = nasaSoh.persistence?.macro_cell_mae;
  const rulMacroMae = nasaRul.xgboost?.macro_cell_mae;
  return <>
    <section className="metric-grid">
      <Metric label="NEXT-DISCHARGE SOH" value={sohLinearMae != null ? fmt(sohLinearMae, 4) : "—"} unit="MACRO CELL MAE · SOH PTS" note={sohPersistenceMae != null ? `4 cells; persistence ${fmt(sohPersistenceMae, 4)} pp (lower)` : "Cell-level evaluation unavailable; restart the API"}/>
      <Metric label="RUL TO NASA EOL" value={rulMacroMae != null ? fmt(rulMacroMae, 2) : "—"} unit="MACRO CELL MAE · CYCLES" note={rulMacroMae != null ? "XGBoost · 3 complete held-out cells" : "Cell-level evaluation unavailable; restart the API"} accent/>
      <Metric label="COMPLETE RUL CELLS" value="03 / 04" unit="cells" note="B0007 did not cross the threshold"/>
      <Metric label="SECOND-LIFE SCREEN" value="HEURISTIC" unit="only" note="Capacity bands; no safety certification"/>
    </section>
    <section className="overview-grid">
      <article className="panel results-panel"><div className="panel-heading"><div><div className="kicker">CELL-HELD-OUT RESULTS</div><h2>RUL error by unseen cell</h2></div><span className="unit">MAE · CYCLES</span></div>
        <div className="fold-table"><div className="fold-head"><span>HELD-OUT CELL</span><span>TRAINED ON</span><span>MAE</span></div>{(rul?.fold_metrics || []).filter((f) => f.model === "xgboost").map((f) => <div className="fold-row" key={f.held_out_battery}><b>{f.held_out_battery}</b><span>{f.training_batteries}</span><strong>{fmt(f.mae_cycles, 2)}</strong></div>)}</div>
        <p className="footnote">Only three independent cells cross the 1.4 Ah study threshold. Macro-cell MAE weights cells equally; many cycle rows do not increase the number of independent cells.</p>
      </article>
      <article className="panel results-panel"><div className="panel-heading"><div><div className="kicker">SOH ERROR BY HELD-OUT CELL</div><h2>Model versus persistence</h2></div><span className="unit">MAE · SOH POINTS</span></div>
        <div className="fold-table"><div className="fold-head"><span>HELD-OUT CELL</span><span>LINEAR MODEL</span><span>PERSISTENCE</span></div>{Object.keys(heldCellSoh).length ? Object.keys(heldCellSoh).map((cell) => <div className="fold-row" key={cell}><b>{cell}</b><span>{fmt(heldCellSoh[cell], 3)}</span><strong>{fmt(heldCellPersistence[cell], 3)}</strong></div>) : <div className="fold-row"><span>Cell-level results require API restart</span><span>—</span><strong>—</strong></div>}</div>
        <p className="footnote">Observed cell-level errors; the 4-cell range is not a confidence interval. Linear regression does not beat persistence on the macro-cell average.</p>
      </article>
      <article className="panel endpoints-panel"><div className="kicker">ENDPOINT STATUS</div><h2>Threshold observations</h2><div className="endpoint-list">{eolCells.map(([id, item]) => <div className="endpoint-row" key={id}><b>{id}</b><span className={item.eol_threshold_crossed ? "status-crossed" : "status-censored"}>{item.eol_threshold_crossed ? `Crossed at discharge ${item.first_eol_discharge_index}` : "Right-censored"}</span><small>{fmt(item.last_capacity_Ah, 3)} Ah final</small></div>)}</div><div className="censored-note"><b>B0007</b> ended above 1.4 Ah. Its threshold-crossing RUL is unknown, so it was excluded from RUL scoring.</div></article>
    </section>
    <section className="bottom-grid"><article className="panel definition-card"><div className="kicker">RUL LABEL</div><h2>Cycles until observed capacity ≤ 1.4 Ah</h2><p>This is the NASA cohort’s study EOL definition. It is not a universal EV retirement or second-life threshold.</p></article><article className="panel warning-card"><div className="warn-icon">!</div><div><div className="kicker">SCIENTIFIC SCOPE</div><h2>Laboratory cells only</h2><p>Different discharge cutoffs, small independent-cell count, and no pack-level or field data limit generalization.</p></div></article></section>
  </>;
}

function AnalysisResult({ result }) {
  const points = result.history_chart || [];
  const explanation = result.next_discharge_soh.explanation || {};
  const terms = explanation.feature_terms || [];
  const shapExplanation = explanation.local_explanation?.method === "TreeSHAP" ? explanation.local_explanation : null;
  const rulShap = result.remaining_useful_life.local_explanation;
  const nasa = (result.dataset_source || "NASA") === "NASA";
  const sourceSohPrediction = result.next_discharge_soh.predicted_soh_percent;
  return <div className="analysis-stack">
    <section className="result-cards">
      <Metric label="CURRENT RELATIVE SOH" value={fmt(result.relative_soh_percent, 2)} unit="%" note={`${result.observed_discharge_records} measured discharges`}/>
      <Metric label="NEXT DISCHARGE MODEL" value={sourceSohPrediction == null ? "Withheld" : fmt(sourceSohPrediction, 2)} unit={sourceSohPrediction == null ? "" : "% SOH"} note={`Persistence reference: ${fmt(result.next_discharge_soh.explanation.persistence_comparator_percent, 2)}%${result.next_discharge_soh.status === "withheld_outside_observed_training_change_range" ? " · model change outside observed range" : ""}`}/>
      <Metric label="ESTIMATED RUL" value={result.remaining_useful_life.estimated_remaining_discharge_cycles == null ? "Withheld" : fmt(result.remaining_useful_life.estimated_remaining_discharge_cycles, 1)} unit={result.remaining_useful_life.estimated_remaining_discharge_cycles == null ? "" : "cycles"} note={result.remaining_useful_life.estimated_remaining_discharge_cycles == null ? (nasa ? "Confirm NASA-like cell protocol and 1.4 Ah endpoint" : "No validated RUL model for this dataset") : "To NASA 1.4 Ah threshold · low confidence"} accent/>
    </section>
    <Suspense fallback={<section className="panel chart-panel chart-box chart-loading">Loading SOH history chart…</section>}><SoHHistoryChart points={points} kicker={result.input_mode === "manual_parameters" ? `TYPED MEASUREMENTS · ${result.dataset_source || "NASA"}` : "UPLOADED TRAJECTORY"}/></Suspense>
    <section className="analysis-grid"><article className="panel explanation-panel"><div className="kicker">SOH PREDICTION EXPLANATION</div><h2>{shapExplanation ? "Local TreeSHAP attribution" : terms.length ? "Linear-model terms" : result.model_name || explanation.model || "Source-specific model"}</h2><p>{shapExplanation?.interpretation || explanation.interpretation || "Research estimate based on measured SOH history."}</p>{shapExplanation ? <div className="contrib-list">{shapExplanation.feature_attributions.map((item)=><div className="contrib-row" key={item.feature}><span>{item.feature.replaceAll("_"," ")}</span><b>{item.shap_value >= 0 ? "+" : ""}{fmt(item.shap_value,3)}</b></div>)}</div> : terms.length ? <div className="contrib-list">{terms.map((item)=><div className="contrib-row" key={item.feature}><span>{item.feature.replaceAll("_"," ")}</span><b>{item.additive_model_term_percentage_points >= 0 ? "+" : ""}{fmt(item.additive_model_term_percentage_points,3)}</b></div>)}</div> : <div className="contrib-list">{Object.entries(explanation.feature_values || {}).map(([name,value])=><div className="contrib-row" key={name}><span>{name.replaceAll("_"," ")}</span><b>{fmt(value,3)}</b></div>)}</div>}<div className="small-note">{explanation.model_minus_persistence_percentage_points == null ? "Model estimate withheld;" : `Model minus persistence: ${fmt(explanation.model_minus_persistence_percentage_points,3)} SOH points.`} {result.next_discharge_soh.validation_context || "No calibrated prediction interval is available."}</div></article>
      <article className="panel recommendation-panel"><div className="kicker">SECOND-LIFE CAPACITY PRE-SCREEN</div><h2>{result.second_life_screening.category}</h2><p>{result.second_life_screening.rationale} Bands are project assumptions, not universal cutoffs.</p><div className="confidence-pill">LOW CONFIDENCE · CAPACITY-ONLY</div><p className="small-note">Engineering assessment required. No reuse application is recommended from these inputs; resistance, power capability, thermal behavior, physical condition, cell matching, BMS, and pack integration have not been assessed.</p><h3>Required engineering checks</h3><ul>{result.second_life_screening.required_follow_up.map((x)=><li key={x}>{x}</li>)}</ul><div className="red-line">Not a safety decision, certification, or application approval.</div></article></section>
    {nasa && <section className="panel scope-panel"><div><div className="kicker">EXPERIMENTAL SEQUENCE MODEL · NOT ACTIVE</div><h2>LSTM RUL cross-cell comparison</h2><p>A separately trained research candidate was evaluated by holding out each complete NASA cell. Its macro-cell MAE is 30.47 cycles, versus 11.67 cycles for the current XGBoost baseline. The LSTM remains inactive because this small experiment performed worse.</p><div className="fold-table"><div className="fold-head"><span>HELD-OUT CELL</span><span>LSTM MAE (CYCLES)</span><span>TRAIN CELLS</span></div><div className="fold-row"><b>B0005</b><span>36.51</span><span>B0006, B0018</span></div><div className="fold-row"><b>B0006</b><span>28.70</span><span>B0005, B0018</span></div><div className="fold-row"><b>B0018</b><span>26.19</span><span>B0005, B0006</span></div></div><p className="footnote">Only three complete independent cells are available. B0007 is right-censored. Results are exploratory and do not establish field or EV-pack validation.</p></div></section>}
    <section className="panel scope-panel"><div className="warn-icon">!</div><div><div className="kicker">RUL SCOPE</div><h2>{result.remaining_useful_life.status === "not_estimated_protocol_unconfirmed" ? "Protocol compatibility not confirmed" : result.remaining_useful_life.status.replaceAll("_"," ")}</h2><p>{result.remaining_useful_life.estimated_remaining_discharge_cycles == null ? (nasa ? "The RUL model is NASA-specific and requires confirmation of compatible protocol and the 1.4 Ah endpoint." : `${result.dataset_source} has no validated interactive RUL model; no RUL estimate is returned.`) : `${result.remaining_useful_life.eol_definition}. Point estimate only; no calibrated prediction interval. The NASA training cohort has three complete cells.`}</p>{rulShap?.feature_attributions?.length > 0 && <><h3>Local TreeSHAP contributions to RUL</h3><p className="small-note">Signed cycle contributions relative to the SHAP baseline; association, not causation.</p><div className="contrib-list">{rulShap.feature_attributions.map((item)=><div className="contrib-row" key={item.feature}><span>{item.feature.replaceAll("_"," ")}</span><b>{item.shap_value >= 0 ? "+" : ""}{fmt(item.shap_value,3)}</b></div>)}</div></>}</div></section>
  </div>;
}

function Metric({ label, value, unit, note, accent }) {
  return <article className={`metric-card ${accent ? "accent" : ""}`}><div className="metric-label">{label}</div><div className="metric-value">{value}<small>{unit}</small></div><div className="metric-note">{note}</div></article>;
}

