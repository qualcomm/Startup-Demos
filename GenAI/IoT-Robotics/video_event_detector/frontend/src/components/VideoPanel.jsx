/*
 *===--VideoPanel.jsx----------------------------------------------------===//
 * Part of the Startup-Demos Project, under the MIT License
 * See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
 * for license information.
 * Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
 * SPDX-License-Identifier: MIT
 *===----------------------------------------------------------------------===//
 */

import { useState } from 'react'
import { formatTime } from '../utils/time'

export default function VideoPanel({
  videoRef,
  videoUrl,
  isAnalyzing,
  currentTime,
  duration,
  onLoadedMetadata,
  onTimeUpdate,
  analysisFrame,
}) {
  const [mediaAspectRatio, setMediaAspectRatio] = useState(16 / 9)
  const showingPreview = isAnalyzing && Boolean(analysisFrame?.frame_preview)

  function handleMetadataLoaded(event) {
    const { videoWidth, videoHeight } = event.currentTarget
    if (videoWidth > 0 && videoHeight > 0) {
      setMediaAspectRatio(videoWidth / videoHeight)
    }
    onLoadedMetadata(event)
  }

  function handlePreviewLoaded(event) {
    const { naturalWidth, naturalHeight } = event.currentTarget
    if (naturalWidth > 0 && naturalHeight > 0) {
      setMediaAspectRatio(naturalWidth / naturalHeight)
    }
  }

  if (!videoUrl) {
    return (
      <section className="video-shell empty">
        <div className="video-stage">
          <div className="empty-state">
            <p className="eyebrow">Upload a video</p>
            <h1>Detect prompt-defined events in any video.</h1>
            <p>Upload a video, describe the event you care about, and review the matching moments as yes-or-no detections across sampled frames.</p>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="video-shell">
      {showingPreview ? (
        <div className="analysis-preview">
          <div className="video-stage">
            <div className="media-box" style={{ aspectRatio: mediaAspectRatio }}>
              <img
                className="analysis-preview-image"
                src={analysisFrame.frame_preview}
                alt="Current frame under analysis"
                onLoad={handlePreviewLoaded}
              />
            </div>
          </div>
          <div className="analysis-preview-copy">
            <span>Analyzing frame {analysisFrame.frame_num}</span>
            <span>{formatTime(analysisFrame.timestamp)}</span>
          </div>
        </div>
      ) : (
        <div className="video-stage">
          <div className="media-box" style={{ aspectRatio: mediaAspectRatio }}>
            <video
              ref={videoRef}
              className="video-player"
              src={videoUrl}
              controls
              playsInline
              onLoadedMetadata={handleMetadataLoaded}
              onTimeUpdate={onTimeUpdate}
            />
          </div>
        </div>
      )}
      <div className="video-meta">
        <span>{formatTime(currentTime)}</span>
        <span>{showingPreview ? 'Current analysis frame' : formatTime(duration)}</span>
      </div>
    </section>
  )
}
