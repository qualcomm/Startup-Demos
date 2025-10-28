#===--llm_utils.py---------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import requests
import json

def extract_with_llm(transcription, stations, api_url, api_key):
    prompt = f"""
You are a smart ticket booking assistant.

User said:
\"{transcription}\"

Here is a list of valid cities:
{', '.join(stations)}

Your task:
1. Correct any spelling or recognition errors in the transcription.
2. Understand directional phrases like:
   - \"from X to Y\"
   - \"to Y from X\"
   - \"go to Y\" (assume source is Bengaluru if not mentioned)
   - \"from X\" (destination is missing)
   - \"X to Y\" (X is source, Y is destination)
3. Extract the **source city**, **destination city**, and **number of tickets**.
4. The number may be spoken as a digit (e.g., '2') or as a word (e.g., 'ten'). Convert it to an integer.
5. If the source is not mentioned, assume \"Bengaluru\".
6. If the destination is not mentioned, return null.
7. If the ticket count is not mentioned, assume 1.
8. Return the result in **strict JSON format only**, like:
{{"source": "Chennai", "destination": "Pune", "ticket_count": 2}}
9. Do not include any explanation or extra text. Only return the JSON.
"""

    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "message": prompt,
        "mode": "chat",
        "sessionId": "voice-session-001",
        "attachments": [],
        "reset": False
    }

    try:
        response = requests.post(api_url, headers=headers, json=data)
        if response.status_code != 200:
            print("⚠️ LLM API error:", response.status_code, response.text)
            return None, None, 0

        result = response.json()
        source = "Bengaluru"
        destination = None
        ticket_count = 1

        if "textResponse" in result:
            try:
                json_start = result["textResponse"].find('{')
                json_end = result["textResponse"].rfind('}') + 1
                json_str = result["textResponse"][json_start:json_end]
                parsed = json.loads(json_str)
                source = parsed.get("source", "Bengaluru")
                destination = parsed.get("destination")
                ticket_count = parsed.get("ticket_count", 1)
            except Exception as e:
                print("⚠️ Failed to parse textResponse JSON:", e)
                return None, None, 0

        # Normalize and validate
        valid_stations = [s.lower() for s in stations]

        if source:
            source = source.strip()
            if source.lower() not in valid_stations:
                print(f"⚠️ Invalid source '{source}' not in station list. Defaulting to Bengaluru.")
                source = "Bengaluru"
        else:
            source = "Bengaluru"

        if destination:
            destination = destination.strip()
            if destination.lower() not in valid_stations:
                print(f"⚠️ Invalid destination '{destination}' not in station list.")
                return None, None, 0
        else:
            print("⚠️ Destination is missing.")
            return None, None, 0

        return source, destination, ticket_count

    except Exception as e:
        print("⚠️ Exception during LLM extraction:", e)
        return None, None, 0

def get_destination_insights(destination, api_url, api_key):
    prompt = f"""
You are a travel assistant. Provide detailed insights about the city '{destination}'.
Include:
1. Location & Capital Status
2. Districts & Nearby Cities
3. Historical Places to Visit
4. Weather Overview
5. Languages Spoken
6. Food & Culture
7. Safety Tips for Travelers
8. Journey Time from Bengaluru to {destination}

Respond in a readable markdown format.
"""

    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "message": prompt,
        "mode": "chat",
        "sessionId": "travel-info-session-001",
        "attachments": [],
        "reset": False
    }

    try:
        response = requests.post(api_url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            return result.get("textResponse", "No insights available.")
        else:
            return f"⚠️ Failed to fetch travel insights. Status: {response.status_code}"
    except Exception as e:
        return f"⚠️ Error during LLM travel info fetch: {e}"

