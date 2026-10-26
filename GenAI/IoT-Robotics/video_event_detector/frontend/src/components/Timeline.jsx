/*
 *===--Timeline.jsx------------------------------------------------------===//
 * Part of the Startup-Demos Project, under the MIT License
 * See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
 * for license information.
 * Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
 * SPDX-License-Identifier: MIT
 *===----------------------------------------------------------------------===//
 */

import { formatTime } from '../utils/time'

export default function Timeline({ duration, events, onSeek, disabled }) {
  return (
    <section className={`timeline-card ${disabled ? 'disabled' : ''}`}>
      <div className="timeline-header">
        <h3>Detected events</h3>
        <span>{events.length ? `${events.length} events` : 'No events yet'}</span>
      </div>
      <div
        className="timeline found-track"
        role="presentation"
        onClick={(event) => handleSeek(event, duration, onSeek, disabled)}
      >
        {events.map((segment) => {
          const left = duration > 0 ? (segment.start_time / duration) * 100 : 0
          const width = duration > 0 ? Math.max(((segment.end_time - segment.start_time) / duration) * 100, 0.6) : 0
          return (
            <button
              key={segment.event_id}
              type="button"
              className="segment segment-button"
              style={{ left: `${left}%`, width: `${width}%` }}
              title={`${formatTime(segment.start_time)} - ${formatTime(segment.end_time)} (${segment.positive_frames} hits)`}
              onClick={(event) => {
                event.stopPropagation()
                onSeek(segment.start_time)
              }}
              disabled={disabled}
            />
          )
        })}
      </div>
    </section>
  )
}

function handleSeek(event, duration, onSeek, disabled) {
  if (disabled || !duration) {
    return
  }

  const bounds = event.currentTarget.getBoundingClientRect()
  const ratio = Math.min(Math.max((event.clientX - bounds.left) / bounds.width, 0), 1)
  onSeek(ratio * duration)
}
