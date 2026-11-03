const STORAGE_KEY = "ev-battery-ai.learning-log.v1";

export function readLearningLog() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { records: [], error: "" };
    const parsed = JSON.parse(raw);
    if (parsed?.schema_version !== 1 || !Array.isArray(parsed.records)) {
      return { records: [], error: "The saved learning log has an unrecognized format. Export or recover it before saving new entries." };
    }
    return { records: parsed.records, error: "" };
  } catch {
    return { records: [], error: "The saved learning log could not be read. New saves are disabled to protect existing browser data." };
  }
}

export function writeLearningLog(records) {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
    schema_version: 1,
    updated_at: new Date().toISOString(),
    records,
  }));
}
