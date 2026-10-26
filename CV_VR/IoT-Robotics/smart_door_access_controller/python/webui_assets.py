#===--webui_assets.py-------------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import os

# Matches ENROLL_NAME_MAX_LENGTH in python/main.py -- kept as a separate constant since
# this module doesn't import main.py (main.py imports this one), update both together.
_ENROLL_NAME_MAX_LENGTH = 40

# --- App-specific patches applied on top of Arduino's template (face enrollment + ---
# --- granted/verifying/denied recognition feedback). Everything else -- header,   ---
# --- logo, icon set, confidence slider, iframe video feed -- is left untouched.   ---

_INDEX_HTML_ANCHOR = """          <div class="container container-right">
            <div id="feedback-section" class="feedback-section">"""

_INDEX_HTML_INSERT = f"""          <div class="container container-right">
            <div class="feedback-section">
              <h2 class="recent-scans-title" style="margin: 0 0 8px 0">Enrolled Faces</h2>
              <div class="enroll-controls">
                <input type="text" id="enrollNameInput" placeholder="Name" maxlength="{_ENROLL_NAME_MAX_LENGTH}" />
                <button id="enrollButton" class="btn-tertiary">Enroll next face</button>
              </div>
              <div id="enrollStatus" class="enroll-status"></div>
              <ul id="enrolledFacesList"></ul>
            </div>
          </div>

""" + _INDEX_HTML_ANCHOR

_APP_JS_MESSAGE_REGISTRATIONS_ANCHOR = """ui.on_message('streaming', onStreaming);
ui.on_message('paused', onPaused);"""

_APP_JS_MESSAGE_REGISTRATIONS_INSERT = """ui.on_message('streaming', onStreaming);
ui.on_message('paused', onPaused);
ui.on_message('recognition', onRecognition);
ui.on_message('enroll_progress', onEnrollProgress);
ui.on_message('enrolled', onEnrolled);
ui.on_message('faces_list', onFacesList);"""

_APP_JS_INIT_ANCHOR = """initializeConfidenceSlider();
updateFeedback(null);
renderDetections();
updateDisplay();"""

_APP_JS_INIT_INSERT = """initializeConfidenceSlider();
initializeEnrollment();
updateFeedback(null);
renderDetections();
updateDisplay();"""

_APP_JS_POPOVER_ANCHOR = """const feedbackPopoverText =
  'An animation will appear here when the camera detects:<ul><li>Cat<li>Clock<li>Cup<li>Dog<li>Plant';"""

_APP_JS_POPOVER_INSERT = """const feedbackPopoverText =
  'Shows the most recently detected face, along with the recognition result and match score.';"""

_APP_JS_ON_DETECTION_ANCHOR = """async function onDetection(message) {
  printDetection(message);
  renderDetections();
  updateFeedback(message);
}"""

_APP_JS_ON_DETECTION_INSERT = """async function onDetection(message) {
  printDetection(message);
  renderDetections();
}"""

_APP_JS_UPDATE_FEEDBACK_ANCHOR = """function updateFeedback(detection) {
  const objectInfo = {
    cat: { text: 'Meow!', gif: 'cat.webp' },
    'cell phone': { text: 'Stay connected', gif: 'phone.webp' },
    clock: { text: 'Time to go', gif: 'clock.webp' },
    cup: { text: 'Need a break?', gif: 'cup.webp' },
    dog: { text: 'Walkies?', gif: 'dog.webp' },
    'potted plant': { text: 'Glow your ideas!', gif: 'plant.webp' },
  };

  if (detection && objectInfo[detection.content]) {
    const info = objectInfo[detection.content];
    const confidence = detection.confidence * 100;
    if (feedbackContentElement.getAttribute('data-detection') === detection.content) {
      return; // No need to update
    }
    feedbackContentElement.setAttribute('data-detection', detection.content);
    feedbackContentElement.innerHTML = `
            <div class="feedback-detection">
                <div class="percentage">${confidence.toFixed(1)}% ${detection.content}</div>
                <img src="img/${info.gif}" alt="${detection.content}">
                <span>${info.text}</span>
            </div>
        `;
  } else if (feedbackContentElement.getAttribute('data-detection') !== 'none') {
    feedbackContentElement.setAttribute('data-detection', 'none');
    feedbackContentElement.innerHTML = `
            <img src="img/stars.svg" alt="Stars">
            <p class="feedback-text">System response will appear here</p>
        `;
  }
}"""

