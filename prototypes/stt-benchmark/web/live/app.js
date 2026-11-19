const elements = {
  badge: document.querySelector('#connectionBadge'),
  listen: document.querySelector('#listenButton'),
  clear: document.querySelector('#clearButton'),
  reconnect: document.querySelector('#reconnectButton'),
  fullscreen: document.querySelector('#fullscreenButton'),
  settingsButton: document.querySelector('#settingsButton'),
  settingsPanel: document.querySelector('#settingsPanel'),
  warning: document.querySelector('#warningPanel'),
  deviceName: document.querySelector('#deviceName'),
  deviceDetails: document.querySelector('#deviceDetails'),
  transcript: document.querySelector('#transcriptList'),
  transcriptPanel: document.querySelector('.transcript-panel'),
  viewOptions: [...document.querySelectorAll('.view-option')],
  empty: document.querySelector('#emptyState'),
  names: [document.querySelector('#speakerOne'), document.querySelector('#speakerTwo')],
  meters: [document.querySelector('#meterOne'), document.querySelector('#meterTwo')],
  db: [document.querySelector('#dbOne'), document.querySelector('#dbTwo')],
  thresholds: [document.querySelector('#thresholdOne'), document.querySelector('#thresholdTwo')],
  active: [document.querySelector('#activeOne'), document.querySelector('#activeTwo')],
  absoluteThreshold: document.querySelector('#absoluteThresholdSlider'),
  absoluteThresholdValue: document.querySelector('#absoluteThresholdValue'),
  margin: document.querySelector('#marginSlider'),
  marginValue: document.querySelector('#marginValue'),
  calibrate: document.querySelector('#calibrateButton'),
  silence: document.querySelector('#silenceSlider'),
  silenceValue: document.querySelector('#silenceValue'),
};

let currentStatus = null;
let renderedIds = new Set();
let renderedView = null;
let settingsLoaded = false;
let saveTimer = null;

async function post(path, body = {}) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.error || 'Opdracht mislukt');
}

function escapeText(value) {
  const node = document.createElement('span');
  node.textContent = value;
  return node.innerHTML;
}

function renderMessages(messages) {
  const view = elements.transcriptPanel.dataset.view || 'cards';
  if (renderedView !== view) {
    renderedView = view;
    renderedIds.clear();
    elements.transcript.innerHTML = '';
  }

  if (!messages.length) {
    elements.empty.classList.remove('hidden');
    elements.transcript.innerHTML = '';
    renderedIds.clear();
    return;
  }
  elements.empty.classList.add('hidden');

  if (view === 'speakers' && !elements.transcript.querySelector('.speaker-lane')) {
    elements.names.forEach((input, index) => {
      const lane = document.createElement('section');
      lane.className = 'speaker-lane';
      lane.dataset.channel = String(index + 1);
      lane.style.setProperty('--lane-color', index === 0 ? '#2563eb' : '#d97706');
      lane.innerHTML = `<h2 class="speaker-lane-heading">${escapeText(input.value || `Spreker ${index + 1}`)}</h2>`;
      elements.transcript.appendChild(lane);
    });
  }

  if (view === 'speakers') {
    elements.transcript.querySelectorAll('.speaker-lane-heading').forEach((heading, index) => {
      heading.textContent = elements.names[index].value || `Spreker ${index + 1}`;
    });
  }

  let added = false;
  for (const message of messages) {
    if (renderedIds.has(message.id)) continue;
    renderedIds.add(message.id);
    const article = document.createElement('article');
    article.className = 'message';
    article.style.setProperty('--speaker-color', message.color);
    const correction = message.corrected
      ? `<p class="corrected-note">Modeltekst: ${escapeText(message.raw_text)}</p>`
      : '';
    article.innerHTML = `
      <div class="message-head">
        <span class="message-speaker">${escapeText(message.speaker)}</span>
        <span class="message-time">${escapeText(message.time)}</span>
        <span class="message-stats">${message.processing_seconds.toFixed(1)} s verwerking</span>
      </div>
      <p class="message-text">${escapeText(message.text)}</p>
      ${correction}
    `;
    if (view === 'speakers') {
      const lane = elements.transcript.querySelector(`.speaker-lane[data-channel="${message.channel}"]`);
      (lane || elements.transcript).appendChild(article);
    } else {
      elements.transcript.appendChild(article);
    }
    added = true;
  }
  if (added) elements.transcript.scrollTop = elements.transcript.scrollHeight;
}

