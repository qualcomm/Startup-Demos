//===--------------------------app.js--------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===----------------------------------------------------------------------===//


// The WebUI Brick serves Socket.IO on the same host/port as this page.
const socket = io(window.location.origin, {
  path: "/socket.io",
  transports: ["websocket", "polling"],
});

const statusEl     = document.getElementById("status");
const countEl      = document.getElementById("count");
const confidenceEl = document.getElementById("confidence");
const timestampEl  = document.getElementById("timestamp");
const alertEl      = document.getElementById("alert");
const threshEl     = document.getElementById("thresh");
const threshValEl  = document.getElementById("threshVal");
const bboxOverlay  = document.querySelector(".bbox-overlay");

// Zone elements
const zone0El      = document.getElementById("zone0");
const zone1El      = document.getElementById("zone1");
const zone2El      = document.getElementById("zone2");
const zone3El      = document.getElementById("zone3");

// Detection details elements
const detectionDetailsEl = document.getElementById("detectionDetails");
const detectionListEl    = document.getElementById("detectionList");

// --- Connection state --------------------------------------------------------
socket.on("connect", () => {
  statusEl.textContent = "Live";
  statusEl.className = "pill online";
});

socket.on("disconnect", () => {
  statusEl.textContent = "Offline";
  statusEl.className = "pill offline";
});

// --- Live detection updates from the backend ---------------------------------
socket.on("detection", (data) => {
  // Handle both old format (count) and new format (total_people_count)
  const count = data.total_people_count ?? data.count ?? 0;
  countEl.textContent      = count;
  confidenceEl.textContent = (data.confidence ?? 0) + "%";
  timestampEl.textContent  = data.timestamp ?? "--:--:--";

  // Update zone counts
  if (data.zone_counts) {
    zone0El.textContent = data.zone_counts.zone_0 ?? 0;
    zone1El.textContent = data.zone_counts.zone_1 ?? 0;
    zone2El.textContent = data.zone_counts.zone_2 ?? 0;
    zone3El.textContent = data.zone_counts.zone_3 ?? 0;
  } else {
    // Reset zones if no data
    zone0El.textContent = 0;
    zone1El.textContent = 0;
    zone2El.textContent = 0;
    zone3El.textContent = 0;
  }

  // Update detection details and bounding boxes
  if (count > 0 && data.detections && data.detections.length > 0) {
    detectionDetailsEl.style.display = "block";

    let detailsHTML = "";
    let boxesHTML = "";
    const frameWidth = data.frame_width || 640;
    const frameHeight = data.frame_height || 480;
    const overlayWidth = bboxOverlay.clientWidth;
    const overlayHeight = bboxOverlay.clientHeight;
    const scaleX = overlayWidth / frameWidth;
    const scaleY = overlayHeight / frameHeight;

    data.detections.forEach((det) => {
      const confidence = Math.round((det.confidence ?? 0) * 100);
      detailsHTML += `
        <div class="detection-item">
          <span class="detection-person">Person ${det.person_id}</span>
          <span class="detection-zone">Zone ${det.zone}</span>
          <span class="detection-confidence">${confidence}%</span>
        </div>
      `;

      if (det.bbox) {
        const x = (det.bbox.x || 0) * scaleX;
        const y = (det.bbox.y || 0) * scaleY;
        const w = (det.bbox.width || 0) * scaleX;
        const h = (det.bbox.height || 0) * scaleY;
        boxesHTML += `
          <div class="bbox" style="left:${x}px; top:${y}px; width:${w}px; height:${h}px;">
            <span class="bbox-label">${det.person_id} ${(confidence || 0)}%</span>
          </div>
        `;
      }
    });

    detectionListEl.innerHTML = detailsHTML;
    bboxOverlay.innerHTML = boxesHTML;
  } else {
    detectionDetailsEl.style.display = "none";
    detectionListEl.innerHTML = "";
    bboxOverlay.innerHTML = "";
  }

  // Update alert message
  if (count > 0) {
    alertEl.textContent = `✅ ${count} person${count > 1 ? "s" : ""} detected`;
    alertEl.classList.add("active");
  } else {
    alertEl.textContent = "No people in frame";
    alertEl.classList.remove("active");
  }
});

// Acknowledge threshold changes coming back from the backend
socket.on("threshold_ack", (data) => {
  const pct = Math.round((data.value ?? 0.5) * 100);
  threshEl.value = pct;
  threshValEl.textContent = pct + "%";
});

// --- Threshold slider -> backend ---------------------------------------------
threshEl.addEventListener("input", () => {
  const pct = parseInt(threshEl.value, 10);
  threshValEl.textContent = pct + "%";
  // Send as 0..1 to match the Brick's confidence scale
  socket.emit("override_th", { value: pct / 100 });
});
