// manual_override.js
// Standalone module for toggling between Manual Mode and Agent Mode, recording manual actions, and exposing them for retrieval
(function() {
  if (window.__manualOverrideInjected) return;
  window.__manualOverrideInjected = true;

  let isManual = false;
  const manualActions = [];

  // --- UI Creation ---
  const recorderUI = document.createElement('div');
  recorderUI.id = 'recorderUI';
  recorderUI.innerHTML = `
    <button id="recordToggle" class="glass-toggle">
      <span class="toggle-dot"></span>
      <span class="toggle-label">Manual Mode</span>
    </button>
    <div id="recStatus" class="glass-status">Status: Agent Mode</div>
    <button id="downloadActions" class="glass-download" style="display:none">⬇️ Download Actions JSON</button>
  `;
  document.body.appendChild(recorderUI);

  // --- Style Injection ---
  const style = document.createElement('style');
  style.textContent = `
    #recorderUI {
      position: fixed;
      left: 50%;
      bottom: 36px;
      transform: translateX(-50%);
      background: rgba(34, 40, 49, 0.55);
      border-radius: 18px;
      box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border: 1px solid rgba(255,255,255,0.18);
      z-index: 9999;
      padding: 18px 22px 18px 22px;
      display: flex;
      flex-direction: column;
      align-items: center;
      min-width: 180px;
    }
    .glass-toggle {
      display: flex;
      align-items: center;
      justify-content: flex-start;
      border: none;
      border-radius: 50px;
      padding: 8px 18px 8px 10px;
      background: #2196f3;
      color: #fff;
      font-weight: 500;
      font-size: 15px;
      cursor: pointer;
      box-shadow: 0 2px 8px rgba(33, 150, 243, 0.14);
      transition: background 0.18s, box-shadow 0.18s, color 0.18s;
      margin-bottom: 8px;
      gap: 10px;
      outline: none;
      position: relative;
    }
    .glass-toggle:hover {
      background: #1976d2;
      color: #e3e3e3;
      box-shadow: 0 4px 18px rgba(33, 150, 243, 0.22);
    }
    .toggle-dot {
      display: inline-block;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      background: #fff;
      border: 2px solid #2196f3;
      margin-right: 6px;
      transition: background 0.18s, border 0.18s;
    }
    .glass-toggle.active {
      background: #e53935;
      color: #fff;
      box-shadow: 0 2px 8px rgba(229, 57, 53, 0.18);
    }
    .glass-toggle.active:hover {
      background: #b71c1c;
      color: #fff;
      box-shadow: 0 4px 18px rgba(229, 57, 53, 0.22);
    }
    .glass-toggle.active .toggle-dot {
      background: #fff;
      border: 2px solid #e53935;
    }
    .toggle-label {
      font-size: 15px;
      letter-spacing: 0.5px;
      font-weight: 500;
    }
    .glass-status {
      margin-top: 2px;
      font-size: 13px;
      opacity: 0.82;
      color: #e3e3e3;
      text-align: center;
      margin-bottom: 8px;
    }
    .glass-download {
      margin-top: 10px;
      border-radius: 8px;
      background: linear-gradient(135deg, #2196f3 0%, #21cbf3 100%);
      color: white;
      border: none;
      padding: 7px 18px;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      box-shadow: 0 2px 8px rgba(33, 203, 243, 0.14);
      transition: background 0.18s, box-shadow 0.18s;
    }
    .glass-download:hover {
      background: linear-gradient(135deg, #21cbf3 0%, #2196f3 100%);
      box-shadow: 0 4px 16px rgba(33, 203, 243, 0.22);
    }
  `;
  document.head.appendChild(style);

  // --- Event Handlers ---
  const toggleBtn = recorderUI.querySelector('#recordToggle');
  const recStatus = recorderUI.querySelector('#recStatus');
  const downloadBtn = recorderUI.querySelector('#downloadActions');

  toggleBtn.onclick = () => {
    isManual = !isManual;
    toggleBtn.classList.toggle('active', isManual);
    recStatus.textContent = isManual ? 'Status: Manual Editing...' : 'Status: Agent Mode';
    downloadBtn.style.display = isManual ? 'inline-block' : 'none';
    // Fire a custom event for Python/Playwright/DOMService to listen for mode changes
    window.dispatchEvent(new CustomEvent('manualModeToggled', { detail: { isManual } }));
  };

  downloadBtn.onclick = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(manualActions, null, 2));
    const a = document.createElement('a');
    a.setAttribute("href", dataStr);
    a.setAttribute("download", "manual_actions.json");
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  // --- Action Recording ---
  const eventsToCapture = ["click", "input", "change"];
  const excludeSelectors = ["#recorderUI", "#eventsList", "body", "html", "#downloadActions", "#recordToggle"];
  eventsToCapture.forEach(type => {
    document.addEventListener(type, e => {
      if (!isManual) return;
      const el = e.target;
      const selector = getSelector(el);
      if (excludeSelectors.includes(selector)) return;
      if (e.type === "click" && el.tagName === "SELECT") return;
      let action = null;
      if (e.type === "click") {
        action = {
          type: "click",
          args: { selector },
          timestamp: Date.now()
        };
      } else if (e.type === "input" || e.type === "change") {
        action = {
          type: "fill",
          args: { selector, value: el.value },
          timestamp: Date.now()
        };
      }
      if (!action) return;
      // Merge fill actions by selector (keep latest)
      const idx = manualActions.findIndex(a => a.type === action.type && a.args.selector === action.args.selector);
      if (idx >= 0) {
        manualActions[idx] = action;
      } else {
        manualActions.push(action);
      }
      // Optionally, fire a custom event for external listeners
      window.dispatchEvent(new CustomEvent('manualActionRecorded', { detail: { action } }));
    }, true);
  });

  function getSelector(el) {
    if (el.id) return `#${el.id}`;
    let path = el.tagName.toLowerCase();
    if (el.className) {
      const classes = el.className.split(" ").filter(c => c);
      if (classes.length > 0) path += "." + classes.join(".");
    }
    return path;
  }

  // --- Expose API for DOMService/Python ---
  window.getManualActions = function() {
    return JSON.parse(JSON.stringify(manualActions));
  };
  window.setAgentMode = function() {
    if (isManual) toggleBtn.click();
  };
  window.setManualMode = function() {
    if (!isManual) toggleBtn.click();
  };
})();
