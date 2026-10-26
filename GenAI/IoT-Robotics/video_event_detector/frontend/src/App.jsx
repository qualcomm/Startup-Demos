/*
 *===--App.jsx-----------------------------------------------------------===//
 * Part of the Startup-Demos Project, under the MIT License
 * See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
 * for license information.
 * Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
 * SPDX-License-Identifier: MIT
 *===----------------------------------------------------------------------===//
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import ConfigPanel from './components/ConfigPanel'
import Timeline from './components/Timeline'
import VideoPanel from './components/VideoPanel'

const DEFAULT_PROMPT = 'Is there a tiger in this frame ?'
const EMPTY_PROGRESS = { current: 0, total: 0, percent: 0 }

export default function App() {
  const videoRef = useRef(null)
  const eventSourceRef = useRef(null)
  const [videoId, setVideoId] = useState('')
  const [videoUrl, setVideoUrl] = useState('')
  const [duration, setDuration] = useState(0)
  const [currentTime, setCurrentTime] = useState(0)
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT)
  const [frameGap, setFrameGap] = useState('30')
  const [tolerance, setTolerance] = useState('3')
  const [results, setResults] = useState([])
  const [progress, setProgress] = useState(EMPTY_PROGRESS)
  const [isUploading, setIsUploading] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [analysisFrame, setAnalysisFrame] = useState(null)
  const [fileName, setFileName] = useState('')

  const events = useMemo(() => groupEvents(results, parseInteger(tolerance, 3)), [results, tolerance])

  useEffect(() => {
    return closeStream
  }, [])

  function closeStream() {
    eventSourceRef.current?.close()
    eventSourceRef.current = null
  }

  function resetResults() {
    setResults([])
    setProgress(EMPTY_PROGRESS)
    setAnalysisFrame(null)
  }

  function finishAnalysis(message = '') {
    closeStream()
    setIsAnalyzing(false)
    if (message) {
      setError(message)
    }
  }

  async function handleUpload(event) {
    const file = event.target.files?.[0]
    if (!file) {
      return
    }

    const formData = new FormData()
    formData.append('video', file)
    setFileName(file.name)
    setIsUploading(true)
    setError('')
    resetResults()

    try {
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      })

      const payload = await response.json()
      if (!response.ok) {
        throw new Error(payload.error || 'Upload failed.')
      }

      setVideoId(payload.video_id)
      setVideoUrl(payload.video_url)
      setDuration(payload.duration || 0)
      setCurrentTime(0)
    } catch (uploadError) {
      setError(uploadError.message)
      setFileName('')
    } finally {
      setIsUploading(false)
      event.target.value = ''
    }
  }

  function handleAnalyze() {
    if (!videoId) {
      return
    }

    closeStream()
    resetResults()
    setError('')
    setIsAnalyzing(true)

    const params = new URLSearchParams({
      prompt,
      frame_gap: String(parseInteger(frameGap, 30)),
    })
    const stream = new EventSource(`/api/analyze/${videoId}?${params.toString()}`)
    eventSourceRef.current = stream

    stream.onmessage = (message) => {
      const payload = JSON.parse(message.data)
      if (payload.type === 'result') {
        setResults((current) => [...current, payload.result])
        setProgress(payload.progress)
        setAnalysisFrame(payload.result)
        setCurrentTime(payload.result.timestamp || 0)
        return
      }
      if (payload.type === 'done') {
        finishAnalysis()
        return
      }
      if (payload.type === 'error') {
        finishAnalysis(payload.message || 'Analysis failed.')
      }
    }

    stream.onerror = () => {
      finishAnalysis('Analysis stream disconnected.')
    }
  }

  async function handleExport() {
    if (!results.length) {
      return
    }

    try {
      const response = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          results,
          tolerance: parseInteger(tolerance, 3),
        }),
      })

      if (!response.ok) {
        throw new Error('Export failed.')
      }

      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = 'video-event-detector-events.csv'
      anchor.click()
      URL.revokeObjectURL(url)
    } catch (exportError) {
      setError(exportError.message)
    }
  }

  function handleSeek(time) {
    if (!videoRef.current) {
      return
    }
    videoRef.current.currentTime = time
    setCurrentTime(time)
  }

  return (
    <main className="app-layout">
      <section className="main-column">
        <div className="video-area">
          <VideoPanel
            videoRef={videoRef}
            videoUrl={videoUrl}
            isAnalyzing={isAnalyzing}
            currentTime={currentTime}
            duration={duration}
            analysisFrame={analysisFrame}
            onLoadedMetadata={(event) => setDuration(event.currentTarget.duration || 0)}
            onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
          />
        </div>

        <div className="bottom-stack">
          <Timeline
            duration={duration}
            events={events}
            onSeek={handleSeek}
            disabled={!videoId}
          />
        </div>
      </section>

      <div className="controls-column">
        <ConfigPanel
          prompt={prompt}
          frameGap={frameGap}
          tolerance={tolerance}
          isUploading={isUploading}
          isAnalyzing={isAnalyzing}
          progress={progress}
          hasVideo={Boolean(videoId)}
          fileName={fileName}
          canExport={results.length > 0}
          resultsCount={results.length}
          groupedCount={events.length}
          error={error}
          onPromptChange={setPrompt}
          onFrameGapChange={setFrameGap}
          onToleranceChange={setTolerance}
          onUpload={handleUpload}
          onAnalyze={handleAnalyze}
          onExport={handleExport}
        />
      </div>
    </main>
  )
}

function parseInteger(value, fallback) {
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) ? parsed : fallback
}

function groupEvents(results, tolerance) {
  const events = []
  let current = null
  let gap = 0

  for (const item of [...results].sort((a, b) => a.frame_num - b.frame_num)) {
    if (item.answer) {
      if (!current) {
        current = { start_frame: item.frame_num, start_time: item.timestamp, end_frame: item.frame_num, end_time: item.timestamp, positive_frames: 1 }
      } else {
        current.end_frame = item.frame_num
        current.end_time = item.timestamp
        current.positive_frames += 1
      }
      gap = 0
    } else if (current) {
      gap += 1
      if (gap > tolerance) {
        events.push(current)
        current = null
        gap = 0
      }
    }
  }
  if (current) events.push(current)
  return events.map((e, i) => ({ ...e, event_id: i + 1 }))
}
