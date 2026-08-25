// Framework for Multi Layer Control in Python (FMLC) Copyright (c) 2019,
// The Regents of the University of California, through Lawrence Berkeley
// National Laboratory (subject to receipt of any required approvals
// from the U.S. Dept. of Energy). All rights reserved.
//
// Framework for Multi Layer Control
// Frontend logic for the FMLC web interface (vanilla JS, no external dependencies).

'use strict';

var _configJson = null; // parsed JSON from the selected file
var _loopStructure = []; // loop descriptors from /api/load
var _pollTimer = null; // setInterval handle

function showPage(name, link) {
  var pages = document.querySelectorAll('.page');
  for (var i = 0; i < pages.length; i++) { pages[i].classList.remove('active'); }
  var target = document.getElementById('page-' + name);
  if (target) { target.classList.add('active'); }

  var links = document.querySelectorAll('nav ul li a');
  for (var j = 0; j < links.length; j++) { links[j].classList.remove('active'); }
  if (link) { link.classList.add('active'); }
}

function onFileSelected(input) {
  var file = input.files && input.files[0];
  if (!file) { return; }
  showMsg('');

  var reader = new FileReader();
  reader.onload = function (evt) {
    try {
      _configJson = JSON.parse(evt.target.result);
      // Populate fields from stack_config; only overwrite if each key is present
      var sc = _configJson.stack_config || {};
      if ('tz' in sc) { document.getElementById('cfg-tz').value = sc['tz']; }
      if ('name' in sc) { document.getElementById('cfg-name').value = sc['name']; }
      if ('log_level' in sc) { document.getElementById('cfg-loglevel').value = sc['log_level']; }
      setStackConfigInputs(false); // enable
      document.getElementById('btn-load').disabled = false;
      showMsg('File parsed. Click "Load Config" to initialise the stack.', true);
    } catch (e) {
      _configJson = null;
      document.getElementById('btn-load').disabled = true;
      setStackConfigInputs(true); // disable
      showMsg('ERROR: Could not parse JSON:' + e.message);
    }
  };
  reader.readAsText(file);
}

function loadConfig() {
  if (!_configJson) { showMsg('No config file loaded.'); return; }
  setButtons(false, false, false, false);
  showMsg('Loading config:', true);

  // Merge UI field values into the config as stack_config before posting
  var payload = JSON.parse(JSON.stringify(_configJson)); // deep copy
  payload.stack_config = {
    tz: parseInt(document.getElementById('cfg-tz').value, 10),
    name: document.getElementById('cfg-name').value,
    log_level: parseInt(document.getElementById('cfg-loglevel').value, 10)
  };

  apiPost('/api/load', payload, function (data, err) {
    if (err || !data || data.status !== 'ok') {
      showMsg('ERROR: ' + (data && data.message ? data.message : err));
      setButtons(!!_configJson, false, false, false);
      setBadge('error');
      return;
    }
    _loopStructure = data.loops || [];
    buildTables(_loopStructure);
    // Reflect the confirmed stack_config back from the server
    var sc = data.stack_config;
    document.getElementById('cfg-tz').value = sc['tz'];
    document.getElementById('cfg-name').value = sc['name'];
    document.getElementById('cfg-loglevel').value = sc['log_level'];
    setBadge('loaded');
    showMsg('Config loaded. Click "Start FMLC" to begin.', true);
    document.getElementById('btn-load').disabled = false;
    document.getElementById('btn-start').disabled = false;
    document.getElementById('btn-stop').disabled = true;
    document.getElementById('btn-unload').disabled = false;
    setStackConfigInputs(true); // stack already created; changes have no effect
  });
}

function startFmlc() {
  showMsg('Starting FMLC:', true);
  setButtons(false, false, false, false);

  apiPost('/api/start', {}, function (data, err) {
    if (err || !data || data.status !== 'ok') {
      showMsg('ERROR: ' + (data && data.message ? data.message : err));
      document.getElementById('btn-start').disabled = false;
      setBadge('error');
      return;
    }
    setBadge('running');
    showMsg('FMLC is running.', true);
    document.getElementById('btn-load').disabled = true;
    document.getElementById('btn-start').disabled = true;
    document.getElementById('btn-stop').disabled = false;
    document.getElementById('btn-unload').disabled = true;
    setStackConfigInputs(true); // lock while running
  });
}

