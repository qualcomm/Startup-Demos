#===-----------------------run_agentic_pipeline.py------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===------------------------------------------------------------------------===//

# -*- coding: utf-8 -*-
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=False)
from crewai import Crew, Agent, Task
from llm.aisuite_llm import from_env
import json
import time

def _run_single(agent: Agent, task: Task, max_retries: int = 2) -> str:
    """Run a single task with better error handling"""
    for attempt in range(max_retries):
        try:
            print(f"[Agent] {agent.role} - Attempt {attempt + 1}/{max_retries}")
            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=False,
            )
            result = crew.kickoff()
            
            result_str = str(result).strip() if result else ""
            
            if result_str and result_str != "None" and len(result_str) > 5:
                print(f"[Agent] {agent.role} - Success ({len(result_str)} chars)")
                return result_str
            else:
                print(f"[Agent] {agent.role} - Empty response, retrying...")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
        except Exception as e:
            print(f"[Agent] {agent.role} - Error: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
    
    print(f"[Agent] {agent.role} - Failed, using default")
    return None

def run_agentic_pipeline(patient_name: str, vitals: dict, level_name: str, reasons: list) -> dict:
    """
    Run the complete agentic pipeline for patient analysis.
    """
    try:
        print(f"\n{'='*60}")
        print(f"[Pipeline] Patient: {patient_name} | Level: {level_name}")
        print(f"[Pipeline] Vitals: HR={vitals.get('heart_rate')}, SpO2={vitals.get('spo2')}, Temp={vitals.get('temperature')}")
        print(f"{'='*60}")
        
        llm = from_env()
    except ValueError as e:
        print(f"[Pipeline] LLM Configuration Error: {str(e)}")
        return {
            "level_decision": "GOOD",
            "reasons": ["LLM not configured"],
            "monitor_summary": "LLM configuration error",
            "nurse_summary": "LLM configuration error",
            "doctor_report": "LLM configuration error",
            "nurse_followup": "LLM configuration error",
        }
    
    # =========================================================
    # FOR GOOD LEVEL - RETURN GOOD STATUS
    # =========================================================
    if level_name == "GOOD":
        print(f"[Pipeline] Patient is GOOD - returning good status")
        return {
            "level_decision": "GOOD",
            "reasons": ["All vitals normal and stable"],
            "monitor_summary": "Patient vitals are within normal range. Continue routine monitoring.",
            "nurse_summary": "Patient is stable. Continue standard care protocol.",
            "doctor_report": "Patient status is good. All vital signs are normal. Continue current treatment plan.",
            "nurse_followup": "Maintain routine monitoring schedule. No escalation needed.",
        }
    
    # =========================================================
    # FOR LOW/MODERATE/HIGH - RUN LLM AGENTS
    # =========================================================
    
    # =========================================================
    # AGENTS
    # =========================================================
    classifier = Agent(
        role="Clinical Classifier",
        goal="Classify patient alert level",
        backstory="Medical expert who classifies patient severity",
        llm=llm,
        verbose=False,
    )
    
    monitor = Agent(
        role="Vital Monitor",
        goal="Analyze vital signs",
        backstory="Nurse who monitors patient vitals",
        llm=llm,
        verbose=False,
    )
    
    nurse = Agent(
        role="Nurse",
        goal="Provide nursing actions",
        backstory="Experienced nurse",
        llm=llm,
        verbose=False,
    )
    
    doctor = Agent(
        role="Doctor",
        goal="Provide clinical assessment",
        backstory="Physician",
        llm=llm,
        verbose=False,
    )
    
    followup = Agent(
        role="Nurse Coordinator",
        goal="Coordinate care",
        backstory="Care coordinator",
        llm=llm,
        verbose=False,
    )
    
    # =========================================================
    # TASKS
    # =========================================================
    
    t_classify = Task(
        description=(
            f"Patient: {patient_name}\n"
            f"Heart Rate: {vitals.get('heart_rate')} bpm\n"
            f"SpO2: {vitals.get('spo2')}%\n"
            f"Temperature: {vitals.get('temperature')}C\n\n"
            "Classify this patient's alert level as GOOD, LOW, MODERATE, or HIGH.\n"
            "Return ONLY: {\"level\": \"GOOD\", \"reasons\": [\"reason1\"]}"
        ),
        expected_output="JSON classification",
        agent=classifier,
    )
    
    t_monitor = Task(
        description=(
            f"Patient: {patient_name}\n"
            f"HR: {vitals.get('heart_rate')} | SpO2: {vitals.get('spo2')}% | Temp: {vitals.get('temperature')}C\n"
            f"Alert Level: {level_name}\n\n"
            "Provide 2-3 key monitoring points for this patient."
        ),
        expected_output="Monitoring recommendations",
        agent=monitor,
    )
    
    t_nurse = Task(
        description=(
            f"Patient: {patient_name}\n"
            f"Alert Level: {level_name}\n"
            f"Vitals: HR={vitals.get('heart_rate')}, SpO2={vitals.get('spo2')}%, Temp={vitals.get('temperature')}C\n\n"
            "What should the nurse do? Provide action and next check time."
        ),
        expected_output="Nursing action",
        agent=nurse,
    )
    
    t_doctor = Task(
        description=(
            f"Patient: {patient_name}\n"
            f"Alert Level: {level_name}\n"
            f"Vitals: HR={vitals.get('heart_rate')}, SpO2={vitals.get('spo2')}%, Temp={vitals.get('temperature')}C\n\n"
            "Provide a brief clinical assessment and recommendations."
        ),
        expected_output="Clinical assessment",
        agent=doctor,
    )
    
    # =========================================================
    # RUN CLASSIFICATION FIRST
    # =========================================================
    print(f"[Pipeline] Running classifier...")
    classify_out = _run_single(classifier, t_classify)
    
    level_decision = level_name
    classification_reasons = reasons
    
    if classify_out:
        try:
            classify_data = json.loads(classify_out)
            level_decision = classify_data.get("level", level_name).upper()
            classification_reasons = classify_data.get("reasons", reasons)
            print(f"[Pipeline] Classification: {level_decision}")
        except json.JSONDecodeError:
            classify_out_upper = classify_out.upper()
            if "HIGH" in classify_out_upper:
                level_decision = "HIGH"
            elif "MODERATE" in classify_out_upper:
                level_decision = "MODERATE"
            elif "LOW" in classify_out_upper:
                level_decision = "LOW"
            else:
                level_decision = level_name
            classification_reasons = [classify_out[:80]]
    
    # =========================================================
    # RUN OTHER AGENTS
    # =========================================================
    print(f"[Pipeline] Running monitor agent...")
    monitor_out = _run_single(monitor, t_monitor)
    if not monitor_out:
        if level_name == "HIGH":
            monitor_out = "CRITICAL: Continuous monitoring required. Watch for any deterioration."
        elif level_name == "MODERATE":
            monitor_out = "Increased monitoring needed. Check vitals every 10 minutes."
        elif level_name == "LOW":
            monitor_out = "Monitor closely. Check vitals every 20 minutes."
        else:
            monitor_out = "Routine monitoring. Check vitals every 30 minutes."
    
    print(f"[Pipeline] Running nurse agent...")
    nurse_out = _run_single(nurse, t_nurse)
    if not nurse_out:
        if level_name == "HIGH":
            nurse_out = "ESCALATE immediately to doctor. Prepare for emergency intervention. Continuous monitoring required."
        elif level_name == "MODERATE":
            nurse_out = "Alert doctor immediately. Increase monitoring frequency. Prepare for possible intervention."
        elif level_name == "LOW":
            nurse_out = "Add to watchlist. Increase monitoring frequency to every 20 minutes. Report any changes."
        else:
            nurse_out = "Continue routine monitoring every 30 minutes."
    
    print(f"[Pipeline] Running doctor agent...")
    doctor_out = _run_single(doctor, t_doctor)
    if not doctor_out:
        if level_name == "HIGH":
            doctor_out = "CRITICAL CONDITION: Patient requires immediate intervention. Consider ICU admission. Continuous monitoring and aggressive treatment needed."
        elif level_name == "MODERATE":
            doctor_out = "Patient shows significant concerns. Recommend close observation and possible intervention. May require hospitalization."
        elif level_name == "LOW":
            doctor_out = "Patient shows minor concerns. Continue current treatment and increase monitoring frequency."
        else:
            doctor_out = "Patient stable. Continue routine care and monitoring."
    
    # =========================================================
    # RUN FOLLOW-UP
    # =========================================================
    print(f"[Pipeline] Running follow-up agent...")
    t_followup = Task(
        description=(
            f"Doctor's assessment:\n{doctor_out}\n\n"
            "Provide nurse action checklist based on doctor's assessment."
        ),
        expected_output="Nurse checklist",
        agent=followup,
    )
    
    followup_out = _run_single(followup, t_followup)
    if not followup_out:
        if level_name == "HIGH":
            followup_out = "1. Notify doctor immediately\n2. Prepare for emergency transfer\n3. Continuous vital monitoring\n4. Document all changes\n5. Prepare emergency equipment"
        elif level_name == "MODERATE":
            followup_out = "1. Alert doctor\n2. Increase monitoring to every 10 minutes\n3. Prepare intervention equipment\n4. Document status changes\n5. Keep family informed"
        elif level_name == "LOW":
            followup_out = "1. Add to watchlist\n2. Monitor every 20 minutes\n3. Report any deterioration\n4. Document findings\n5. Continue current care"
        else:
            followup_out = "1. Continue routine care\n2. Monitor every 30 minutes\n3. Document vitals\n4. Report any changes"
    
    print(f"[Pipeline] Completed for {patient_name}\n")
    
    return {
        "level_decision": level_decision,
        "reasons": classification_reasons,
        "monitor_summary": monitor_out,
        "nurse_summary": nurse_out,
        "doctor_report": doctor_out,
        "nurse_followup": followup_out,
    }

