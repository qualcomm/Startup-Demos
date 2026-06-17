//===-----------------------app.js------------------------------------------===//
// Part of the Startup-Demos Project, under the MIT License
// See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
// for license information.
// Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
// SPDX-License-Identifier: MIT License
//===------------------------------------------------------------------------===/

const grid = document.getElementById("patientsGrid");
const lastUpdateEl = document.getElementById("lastUpdate");
const connStatusEl = document.getElementById("connStatus");

function badgeClass(levelName){
    const x = (levelName || "").toUpperCase();
    if (x === "GOOD") return "good";
    if (x === "LOW") return "low";
    if (x === "MODERATE") return "moderate";
    if (x === "HIGH") return "high";
    return "";
}

function fmt(v, suffix=""){
    if (v === null || v === undefined) return "--";
    return `${v}${suffix}`;
}

function shouldShowDoctorBox(p){
    const lvl = (p.level_name || "").toUpperCase();
    const nurse = (p.nurse_alert || p.nurse_action || "").toUpperCase();
    const hasDoctorText = (p.doctor_report || p.doctor_note || "").trim().length > 0;
    return (lvl === "MODERATE" || lvl === "HIGH" || nurse.includes("ALERT") || nurse.includes("ESCALATE") || hasDoctorText);
}

function makeCard(pid){
    const card = document.createElement("div");
    card.className = "card";
    card.id = `card_${pid}`;
    card.innerHTML = `
        <div class="cardHeader">
            <div>
                <p class="patientName" id="${pid}_name">Patient</p>
                <div class="patientId">${pid}</div>
            </div>
            <div class="badge" id="${pid}_badge">--</div>
        </div>
        
        <div class="vitals">
            <div class="metric">
                <div class="label">Heart Rate</div>
                <div class="value" id="${pid}_hr">--</div>
            </div>
            <div class="metric">
                <div class="label">SpO2</div>
                <div class="value" id="${pid}_spo2">--</div>
            </div>
            <div class="metric">
                <div class="label">Temp</div>
                <div class="value" id="${pid}_temp">--</div>
            </div>
        </div>
        
        <div class="section">
            <div class="sectionTitle">
                <div>Agentic Classification</div>
                <div class="small" id="${pid}_reasons">--</div>
            </div>
            <pre id="${pid}_classification">--</pre>
        </div>
        
        <div class="section">
            <div class="sectionTitle">
                <div>Monitor Summary</div>
                <div class="small">Risk Analysis</div>
            </div>
            <pre id="${pid}_monitor">--</pre>
        </div>
        
        <div class="section">
            <div class="sectionTitle">
                <div>Nurse Agent</div>
                <div class="small">Action and Alert</div>
            </div>
            <pre id="${pid}_nurse">--</pre>
        </div>
        
        <div class="section hidden" id="${pid}_doctorBox">
            <div class="sectionTitle">
                <div>Doctor Agent Report</div>
                <div class="small">Visible on escalation</div>
            </div>
            <pre id="${pid}_doctor">--</pre>
            <div style="height:8px"></div>
            <div class="sectionTitle">
                <div>Nurse Follow-up</div>
                <div class="small">Doctor to Nurse loop</div>
            </div>
            <pre id="${pid}_followup">--</pre>
        </div>
    `;
    return card;
}

function ensureCards(patientIds){
    grid.innerHTML = "";
    patientIds.forEach(pid => grid.appendChild(makeCard(pid)));
}

async function refresh(){
    try{
        connStatusEl.innerText = "Status: Online";
        connStatusEl.classList.remove("muted");
        
        const res = await fetch("/api/latest", { cache: "no-store" });
        const data = await res.json();
        
        const patients = data.patients || {};
        const patientIds = Object.keys(patients);
        
        if (grid.children.length === 0){
            ensureCards(patientIds.length ? patientIds : ["P1","P2","P3","P4"]);
        }
        
        lastUpdateEl.innerText = `Last update: ${data.last_update_ts || "--"}`;
        
        for (const pid of Object.keys(patients)){
            const p = patients[pid];
            
            const badge = document.getElementById(`${pid}_badge`);
            const lvl = (p.level_name || "--").toUpperCase();
            badge.innerText = lvl;
            badge.className = `badge ${badgeClass(lvl)}`;
            
            document.getElementById(`${pid}_name`).innerText = p.name || pid;
            document.getElementById(`${pid}_hr`).innerText   = fmt(p.vitals?.heart_rate, "");
            document.getElementById(`${pid}_spo2`).innerText = fmt(p.vitals?.spo2, "%");
            document.getElementById(`${pid}_temp`).innerText = fmt(p.vitals?.temperature, "C");
            
            const reasons = (p.reasons || []).join(" | ");
            document.getElementById(`${pid}_reasons`).innerText = reasons || "Analyzing...";
            
            const classificationText = p.classification_summary || 
                `Level: ${lvl}\nReasons: ${reasons || "Stable"}`;
            document.getElementById(`${pid}_classification`).innerText = classificationText;
            
            const monitorText = p.monitor_summary || "--";
            document.getElementById(`${pid}_monitor`).innerText = monitorText;
            
            const nurseText = p.nurse_summary || p.nurse_alert || p.nurse_action || "--";
            document.getElementById(`${pid}_nurse`).innerText = nurseText;
            
            const doctorBox = document.getElementById(`${pid}_doctorBox`);
            if (shouldShowDoctorBox(p)){
                doctorBox.classList.remove("hidden");
                document.getElementById(`${pid}_doctor`).innerText =
                    p.doctor_report || p.doctor_note || "--";
                document.getElementById(`${pid}_followup`).innerText =
                    p.nurse_followup || "--";
            } else {
                doctorBox.classList.add("hidden");
            }
        }
    } catch (e){
        connStatusEl.innerText = "Status: Offline";
        connStatusEl.classList.add("muted");
        console.error("Fetch error:", e);
    }
}

refresh();
setInterval(refresh, 2000);

