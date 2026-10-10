/*
 *===--ConfigPanel.jsx---------------------------------------------------===//
 * Part of the Startup-Demos Project, under the MIT License
 * See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
 * for license information.
 * Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
 * SPDX-License-Identifier: MIT
 *===----------------------------------------------------------------------===//
 */

export default function ConfigPanel({
  prompt,
  frameGap,
  tolerance,
  isUploading,
  isAnalyzing,
  progress,
  hasVideo,
  fileName,
  canExport,
  resultsCount,
  groupedCount,
  error,
  onPromptChange,
  onFrameGapChange,
  onToleranceChange,
  onUpload,
  onAnalyze,
  onExport,
}) {
  const isBusy = isUploading || isAnalyzing

  return (
    <aside className="config-panel">
      <div className="panel-header">
        <h2>Event Detection</h2>
      </div>

      <div className="field">
        <span>Video</span>
        <label className={`file-row${isBusy ? ' disabled' : ''}`}>
          <input type="file" accept="video/*" onChange={onUpload} disabled={isBusy} hidden />
          <span className="file-button">Choose file</span>
          <span className="file-name">{fileName || 'No file chosen'}</span>
          {isUploading ? <span className="spinner" aria-hidden="true" /> : null}
        </label>
      </div>

      <label className="field">
        <span>Event prompt</span>
        <textarea value={prompt} onChange={(event) => onPromptChange(event.target.value)} rows={4} disabled={!hasVideo || isBusy} />
      </label>

      <div className="field-grid">
        <label className="field">
          <span>Sample every</span>
          <input
            type="number"
            min="1"
            value={frameGap}
            title="Process one frame after skipping this many frames between samples. Lower values increase accuracy but take longer."
            onChange={(event) => onFrameGapChange(event.target.value)}
            disabled={!hasVideo || isBusy}
          />
        </label>

        <label className="field">
          <span>Gap tolerance</span>
          <input
            type="number"
            min="0"
            value={tolerance}
            title="Allows this many consecutive no results inside a detected event before splitting it into a new event."
            onChange={(event) => onToleranceChange(event.target.value)}
            disabled={!hasVideo || isBusy}
          />
        </label>
      </div>

      <div className="action-row">
        <button className="primary-button" onClick={onAnalyze} disabled={!hasVideo || isBusy}>
          {isAnalyzing ? 'DetectingÃ¢â‚¬Â¦' : 'Detect Events'}
        </button>
        <button className="secondary-button" onClick={onExport} disabled={!canExport || isBusy}>
          Export CSV
        </button>
      </div>

      <div className="results-section">
        <div className="progress-block" aria-live="polite">
          <div className="progress-copy">
            <span>Progress</span>
            <span>{progress.total ? `${progress.current}/${progress.total}` : 'Idle'}</span>
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${progress.percent || 0}%` }} />
          </div>
        </div>

        <div className="progress-block status-card">
          <div className="progress-copy status-copy">
            <span>Frames</span>
            <span>{resultsCount ? `${resultsCount} analyzed` : 'None yet'}</span>
          </div>
          <div className="progress-copy status-copy">
            <span>Events</span>
            <span>{groupedCount ? `${groupedCount} detected` : 'None detected'}</span>
          </div>
          {error ? <p className="error-text">{error}</p> : null}
        </div>
      </div>
    </aside>
  )
}
