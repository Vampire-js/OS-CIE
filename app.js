const formatNumber = (value, digits = 2) =>
  new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits }).format(value);

const escapeHtml = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
      })[character],
  );

function renderProcesses(processes) {
  const body = document.querySelector("#process-table");
  body.innerHTML = processes
    .map(
      (process) => `
        <tr>
          <td class="mono">${process.pid}</td>
          <td><strong>${escapeHtml(process.command)}</strong><br><span class="muted">${escapeHtml(process.user)}</span></td>
          <td><span class="state state-${process.state_code.toLowerCase()}">${escapeHtml(process.state)}</span></td>
          <td>${formatNumber(process.cpu_percent, 1)}%</td>
          <td>${formatNumber(process.memory_percent, 1)}%</td>
        </tr>
      `,
    )
    .join("");
}

function renderLiveMetrics(data) {
  document.querySelector("#cpu-live").textContent =
    data.cpu_percent === null ? "Unavailable" : `${formatNumber(data.cpu_percent, 1)}%`;
  document.querySelector("#memory-used").textContent =
    `${data.memory.used} / ${data.memory.total}`;
  document.querySelector("#memory-detail").textContent =
    `${data.memory.available} available · ${data.memory.buff_cache} buffer/cache · swap ${data.memory.swap_used} used`;
  document.querySelector("#memory-bar").style.width = `${data.memory.used_percent}%`;
  renderProcesses(data.processes);
}

function setLiveStatus(message, connected) {
  const badge = document.querySelector("#live-badge");
  badge.classList.toggle("disconnected", !connected);
  document.querySelector("#live-status").textContent = message;
}

function renderTimings(locality) {
  const row = locality.row_median_ms;
  const column = locality.column_median_ms;
  const maximum = Math.max(row, column);
  const chart = document.querySelector("#timing-chart");
  chart.innerHTML = [
    ["Row-major", row, "row"],
    ["Column-major", column, "column"],
  ]
    .map(
      ([label, value, className]) => `
        <div class="bar-row">
          <div class="bar-label">
            <strong>${label}</strong>
            <span>${formatNumber(value, 3)} ms</span>
          </div>
          <div class="bar-track">
            <div class="bar ${className}" style="width:${(value / maximum) * 100}%"></div>
          </div>
        </div>
      `,
    )
    .join("");

  document.querySelector("#ratio-pill").textContent =
    `${formatNumber(locality.column_to_row_ratio, 2)}× slower by columns`;
  document.querySelector("#experiment-meta").innerHTML = `
    <span><strong>${formatNumber(locality.matrix_size, 0)} × ${formatNumber(locality.matrix_size, 0)}</strong> integers</span>
    <span><strong>${formatNumber(locality.matrix_bytes / 1024 / 1024, 0)} MiB</strong> matrix</span>
    <span><strong>${locality.trials}</strong> alternating trials</span>
    <span><strong>Median</strong> reported</span>
  `;

  const trialRows = locality.row_major_ms
    .map(
      (value, index) => `
        <tr>
          <td>${index + 1}</td>
          <td>${formatNumber(value, 3)} ms</td>
          <td>${formatNumber(locality.column_major_ms[index], 3)} ms</td>
        </tr>
      `,
    )
    .join("");
  document.querySelector("#trial-table").innerHTML = `
    <table>
      <thead><tr><th>Trial</th><th>Row-major</th><th>Column-major</th></tr></thead>
      <tbody>${trialRows}</tbody>
    </table>
  `;
}

async function loadStaticDashboard() {
  const response = await fetch("data/results.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Could not load measurements (${response.status})`);
  }
  const data = await response.json();

  document.querySelector("#capture-time").textContent =
    `Captured live on ${new Date(data.captured_at).toLocaleString()}`;
  document.querySelector("#cpu-model").textContent = data.cpu.model;
  document.querySelector("#cpu-detail").textContent =
    `${data.cpu.cores_per_socket} cores · ${data.cpu.logical_cpus} logical CPUs · up to ${data.cpu.max_mhz} MHz`;
  document.querySelector("#architecture").textContent = data.cpu.architecture;
  document.querySelector("#isa-detail").textContent =
    `${data.cpu.op_modes} · ${data.cpu.byte_order} · ${data.cpu.isa_extensions.join(", ").toUpperCase()}`;
  renderLiveMetrics({
    cpu_percent: null,
    memory: data.memory,
    processes: data.processes,
  });
  renderTimings(data.locality);

  document.querySelector("#command-list").innerHTML = data.commands
    .map((command) => `<li><code>${escapeHtml(command)}</code></li>`)
    .join("");
  document.querySelector("#raw-file-list").innerHTML = data.raw_files
    .map(
      (file) =>
        `<li><a href="data/${encodeURIComponent(file)}">${escapeHtml(file)}</a></li>`,
    )
    .join("");
}

async function pollLiveMetrics() {
  try {
    const response = await fetch("/api/live", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    renderLiveMetrics(data);
    const updated = new Date(data.updated_at).toLocaleTimeString();
    setLiveStatus(`updated ${updated} · every 2s`, true);
  } catch (error) {
    setLiveStatus(`offline · ${error.message}`, false);
  } finally {
    window.setTimeout(pollLiveMetrics, 2000);
  }
}

loadStaticDashboard().then(pollLiveMetrics).catch((error) => {
  document.querySelector("#capture-time").textContent =
    `${error.message}. Run ./run.sh, then start python3 server.py.`;
  setLiveStatus("offline", false);
});
