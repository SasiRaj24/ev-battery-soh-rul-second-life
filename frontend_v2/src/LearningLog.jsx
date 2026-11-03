import { useRef, useState } from "react";

const fmt = (value, digits = 2) => Number(value).toFixed(digits);
const validRecord = (record) => record && typeof record.id === "string" && record.id.length > 0
  && typeof record.cell_id === "string" && typeof record.dataset_source === "string"
  && record.inputs && Number.isFinite(Number(record.inputs.current_cycle_number))
  && record.inputs.reference_capacity_Ah > 0 && record.prediction
  && Array.isArray(record.follow_ups) && record.follow_ups.every((item) => item
    && typeof item.id === "string" && Number.isInteger(item.cycle_number)
    && Number.isFinite(item.capacity_Ah) && item.capacity_Ah > 0
    && Number.isFinite(item.measured_soh_percent)
    && typeof item.measurement_provenance === "string"
    && ["soh_only", "threshold_crossed", "right_censored"].includes(item.rul_observation_status))
  && (record.second_life_assessments == null || (Array.isArray(record.second_life_assessments)
    && record.second_life_assessments.every((item) => item && typeof item.id === "string"
      && typeof item.reviewer === "string" && typeof item.intended_application === "string"
      && typeof item.evidence_provenance === "string" && typeof item.disposition === "string")));

