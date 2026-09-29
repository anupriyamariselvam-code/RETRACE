const API_BASE = "http://127.0.0.1:8000";

const FAILURE_STATUSES = new Set([
  "BLOCKED", "FAILED", "UNAVAILABLE", "INVALID_INPUT",
  "NEEDS_INFORMATION", "ERROR", "TAMPERED"
]);

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function pretty(value) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

function firstFailure(evidence) {
  return evidence.find(event =>
    FAILURE_STATUSES.has(String(event.status || "").toUpperCase()) ||
    String(event.integrity_status || "").toUpperCase() === "TAMPERED"
  );
}

function diagnosisFor(event, trace) {
  if (!event) {
    return {
      title: trace.status === "COMPLETED" ? "No failed stage recorded" : "No explicit failed event found",
      explanation: trace.status === "COMPLETED"
        ? "The recorded events do not show a failed stage."
        : "The trace status is not completed, but the evidence does not identify a failed event. Inspect the event details."
    };
  }

  const details = event.details || {};
  let explanation = `The first recorded failure signal occurred at stage "${event.stage}" (status: ${event.status}).`;
  if (Array.isArray(details.violations) && details.violations.length) {
    explanation += " Policy evidence: " + details.violations.join("; ") + ".";
  } else if (details.message) {
    explanation += " Recorded message: " + details.message;
  } else if (details.reason) {
    explanation += " Recorded reason: " + details.reason;
  } else if (details.available_quantity !== undefined || details.requested_quantity !== undefined) {
    explanation += ` Inventory evidence: requested ${details.requested_quantity ?? "?"}, available ${details.available_quantity ?? "?"}.`;
  }
  return { title: `Failure point: ${event.stage}`, explanation };
}

function renderTrace(container, trace) {
  container.replaceChildren();
  const heading = el("div", "result-heading");
  heading.append(el("h3", "", "Trace analysis"));
  heading.append(el("span", `pill ${String(trace.status).toLowerCase()}`, trace.status || "Unknown"));
  container.append(heading);

  const meta = el("div", "meta-grid");
  [["Trace ID", trace.trace_id], ["Request", trace.request], ["Created", trace.timestamp]].forEach(([label, value]) => {
    const item = el("div", "meta-item");
    item.append(el("span", "meta-label", label), el("span", "meta-value", value || "—"));
    meta.append(item);
  });
  container.append(meta);

  const evidence = Array.isArray(trace.evidence) ? trace.evidence : [];
  const failure = firstFailure(evidence);
  const diagnosis = diagnosisFor(failure, trace);
  const diagnosisBox = el("div", failure ? "diagnosis failure" : "diagnosis");
  diagnosisBox.append(el("div", "diagnosis-label", "Evidence-based finding"));
  diagnosisBox.append(el("h4", "", diagnosis.title));
  diagnosisBox.append(el("p", "", diagnosis.explanation));
  diagnosisBox.append(el("p", "caveat", "This identifies the first failure signal in the recorded trace; it is not an automatic proof of the underlying code defect."));
  container.append(diagnosisBox);

  const timelineTitle = el("h4", "timeline-title", `Execution timeline (${evidence.length} events)`);
  container.append(timelineTitle);
  const timeline = el("ol", "timeline");
  evidence.forEach((event, index) => {
    const item = el("li", "timeline-item");
    const status = String(event.status || "UNKNOWN");
    const stateClass = FAILURE_STATUSES.has(status.toUpperCase()) ? "event-failed" : "event-ok";
    const head = el("div", "event-head");
    head.append(el("span", "event-index", String(index + 1).padStart(2, "0")));
    head.append(el("strong", "event-stage", event.stage || "Unknown stage"));
    head.append(el("span", `pill ${stateClass}`, status));
    item.append(head);
    const detail = el("pre", "event-details", pretty(event.details));
    item.append(detail);
    const integrity = event.integrity_status || "NOT_CHECKED";
    item.append(el("div", "integrity", `Evidence integrity: ${integrity}`));
    timeline.append(item);
  });
  container.append(timeline);
}

async function fetchTraceDetail(traceId) {
  const response = await fetch(`${API_BASE}/trace/${encodeURIComponent(traceId)}`);
  if (!response.ok) throw new Error(`Trace detail request failed (${response.status})`);
  return response.json();
}

async function sendTrace() {
  const input = document.getElementById("userInput");
  const result = document.getElementById("result");
  const button = document.getElementById("traceButton");
  const userInput = input.value.trim();

  result.classList.remove("hidden");
  result.textContent = "";
  if (!userInput) {
    result.append(el("p", "error-text", "Enter a request first."));
    return;
  }

  button.disabled = true;
  button.textContent = "Analyzing…";
  result.append(el("p", "muted", "Sending request to RETRACE backend…"));

  try {
    const response = await fetch(`${API_BASE}/trace/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_input: userInput })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    if (!data.trace_id) throw new Error(data.detail || data.message || "Backend response did not include a trace ID.");

    const detail = await fetchTraceDetail(data.trace_id);
    renderTrace(result, detail);
    await loadHistory();
  } catch (error) {
    result.replaceChildren(el("p", "error-text", `Could not analyze request: ${error.message}`));
    console.error(error);
  } finally {
    button.disabled = false;
    button.textContent = "Analyze request";
  }
}

async function openTrace(traceId) {
  const result = document.getElementById("result");
  result.classList.remove("hidden");
  result.textContent = "Loading trace evidence…";
  try {
    const detail = await fetchTraceDetail(traceId);
    renderTrace(result, detail);
    result.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    result.textContent = `Could not load trace: ${error.message}`;
  }
}

async function loadHistory() {
  const history = document.getElementById("history");
  history.replaceChildren(el("p", "muted", "Loading trace history…"));
  try {
    const response = await fetch(`${API_BASE}/trace/`);
    if (!response.ok) throw new Error(`History request failed (${response.status})`);
    const traces = await response.json();
    history.replaceChildren();
    if (!Array.isArray(traces) || traces.length === 0) {
      history.append(el("p", "muted", "No traces have been recorded yet."));
      return;
    }
    traces.forEach(trace => {
      const card = el("article", "history-item");
      const top = el("div", "history-top");
      top.append(el("strong", "", trace.trace_id));
      top.append(el("span", `pill ${String(trace.status || "").toLowerCase()}`, trace.status || "Unknown"));
      card.append(top);
      card.append(el("p", "history-request", trace.request || "Request text unavailable"));
      card.append(el("span", "history-time", trace.timestamp || ""));
      const traceIdInput = document.getElementById("traceId");


      const button = el("button", "small-button", "Inspect evidence");
      button.type = "button";
      button.addEventListener("click", () => openTrace(trace.trace_id));
      card.append(button);
      history.append(card);
    });
  } catch (error) {
    history.replaceChildren(el("p", "error-text", `Could not load history: ${error.message}`));
    console.error(error);
  }
}

document.addEventListener("DOMContentLoaded", loadHistory);