function renderStatus(status) {
  currentStatus = status;
  elements.badge.textContent = status.calibrating ? 'Kalibreert…' : status.running ? 'Luistert' : 'Gepauzeerd';
  elements.badge.className = `status-badge ${status.calibrating ? 'waiting' : status.running ? 'live' : 'paused'}`;
  elements.listen.textContent = status.running ? 'Pauzeren' : 'Start luisteren';
  elements.deviceName.textContent = status.device.name;
  elements.deviceDetails.textContent = `${status.device.host_api} · ${status.device.channels} USB-kanalen · ${status.device.processed_channels} gebruikt · ${status.device.sample_rate / 1000} kHz`;

  status.channels.forEach((channel, index) => {
    elements.meters[index].style.width = `${Math.round(channel.level * 100)}%`;
    elements.db[index].textContent = `${channel.dbfs.toFixed(0)} dBFS`;
    elements.thresholds[index].textContent = channel.calibrating
      ? 'grens wordt gemeten…'
      : `grens ${channel.start_threshold_dbfs.toFixed(0)} dBFS`;
    elements.active[index].textContent = channel.calibrating ? 'Kalibreert…' : channel.active ? 'Luistert…' : 'Stil';
    elements.active[index].classList.toggle('active', channel.active);
    if (document.activeElement !== elements.names[index]) elements.names[index].value = channel.speaker;
  });

  if (!settingsLoaded) {
    elements.absoluteThreshold.value = status.settings.minimum_voice_dbfs;
    elements.absoluteThresholdValue.textContent = `${status.settings.minimum_voice_dbfs.toFixed(0)} dBFS`;
    elements.margin.value = status.settings.noise_margin_db;
    elements.marginValue.textContent = `${status.settings.noise_margin_db.toFixed(0)} dB`;
    elements.silence.value = status.settings.silence_ms;
    elements.silenceValue.textContent = `${status.settings.silence_ms} ms`;
    settingsLoaded = true;
  }

  const warnings = [];
  if (status.calibrating && status.running) {
    const seconds = Math.max(0, 3 * (1 - status.calibration_progress));
    warnings.push(`Kalibratie: blijf nog ${seconds.toFixed(1)} seconde stil.`);
  }
  if (status.mono_suspected) {
    warnings.push('De twee kanalen lijken identiek. Controleer of de ontvanger nog in de afzonderlijke meerkanaalsmodus staat.');
  }
  if (status.dropped_blocks) warnings.push(`${status.dropped_blocks} audioblokken overgeslagen; sluit zware programma’s.`);
  if (status.stream_status) warnings.push(`Audio: ${status.stream_status}`);
  if (status.audio_error) warnings.push(`Microfoon: ${status.audio_error}`);
  if (status.model_error) warnings.push(`Transcriptie: ${status.model_error}`);
  elements.warning.textContent = warnings.join(' ');
  elements.warning.classList.toggle('hidden', warnings.length === 0);
  renderMessages(status.messages);
}

async function refresh() {
  try {
    const response = await fetch('/api/status', { cache: 'no-store' });
    if (!response.ok) throw new Error('Geen verbinding');
    renderStatus(await response.json());
  } catch (error) {
    elements.badge.textContent = 'Geen verbinding';
    elements.badge.className = 'status-badge waiting';
  }
}

function scheduleSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    try {
      await post('/api/config', {
        speakers: elements.names.map((input) => ({ name: input.value })),
        minimum_voice_dbfs: Number(elements.absoluteThreshold.value),
        noise_margin_db: Number(elements.margin.value),
        silence_ms: Number(elements.silence.value),
      });
    } catch (error) {
      elements.warning.textContent = error.message;
      elements.warning.classList.remove('hidden');
    }
  }, 250);
}

elements.listen.addEventListener('click', async () => {
  if (!currentStatus) return;
  await post(currentStatus.running ? '/api/stop' : '/api/start');
  await refresh();
});
elements.clear.addEventListener('click', async () => {
  await post('/api/clear');
  renderedIds.clear();
  elements.transcript.innerHTML = '';
  await refresh();
});

elements.reconnect.addEventListener('click', async () => {
  elements.reconnect.disabled = true;
  elements.reconnect.textContent = 'Verbinden…';
  try {
    await post('/api/reconnect');
    await refresh();
  } catch (error) {
    elements.warning.textContent = error.message;
    elements.warning.classList.remove('hidden');
  } finally {
    elements.reconnect.disabled = false;
    elements.reconnect.textContent = 'Microfoon opnieuw verbinden';
  }
});
elements.fullscreen.addEventListener('click', () => {
  if (document.fullscreenElement) document.exitFullscreen();
  else document.documentElement.requestFullscreen();
});
elements.settingsButton.addEventListener('click', () => {
  const open = elements.settingsPanel.classList.toggle('hidden') === false;
  elements.settingsButton.setAttribute('aria-expanded', String(open));
});
elements.names.forEach((input) => input.addEventListener('input', scheduleSave));
elements.absoluteThreshold.addEventListener('input', () => {
  elements.absoluteThresholdValue.textContent = `${elements.absoluteThreshold.value} dBFS`;
  scheduleSave();
});
elements.margin.addEventListener('input', () => {
  elements.marginValue.textContent = `${elements.margin.value} dB`;
  scheduleSave();
});
elements.calibrate.addEventListener('click', async () => {
  elements.calibrate.disabled = true;
  try {
    await post('/api/calibrate');
    await refresh();
  } finally {
    elements.calibrate.disabled = false;
  }
});
elements.silence.addEventListener('input', () => {
  elements.silenceValue.textContent = `${elements.silence.value} ms`;
  scheduleSave();
});

elements.viewOptions.forEach((button) => button.addEventListener('click', () => {
  const view = button.dataset.view;
  elements.transcriptPanel.dataset.view = view;
  elements.viewOptions.forEach((option) => {
    const selected = option === button;
    option.classList.toggle('selected', selected);
    option.setAttribute('aria-pressed', String(selected));
  });
  if (currentStatus) renderMessages(currentStatus.messages);
}));

refresh();
setInterval(refresh, 250);