function stopFmlc() {
  showMsg('Stopping FMLC:', true);
  setButtons(false, false, false, false);

  apiPost('/api/stop', {}, function (data, err) {
    if (err || !data || data.status !== 'ok') {
      showMsg('ERROR: ' + (data && data.message ? data.message : err));
      document.getElementById('btn-stop').disabled = false;
      setBadge('error');
      return;
    }
    setBadge('stopped');
    showMsg('FMLC stopped. Click "Start FMLC" to resume, or "Unload FMLC" to reset.', true);
    document.getElementById('btn-load').disabled = !(_configJson !== null);
    document.getElementById('btn-start').disabled = !(_loopStructure.length > 0 && _configJson !== null);
    document.getElementById('btn-stop').disabled = true;
    document.getElementById('btn-unload').disabled = false;
    setStackConfigInputs(true); // stack still in memory; changes have no effect
  });
}

function unloadFmlc() {
  showMsg('Unloading FMLC:', true);
  setButtons(false, false, false, false);

  apiPost('/api/unload', {}, function (data, err) {
    if (err || !data || data.status !== 'ok') {
      showMsg('ERROR: ' + (data && data.message ? data.message : err));
      document.getElementById('btn-unload').disabled = false;
      setBadge('error');
      return;
    }
    // Reset all client-side stack state
    _loopStructure = [];
    var container = document.getElementById('loop-tables');
    container.innerHTML = '<p style="color:#888; font-size:13px;">Load a config file to display the control loop tables.</p>';
    setStackConfigInputs(true); // disable until next config is loaded
    clearLogs();
    setBadge('idle');
    showMsg('FMLC unloaded. Select a config file and click "Load Config" to start fresh.', true);
    // Only Load Config can be re-enabled (if a file is already selected)
    document.getElementById('btn-load').disabled = (_configJson === null);
    document.getElementById('btn-start').disabled = true;
    document.getElementById('btn-stop').disabled = true;
    document.getElementById('btn-unload').disabled = true;
  });
}

var POLL_INTERVAL_MS = 2000;

function startPolling() {
  if (_pollTimer !== null) { return; }
  _pollTimer = setInterval(pollStatus, POLL_INTERVAL_MS);
}

function pollStatus() {
  apiGet('/api/status', function (data, err) {
    if (err || !data) { return; }
    var badge = document.getElementById('status-badge');
    if (badge && badge.textContent.toLowerCase() !== data.fmlc_status) {
      setBadge(data.fmlc_status);
    }
    syncButtonsFromStatus(data.fmlc_status);
    var modules = data.modules || {};
    for (var name in modules) {
      if (!modules.hasOwnProperty(name)) { continue; }
      var info = modules[name];
      updateCell('log-' + safeCellId(name), info.last_log || '');
      updateCell('exec-' + safeCellId(name), info.last_exec || '');
      updateCell('dur-' + safeCellId(name), (info.last_duration !== undefined && info.last_duration !== -1) ? info.last_duration + ' s' : '-');
    }
  });
  apiGet('/api/logs', function (data, err) {
    if (err || !data) { return; }
    var lines = data.lines || [];
    // Last log line on main page
    var lastEl = document.getElementById('last-log');
    if (lastEl && lines.length) { lastEl.textContent = lines[lines.length - 1]; }
    // Full log on log tab
    var el = document.getElementById('log-output');
    if (!el) { return; }
    var text = lines.join('\n');
    if (el.textContent !== text) {
      var atBottom = el.scrollHeight - el.scrollTop <= el.clientHeight + 2;
      el.textContent = text;
      if (atBottom) { el.scrollTop = el.scrollHeight; } // auto-scroll only when at bottom
    }
  });
}

function clearLogs() {
  apiPost('/api/logs/clear', {}, function () {
    var el = document.getElementById('log-output');
    if (el) { el.textContent = ''; }
    var lastEl = document.getElementById('last-log');
    if (lastEl) { lastEl.textContent = ''; }
  });
}

function updateCell(cellId, newText) {
  var cell = document.getElementById(cellId);
  if (!cell) { return; }
  if (cell.textContent !== newText) {
    cell.textContent = newText;
  }
}

function syncButtonsFromStatus(status) {
  var btnLoad = document.getElementById('btn-load');
  var btnStart = document.getElementById('btn-start');
  var btnStop = document.getElementById('btn-stop');
  var btnUnload = document.getElementById('btn-unload');
  if (!btnLoad) { return; }

  // Load Config requires a file to have been parsed in this browser session.
  var hasFile = (_configJson !== null);
  // Start/Unload require the stack to have been loaded in this session (tables present).
  var hasStack = (hasFile && _loopStructure.length > 0);

  if (status === 'running') {
    btnLoad.disabled = true; // cannot load a new config while running
    btnStart.disabled = true;
    btnStop.disabled = false;
    btnUnload.disabled = true; // must stop before unloading
    setStackConfigInputs(true); // locked while running
  } else if (status === 'stopped' || status === 'loaded') {
    btnLoad.disabled = !hasFile;
    btnStart.disabled = !hasStack;
    btnStop.disabled = true;
    btnUnload.disabled = !hasStack;
    setStackConfigInputs(true); // stack exists; changes have no effect until next Load Config
  } else {
    // idle or error: editable whenever a file has been selected
    btnLoad.disabled = !hasFile;
    btnStart.disabled = true;
    btnStop.disabled = true;
    btnUnload.disabled = true;
    setStackConfigInputs(!hasFile);
  }
}