_APP_JS_UPDATE_FEEDBACK_INSERT = r"""function updateFeedback(recognition) {
  if (!recognition) {
    feedbackContentElement.setAttribute('data-detection', 'none');
    feedbackContentElement.innerHTML = `
            <img src="img/stars.svg" alt="Stars">
            <p class="feedback-text">System response will appear here</p>
        `;
    return;
  }

  const label = recognition.granted ? `${recognition.name} - Access granted` : 'Unknown';
  const scorePct = (recognition.score * 100).toFixed(1);
  const statusClass = recognition.granted ? 'granted' : 'denied';

  feedbackContentElement.setAttribute('data-detection', label);
  feedbackContentElement.innerHTML = `
        <div class="feedback-detection">
            <img src="data:image/jpeg;base64,${recognition.thumbnail}" alt="${label}">
            <div class="percentage">${scorePct}%</div>
            <span class="feedback-status ${statusClass}">${label}</span>
        </div>
    `;
}

function onRecognition(recognition) {
  updateEnrollStatus(recognition);
  updateFeedback(recognition);
}

function onEnrollProgress(message) {
  const enrollStatusElement = document.getElementById('enrollStatus');
  enrollStatusElement.className = 'enroll-status';
  enrollStatusElement.textContent = `Capturing "${message.name}": ${message.count}/${message.required}`;
}

function onEnrolled(message) {
  const enrollStatusElement = document.getElementById('enrollStatus');
  enrollStatusElement.className = 'enroll-status granted';
  enrollStatusElement.textContent = `Enrolled "${message.name}"`;
  document.getElementById('enrollNameInput').value = '';
}

function onFacesList(message) {
  renderEnrolledFaces(message.names || []);
}

function initializeEnrollment() {
  const enrollButton = document.getElementById('enrollButton');
  const enrollNameInput = document.getElementById('enrollNameInput');

  enrollButton.addEventListener('click', () => {
    const name = enrollNameInput.value.trim();
    if (!name) return;
    ui.send_message('enroll_face', { name });
    const enrollStatusElement = document.getElementById('enrollStatus');
    enrollStatusElement.className = 'enroll-status';
    enrollStatusElement.textContent = `Show the face for "${name}" to the camera...`;
  });
}

function updateEnrollStatus(recognition) {
  const enrollStatusElement = document.getElementById('enrollStatus');
  if (recognition.granted) {
    enrollStatusElement.className = 'enroll-status granted';
    enrollStatusElement.textContent = `${recognition.name} - Access granted`;
  } else {
    enrollStatusElement.className = 'enroll-status denied';
    enrollStatusElement.textContent = 'Unknown';
  }
}

function renderEnrolledFaces(names) {
  const enrolledFacesListElement = document.getElementById('enrolledFacesList');
  enrolledFacesListElement.innerHTML = '';

  if (names.length === 0) {
    enrolledFacesListElement.innerHTML = '<li class="empty-list">No faces enrolled yet</li>';
    return;
  }

  names.forEach(name => {
    const item = document.createElement('li');

    const nameSpan = document.createElement('span');
    nameSpan.textContent = name;

    const deleteButton = document.createElement('button');
    deleteButton.className = 'enrolled-face-delete';
    deleteButton.textContent = '✕';
    deleteButton.addEventListener('click', () => {
      ui.send_message('delete_face', { name });
    });

    item.appendChild(nameSpan);
    item.appendChild(deleteButton);
    enrolledFacesListElement.appendChild(item);
  });
}"""

_STYLE_CSS_APPEND_MARKER = "/* Face enrollment + recognition feedback (Startup-Demos addition) */"

