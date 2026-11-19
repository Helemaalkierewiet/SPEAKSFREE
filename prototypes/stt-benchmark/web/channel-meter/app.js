const ACTIVE_DB = -52;

const ui = {
  status: document.querySelector('#statusBadge'),
  start: document.querySelector('#startButton'),
  stop: document.querySelector('#stopButton'),
  warning: document.querySelector('#warningPanel'),
  settings: [...document.querySelectorAll('#settingsList dd')],
  correlations: document.querySelector('#correlations'),
  cards: [...document.querySelectorAll('.meter-card')],
};

function showWarning(message = '') {
  ui.warning.textContent = message;
  ui.warning.classList.toggle('hidden', !message);
}

function setStatus(text, state) {
  ui.status.textContent = text;
  ui.status.className = `badge ${state}`;
}

async function post(path) {
  const response = await fetch(path, { method: 'POST' });
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.error || 'Opdracht mislukt');
}

function emptyLevel() {
  return { rms: 0, dbfs: -160, peak: 0 };
}

function render(status) {
  setStatus(status.running ? 'Meet live' : 'Gestopt', status.running ? 'live' : 'waiting');
  ui.start.disabled = status.running;
  ui.stop.disabled = !status.running;

  ui.settings[0].textContent = status.raw ? 'RAW WASAPI' : 'onbekend';
  ui.settings[1].textContent = status.device || '—';
  ui.settings[2].textContent = status.channels || '—';
  ui.settings[3].textContent = status.sample_rate ? `${status.sample_rate / 1000} kHz` : '—';

  const levels = Array.from({ length: 4 }, (_, index) => status.levels?.[index] || emptyLevel());
  levels.forEach((level, index) => {
    const card = ui.cards[index];
    const active = level.dbfs >= ACTIVE_DB;
    const width = Math.max(0, Math.min(100, ((level.dbfs + 72) / 72) * 100));
    card.querySelector('.meter-fill').style.width = `${width}%`;
    card.querySelector('.db').textContent = level.dbfs <= -150 ? '−∞ dBFS' : `${level.dbfs.toFixed(1)} dBFS`;
    card.querySelector('.peak').textContent = `piek ${(level.peak * 100).toFixed(1)}%`;
    card.querySelector('.state').textContent = active ? 'Signaal' : 'Stil';
    card.classList.toggle('active', active);
  });

  const correlations = status.correlations || [];
  ui.correlations.innerHTML = correlations.length
    ? correlations.map((pair) => {
      const activePair = levels[pair.left - 1].dbfs >= ACTIVE_DB || levels[pair.right - 1].dbfs >= ACTIVE_DB;
      const identical = activePair && pair.value > 0.995;
      return `<span class="correlation ${identical ? 'identical' : ''}">CH${pair.left}–CH${pair.right}: ${(pair.value * 100).toFixed(1)}%</span>`;
    }).join('')
    : '<span>Start de meting om te vergelijken.</span>';

  showWarning(status.error || '');
}

async function refresh() {
  try {
    const response = await fetch('/api/status', { cache: 'no-store' });
    if (!response.ok) throw new Error('Geen verbinding met de meter');
    render(await response.json());
  } catch (error) {
    setStatus('Geen verbinding', 'error');
    showWarning(error.message);
  }
}

ui.start.addEventListener('click', async () => {
  ui.start.disabled = true;
  setStatus('RAW-bron starten…', 'waiting');
  try {
    await post('/api/start');
    await refresh();
  } catch (error) {
    showWarning(error.message);
    setStatus('Start mislukt', 'error');
  }
});

ui.stop.addEventListener('click', async () => {
  await post('/api/stop');
  await refresh();
});

refresh();
setInterval(refresh, 100);