function buildTables(loops) {
  var container = document.getElementById('loop-tables');
  container.innerHTML = '';

  if (!loops || loops.length === 0) {
    container.innerHTML = '<p style="color:#888;font-size:13px;">No loops found in config.</p>';
    return;
  }

  for (var i = 0; i < loops.length; i++) {
    var loop = loops[i];
    var section = document.createElement('div');
    section.className = 'panel';

    var heading = document.createElement('h2');
    heading.textContent = 'Loop: ' + loop.name + ' (' + loop.sampletime + ' s)';
    section.appendChild(heading);

    var table = document.createElement('table');

    // Header row
    var thead = table.createTHead();
    var hrow = thead.insertRow();
    ['Module', 'Last Log Message', 'Last Execution Time', 'Duration'].forEach(function (col) {
      var th = document.createElement('th');
      th.textContent = col;
      hrow.appendChild(th);
    });

    // Data rows - one per module in this loop
    var tbody = table.createTBody();
    var mods = loop.modules || [];
    for (var j = 0; j < mods.length; j++) {
      var modName = mods[j];
      var row = tbody.insertRow();

      var tdName = row.insertCell();
      tdName.textContent = modName;

      var tdLog = row.insertCell();
      tdLog.id = 'log-' + safeCellId(modName);
      tdLog.className = 'cell-log';
      tdLog.textContent = '-';

      var tdExec = row.insertCell();
      tdExec.id = 'exec-' + safeCellId(modName);
      tdExec.className = 'cell-exec';
      tdExec.textContent = '-';

      var tdDur = row.insertCell();
      tdDur.id = 'dur-' + safeCellId(modName);
      tdDur.className = 'cell-exec';
      tdDur.textContent = '-';
    }

    section.appendChild(table);
    container.appendChild(section);
  }
}

function safeCellId(name) {
  return name.replace(/[^a-zA-Z0-9_-]/g, '_');
}

// Enable or disable all stack config input fields.
function setStackConfigInputs(disabled) {
  document.getElementById('cfg-tz').disabled = disabled;
  document.getElementById('cfg-name').disabled = disabled;
  document.getElementById('cfg-loglevel').disabled = disabled;
}

function setButtons(load, start, stop, unload) {
  document.getElementById('btn-load').disabled = !load;
  document.getElementById('btn-start').disabled = !start;
  document.getElementById('btn-stop').disabled = !stop;
  document.getElementById('btn-unload').disabled = !unload;
}

function setBadge(status) {
  var badge = document.getElementById('status-badge');
  if (!badge) { return; }
  badge.className = status || 'idle';
  badge.textContent = status ? (status.charAt(0).toUpperCase() + status.slice(1)) : 'Idle';
}

function showMsg(text, ok) {
  var el = document.getElementById('msg-line');
  if (!el) { return; }
  el.textContent = text || '';
  el.className = ok ? 'ok' : '';
}

function apiPost(url, payload, callback) {
  var xhr = new XMLHttpRequest();
  xhr.open('POST', url, true);
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.onreadystatechange = function () {
    if (xhr.readyState !== 4) { return; }
    try {
      callback(JSON.parse(xhr.responseText), xhr.status >= 400 ? ('HTTP ' + xhr.status) : null);
    } catch (e) { callback(null, 'Parse error: ' + e.message); }
  };
  xhr.onerror = function () { callback(null, 'Network error'); };
  xhr.send(JSON.stringify(payload));
}

function apiGet(url, callback) {
  var xhr = new XMLHttpRequest();
  xhr.open('GET', url, true);
  xhr.onreadystatechange = function () {
    if (xhr.readyState !== 4) { return; }
    try {
      callback(JSON.parse(xhr.responseText), xhr.status >= 400 ? ('HTTP ' + xhr.status) : null);
    } catch (e) { callback(null, 'Parse error: ' + e.message); }
  };
  xhr.onerror = function () { callback(null, 'Network error'); };
  xhr.send();
}

startPolling();