_STYLE_CSS_APPEND = """
""" + _STYLE_CSS_APPEND_MARKER + """
.enroll-controls {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

#enrollNameInput {
  flex: 1;
  min-width: 0;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #c9d2d2;
  font-size: 13px;
  font-family: 'Open Sans';
}

.enroll-status {
  font-size: 12px;
  min-height: 16px;
  color: #5d6a6b;
  margin-bottom: 8px;
}

.enroll-status.granted { color: #16a588; font-weight: 700; }
.enroll-status.verifying { color: #b8860b; font-weight: 700; }
.enroll-status.denied { color: #c0392b; font-weight: 700; }

#enrolledFacesList {
  list-style: none;
  padding: 0;
  margin: 0;
}

#enrolledFacesList li {
  border-top: 1px solid #e5eaea;
  font-size: 13px;
  padding: 8px 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.enrolled-face-delete {
  cursor: pointer;
  background: none;
  border: none;
  color: #c0392b;
  font-size: 14px;
  padding: 0 4px;
}

.feedback-status {
  font-size: 12px;
  font-weight: 700;
}

.feedback-status.granted { color: #16a588; }
.feedback-status.verifying { color: #b8860b; }
.feedback-status.denied { color: #c0392b; }

.empty-list {
  text-align: center;
  color: #5d6a6b;
  padding: 16px 0;
}
"""


def _read(assets_dir: str, filename: str) -> str:
    with open(os.path.join(assets_dir, filename), "r", encoding="utf-8") as f:
        return f.read()


def _patch(content: str, anchor: str, insert: str, filename: str) -> str:
    """Replace anchor with insert, idempotently.

    If insert is already present, the patch was already applied by a previous run --
    leave content untouched. Otherwise the anchor must be found exactly once (Arduino's
    original template); anything else means the template drifted from what these
    patches expect.
    """
    if insert in content:
        return content
    if content.count(anchor) != 1:
        raise RuntimeError(
            f"webui_assets: expected exactly one occurrence of an anchor in {filename}, "
            f"found {content.count(anchor)}. The Arduino template may have changed."
        )
    return content.replace(anchor, insert)


def _build_index_html(assets_dir: str) -> str:
    content = _read(assets_dir, "index.html")
    return _patch(content, _INDEX_HTML_ANCHOR, _INDEX_HTML_INSERT, "index.html")


def _build_app_js(assets_dir: str) -> str:
    content = _read(assets_dir, "app.js")
    content = _patch(content, _APP_JS_MESSAGE_REGISTRATIONS_ANCHOR, _APP_JS_MESSAGE_REGISTRATIONS_INSERT, "app.js")
    content = _patch(content, _APP_JS_INIT_ANCHOR, _APP_JS_INIT_INSERT, "app.js")
    content = _patch(content, _APP_JS_POPOVER_ANCHOR, _APP_JS_POPOVER_INSERT, "app.js")
    content = _patch(content, _APP_JS_ON_DETECTION_ANCHOR, _APP_JS_ON_DETECTION_INSERT, "app.js")
    content = _patch(content, _APP_JS_UPDATE_FEEDBACK_ANCHOR, _APP_JS_UPDATE_FEEDBACK_INSERT, "app.js")
    return content


def _build_style_css(assets_dir: str) -> str:
    content = _read(assets_dir, "style.css")
    if _STYLE_CSS_APPEND_MARKER in content:
        return content
    return content + _STYLE_CSS_APPEND


def write_assets(assets_dir: str):
    """Patch index.html, app.js, and style.css in assets_dir in place.

    Starts from Arduino's own "Detect Objects on Smartphone Camera" example frontend
    (kept under its original MPL-2.0 header) and patches in the app-specific pieces
    this app needs: face enrollment UI, enrolled-faces list, and
    granted/verifying/denied recognition feedback. Called on every app startup; each
    patch is idempotent, so re-running against already-patched files is a no-op.
    """
    files = {
        "index.html": _build_index_html(assets_dir),
        "app.js": _build_app_js(assets_dir),
        "style.css": _build_style_css(assets_dir),
    }
    for filename, content in files.items():
        with open(os.path.join(assets_dir, filename), "w", encoding="utf-8") as f:
            f.write(content)
