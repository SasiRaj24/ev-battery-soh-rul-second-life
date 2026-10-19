const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001/api/v2";

async function request(path, options) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    let detail = `API returned ${response.status}`;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch { /* retain status text */ }
    throw new Error(detail);
  }
  return response.json();
}

export const getSohValidation = () => request("/validation/soh");
export const getRulValidation = () => request("/validation/rul");
export const getResearchEvaluation = () => request("/validation/research");
export const getDatasetCatalog = () => request("/datasets");
export const getModelManifest = () => request("/models");
export const analyzeCsv = (text, compatibleWithNasaRulScope = false) => request(`/analyze/csv?compatible_with_nasa_rul_scope=${compatibleWithNasaRulScope}`, {
  method: "POST",
  headers: { "Content-Type": "text/csv; charset=utf-8" },
  body: text,
});
export const analyzeParameters = (values) => request("/analyze/parameters", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(values),
});
export const analyzeCollectiveParameters = (values) => request("/analyze/collective", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(values),
});
