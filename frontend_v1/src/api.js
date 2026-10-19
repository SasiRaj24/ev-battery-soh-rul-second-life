const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

async function request(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) throw new Error(`Research API returned ${response.status}`);
  return response.json();
}

export const getHealth = () => request("/health");
export const getSummary = () => request("/validation/summary");
export const getFolds = () => request("/validation/folds");
export const getPredictions = (battery, model) =>
  request(`/validation/batteries/${battery}/predictions?model=${encodeURIComponent(model)}`);