function saveAsJson(records) {
  const payload = JSON.stringify({ schema_version: 1, exported_at: new Date().toISOString(), records }, null, 2);
  const url = URL.createObjectURL(new Blob([payload], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `ev-battery-learning-log-${new Date().toISOString().slice(0, 10)}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function LearningLog({ records, onChange, storageError }) {
  const importInput = useRef(null);
  const [openForm, setOpenForm] = useState(null);
  const [openAssessment, setOpenAssessment] = useState(null);
  const [forms, setForms] = useState({});
  const [assessmentForms, setAssessmentForms] = useState({});
  const [formErrors, setFormErrors] = useState({});
  const [notice, setNotice] = useState("");
  const completedCount = records.reduce((sum, item) => sum + item.follow_ups.length, 0);
  const measuredSoh = records.flatMap((record) => record.follow_ups
    .filter((item) => item.prediction_target_cycle_match && Number.isFinite(item.soh_error_measured_minus_predicted_pp))
    .map((item) => ({ source: record.dataset_source, cell: record.cell_id, absError: Math.abs(item.soh_error_measured_minus_predicted_pp) })));
  const sohByFamily = Object.entries(measuredSoh.reduce((groups, item) => {
    const family = groups[item.source] || (groups[item.source] = {});
    const cell = family[item.cell] || (family[item.cell] = []);
    cell.push(item.absError);
    return groups;
  }, {})).map(([family, cells]) => {
    const errorsByCell = Object.values(cells);
    const cellMae = errorsByCell.map((errors) => errors.reduce((sum, value) => sum + value, 0) / errors.length);
    return { family, cells: cellMae.length, observations: errorsByCell.reduce((sum, errors) => sum + errors.length, 0), macroMae: cellMae.reduce((sum, value) => sum + value, 0) / cellMae.length };
  });
  const rulCounts = records.flatMap((record) => record.follow_ups).reduce((counts, item) => {
    if (item.rul_observation_status === "threshold_crossed" && item.first_crossing_confirmed) counts.crossed += 1;
    if (item.rul_observation_status === "right_censored") counts.censored += 1;
    return counts;
  }, { crossed: 0, censored: 0 });
  const assessmentCount = records.reduce((sum, record) => sum + (record.second_life_assessments || []).length, 0);
  const setField = (id, key, value) => setForms((old) => ({
    ...old,
    [id]: { ...(old[id] || {}), [key]: value },
  }));

  function addFollowUp(record) {
    const form = forms[record.id] || {};
    const cycle = Number(form.cycle_number);
    const capacity = Number(form.capacity_Ah);
    const endpoint = form.rul_endpoint_Ah === "" || form.rul_endpoint_Ah == null ? null : Number(form.rul_endpoint_Ah);
    if (!Number.isInteger(cycle) || cycle <= record.inputs.current_cycle_number) {
      setFormErrors((old) => ({ ...old, [record.id]: "Enter a later whole-number cycle than the prediction checkpoint." }));
      return;
    }
    if (!Number.isFinite(capacity) || capacity <= 0 || !form.provenance?.trim()) {
      setFormErrors((old) => ({ ...old, [record.id]: "Enter a positive measured capacity and where/how that measurement was recorded." }));
      return;
    }
    if (endpoint !== null && (!Number.isFinite(endpoint) || endpoint <= 0)) {
      setFormErrors((old) => ({ ...old, [record.id]: "The RUL endpoint must be a positive capacity in Ah." }));
      return;
    }
    if (endpoint !== null && capacity <= endpoint && !form.first_crossing_confirmed) {
      setFormErrors((old) => ({ ...old, [record.id]: "Confirm that this is the first recorded measurement at or below the endpoint before saving a threshold-crossing label." }));
      return;
    }
    const measuredSoh = capacity / record.inputs.reference_capacity_Ah * 100;
    const isTargetCycle = cycle === record.prediction.target_cycle_number;
    const outcomeStatus = endpoint === null ? "soh_only" : capacity <= endpoint ? "threshold_crossed" : "right_censored";
    const followUp = {
      id: globalThis.crypto?.randomUUID?.() || `followup-${Date.now()}`,
      recorded_at: new Date().toISOString(),
      cycle_number: cycle,
      capacity_Ah: capacity,
      measured_soh_percent: measuredSoh,
      measurement_provenance: form.provenance.trim(),
      prediction_target_cycle_match: isTargetCycle,
      soh_error_measured_minus_predicted_pp: isTargetCycle && record.prediction.soh_percent != null
        ? measuredSoh - record.prediction.soh_percent : null,
      rul_endpoint_capacity_Ah: endpoint,
      rul_observation_status: outcomeStatus,
      first_crossing_confirmed: outcomeStatus === "threshold_crossed" && Boolean(form.first_crossing_confirmed),
      observed_remaining_cycles_from_prediction: outcomeStatus === "threshold_crossed" && form.first_crossing_confirmed
        ? cycle - record.inputs.current_cycle_number : null,
    };
    const next = records.map((item) => item.id === record.id
      ? { ...item, follow_ups: [...item.follow_ups, followUp] }
      : item);
    if (!onChange(next)) return;
    setFormErrors((old) => ({ ...old, [record.id]: "" }));
    setForms((old) => ({ ...old, [record.id]: {} }));
    setOpenForm(null);
    setNotice("Follow-up saved. It is a measured outcome record, not a model-training update.");
  }

  function addAssessment(record) {
    const form = assessmentForms[record.id] || {};
    if (!form.intended_application?.trim() || !form.reviewer?.trim() || !form.evidence_provenance?.trim() || !form.disposition) {
      setFormErrors((old) => ({ ...old, [`assessment-${record.id}`]: "Enter the intended application, reviewer, assessment outcome, and evidence/report provenance." }));
      return;
    }
    const assessment = {
      id: globalThis.crypto?.randomUUID?.() || `assessment-${Date.now()}`,
      recorded_at: new Date().toISOString(),
      intended_application: form.intended_application.trim(),
      reviewer: form.reviewer.trim(),
      disposition: form.disposition,
      evidence_provenance: form.evidence_provenance.trim(),
      notes: form.notes?.trim() || "",
      assessment_type: "reviewer_reported_engineering_assessment",
    };
    const next = records.map((item) => item.id === record.id
      ? { ...item, second_life_assessments: [...(item.second_life_assessments || []), assessment] }
      : item);
    if (!onChange(next)) return;
    setFormErrors((old) => ({ ...old, [`assessment-${record.id}`]: "" }));
    setAssessmentForms((old) => ({ ...old, [record.id]: {} }));
    setOpenAssessment(null);
    setNotice("Engineering assessment saved as a reviewer-reported outcome. It does not certify safety or train a model.");
  }

  async function importJson(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      const payload = JSON.parse(await file.text());
      if (payload?.schema_version !== 1 || !Array.isArray(payload.records) || !payload.records.every(validRecord)) {
        setNotice("Import stopped: the JSON does not match the expected learning-log format. Existing records were not changed.");
        return;
      }
      const existingIds = new Set(records.map((item) => item.id));
      const additions = payload.records.filter((item) => {
        if (existingIds.has(item.id)) return false;
        existingIds.add(item.id);
        return true;
      });
      if (!additions.length) {
        setNotice("Nothing imported: all record IDs are already present. Existing records were not changed.");
        return;
      }
      if (!onChange([...additions, ...records])) return;
      setNotice(`Imported ${additions.length} new record${additions.length === 1 ? "" : "s"}. Existing IDs were skipped. Review the source and provenance before using these records.`);
    } catch {
      setNotice("Import stopped: the selected file could not be read as valid JSON. Existing records were not changed.");
    }
  }

  return <section className="learning-page">
    <article className="panel dataset-intro"><div className="kicker">TRACEABLE OUTCOMES · NO AUTOMATIC RETRAINING</div><h2>Prediction and follow-up log</h2><p>Save a model estimate with its cell, input measurements, source, test context, provenance, and model release. Add later capacity measurements to compare SOH at the predicted checkpoint and record RUL observations as threshold-crossed or right-censored.</p><div className="dataset-notice"><b>Storage:</b> entries remain in this browser on this device. Export JSON to back them up or move them; import merges new IDs and skips existing ones. Records are not sent to the server or used to update a model.</div></article>
    {storageError && <div className="error-box">{storageError}</div>}
    {notice && <div className="learning-notice" role="status">{notice}</div>}
    <section className="panel learning-summary">
      <div><div className="kicker">LOCAL RESEARCH RECORDS</div><h2>{records.length} predictions · {completedCount} follow-up measurements</h2><p>Different cells remain identifiable for cell-based evaluation; keep dataset families separate during analysis.</p></div>
      <div className="learning-log-actions"><input ref={importInput} type="file" accept="application/json,.json" onChange={importJson} hidden/><button className="secondary-button" disabled={!records.length} onClick={() => saveAsJson(records)}>Export learning log JSON</button><button className="secondary-button" onClick={() => importInput.current?.click()}>Import / merge JSON</button></div>
    </section>
    <section className="panel learning-evaluation"><div><div className="kicker">OUTCOME REVIEW · OBSERVED LOG ENTRIES</div><h2>Follow-up evaluation</h2><p>SOH scores include only measurements at the exact forecast target cycle. Errors are averaged within cells first, then across cells in each source. These are user-entered observations, not independent benchmark validation.</p></div><div className="learning-evaluation-grid"><div className="evaluation-stat"><span>Matched SOH follow-ups</span><b>{measuredSoh.length}</b></div><div className="evaluation-stat"><span>Cells with scored SOH</span><b>{new Set(measuredSoh.map((item) => `${item.source}:${item.cell}`)).size}</b></div><div className="evaluation-stat"><span>Confirmed threshold crossings</span><b>{rulCounts.crossed}</b></div><div className="evaluation-stat"><span>Right-censored observations</span><b>{rulCounts.censored}</b></div><div className="evaluation-stat"><span>Reviewer-reported reuse assessments</span><b>{assessmentCount}</b></div></div>{sohByFamily.length > 0 && <div className="learning-family-scores"><div className="kicker">SOH · CELL-MACRO MAE</div>{sohByFamily.map((item) => <div key={item.family}><span>{item.family} · {item.cells} cells · {item.observations} matched observations</span><b>{fmt(item.macroMae, 3)} pp</b></div>)}</div>}<div className="dataset-notice"><b>Interpretation:</b> no overall “accuracy rate” is calculated. Cell counts, exact target-cycle matching, source separation, and confirmed endpoint crossings are retained to avoid treating repeated readings as independent batteries. Small or selectively logged samples should not be used to claim general validation.</div></section>
    {!records.length ? <article className="panel empty-learning"><div className="kicker">START WITH A SAVED PREDICTION</div><h2>No predictions logged yet</h2><p>Run a typed analysis, add the cell ID and source provenance, then choose “Save prediction to log” beneath its result. A prediction without a later measured outcome is not a training label.</p></article> : <div className="learning-record-list">
      {records.map((record) => <article className="panel learning-record" key={record.id}>
        <div className="learning-record-heading"><div><div className="kicker">{record.dataset_source} · CELL {record.cell_id}</div><h2>Saved {new Date(record.created_at).toLocaleString()}</h2></div><span className="version-chip">MODEL <b>{record.model_release}</b></span></div>
        <div className="learning-facts"><span>Current cycle <b>{record.inputs.current_cycle_number}</b></span><span>Measured capacity <b>{fmt(record.inputs.current_capacity_Ah, 4)} Ah</b></span><span>Reference <b>{fmt(record.inputs.reference_capacity_Ah, 4)} Ah</b></span><span>Predicted SOH <b>{record.prediction.soh_percent == null ? "Withheld" : `${fmt(record.prediction.soh_percent)}%`}</b></span><span>Target cycle <b>{record.prediction.target_cycle_number}</b></span><span>Predicted RUL <b>{record.prediction.rul_cycles == null ? "Withheld" : `${fmt(record.prediction.rul_cycles, 1)} cycles`}</b></span></div>
        <p className="learning-provenance"><b>Measurement provenance:</b> {record.measurement_provenance}</p>
        {record.test_conditions && <p className="learning-provenance"><b>Test conditions:</b> {record.test_conditions}</p>}
        {(record.second_life_assessments || []).length > 0 && <div className="followup-list"><div className="kicker">REVIEWER-REPORTED SECOND-LIFE ASSESSMENTS</div>{record.second_life_assessments.map((assessment) => <div className="assessment-row" key={assessment.id}><div><b>{assessment.intended_application}</b><span>{assessment.disposition.replaceAll("_", " ")}</span><small>Reviewer: {assessment.reviewer} · {new Date(assessment.recorded_at).toLocaleDateString()}</small><small>Evidence: {assessment.evidence_provenance}</small>{assessment.notes && <small>Notes: {assessment.notes}</small>}</div><span className="assessment-scope">Engineering review record · not a safety certification</span></div>)}</div>}
        {record.follow_ups.length > 0 && <div className="followup-list"><div className="kicker">LATER MEASUREMENTS</div>{record.follow_ups.map((followUp) => <div className="followup-row" key={followUp.id}><div><b>Cycle {followUp.cycle_number}</b><span>{fmt(followUp.capacity_Ah, 4)} Ah · measured SOH {fmt(followUp.measured_soh_percent)}%</span><small>{followUp.measurement_provenance}</small></div><div className="followup-outcome"><b>{followUp.soh_error_measured_minus_predicted_pp == null ? "SOH error not scored" : `${followUp.soh_error_measured_minus_predicted_pp > 0 ? "+" : ""}${fmt(followUp.soh_error_measured_minus_predicted_pp)} pp error`}</b><span>{followUp.rul_observation_status === "right_censored" ? `Right-censored above ${fmt(followUp.rul_endpoint_capacity_Ah, 3)} Ah at cycle ${followUp.cycle_number}` : followUp.rul_observation_status === "threshold_crossed" ? `First recorded threshold crossing at cycle ${followUp.cycle_number} · ${followUp.observed_remaining_cycles_from_prediction} cycles from prediction` : "SOH outcome only · no RUL endpoint entered"}</span></div></div>)}</div>}
        {openAssessment === record.id ? <div className="followup-form-wrap"><div className="kicker">RECORD AN ENGINEERING ASSESSMENT</div><p>Record an assessment already performed by a qualified reviewer. This log does not determine application suitability or certify safety.</p><div className="followup-form assessment-form"><label>Intended application<input value={assessmentForms[record.id]?.intended_application || ""} onChange={(e) => setAssessmentForms((old) => ({ ...old, [record.id]: { ...(old[record.id] || {}), intended_application: e.target.value } }))} placeholder="e.g. stationary backup, low-power storage"/></label><label>Reviewer / role<input value={assessmentForms[record.id]?.reviewer || ""} onChange={(e) => setAssessmentForms((old) => ({ ...old, [record.id]: { ...(old[record.id] || {}), reviewer: e.target.value } }))} placeholder="Qualified reviewer or role"/></label><label>Assessment outcome<select value={assessmentForms[record.id]?.disposition || ""} onChange={(e) => setAssessmentForms((old) => ({ ...old, [record.id]: { ...(old[record.id] || {}), disposition: e.target.value } }))}><option value="">Select reviewed outcome</option><option value="further_testing_required">Further engineering testing required</option><option value="candidate_for_application_assessment">Candidate for this application assessment</option><option value="not_suitable_for_assessed_application">Not suitable for assessed application</option><option value="recycling_or_reengineering_review">Recycling or re-engineering review</option></select></label><label className="followup-provenance">Evidence / report / protocol provenance<input value={assessmentForms[record.id]?.evidence_provenance || ""} onChange={(e) => setAssessmentForms((old) => ({ ...old, [record.id]: { ...(old[record.id] || {}), evidence_provenance: e.target.value } }))} placeholder="Report ID, test protocol, date, instrument, or source"/></label><label className="followup-provenance">Assessment notes · optional<textarea value={assessmentForms[record.id]?.notes || ""} onChange={(e) => setAssessmentForms((old) => ({ ...old, [record.id]: { ...(old[record.id] || {}), notes: e.target.value } }))} placeholder="Summarize reviewed power, impedance, thermal, isolation, matching, or BMS evidence"/></label></div>{formErrors[`assessment-${record.id}`] && <div className="error-box">{formErrors[`assessment-${record.id}`]}</div>}<div className="followup-actions"><button className="primary-button" onClick={() => addAssessment(record)}>Save reviewer assessment</button><button className="text-button" onClick={() => setOpenAssessment(null)}>Cancel</button></div></div> : <button className="secondary-button" onClick={() => { setNotice(""); setOpenAssessment(record.id); }}>+ Record second-life assessment</button>}
        {openForm === record.id ? <div className="followup-form-wrap"><div className="kicker">ADD A LATER MEASURED OUTCOME</div><p>Enter the actual observed checkpoint. RUL endpoint is optional; if capacity remains above it, the record is right-censored and no exact RUL error is calculated.</p><div className="followup-form"><label>Later cycle<input type="number" min={record.inputs.current_cycle_number + 1} step="1" value={forms[record.id]?.cycle_number || ""} onChange={(e) => setField(record.id, "cycle_number", e.target.value)} placeholder={`after ${record.inputs.current_cycle_number}`}/></label><label>Measured discharge capacity (Ah)<input type="number" min="0.0001" step="any" value={forms[record.id]?.capacity_Ah || ""} onChange={(e) => setField(record.id, "capacity_Ah", e.target.value)} placeholder="e.g. 1.76"/></label><label>RUL endpoint capacity (Ah) · optional<input type="number" min="0.0001" step="any" value={forms[record.id]?.rul_endpoint_Ah ?? (record.dataset_source === "NASA" ? "1.4" : "")} onChange={(e) => setField(record.id, "rul_endpoint_Ah", e.target.value)} placeholder="e.g. NASA study: 1.4"/></label><label className="followup-provenance">Measurement provenance<input value={forms[record.id]?.provenance || ""} onChange={(e) => setField(record.id, "provenance", e.target.value)} placeholder="Dataset record, file/sheet, protocol or instrument"/></label><label className="followup-confirm"><input type="checkbox" checked={Boolean(forms[record.id]?.first_crossing_confirmed)} onChange={(e) => setField(record.id, "first_crossing_confirmed", e.target.checked)}/><span>If capacity is at/below the endpoint, confirm this is the first recorded threshold crossing for this cell.</span></label></div>
          {formErrors[record.id] && <div className="error-box">{formErrors[record.id]}</div>}
          <div className="followup-actions"><button className="primary-button" onClick={() => addFollowUp(record)}>Save measured follow-up</button><button className="text-button" onClick={() => setOpenForm(null)}>Cancel</button></div>
        </div> : <button className="secondary-button" onClick={() => { setNotice(""); setOpenForm(record.id); }}>+ Add follow-up measurement</button>}
      </article>)}
    </div>}
    <article className="panel dataset-method-note"><div className="kicker">HOW TO USE THESE RECORDS</div><p>Only compare SOH error when the later measurement is on the model’s target cycle. A measurement at another cycle is retained but its direct forecast error is left unscored. Right-censored RUL observations are retained as bounds, not treated as exact failure times. Review exported records and hold out entire cells and dataset families before training any candidate.</p></article>
  </section>;
}
