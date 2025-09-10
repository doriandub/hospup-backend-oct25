'use client'

import React, { useState, useRef, useCallback, useEffect } from 'react'
import { Play, Pause, Type, Copy, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface VideoSlot {
  id: string
  order: number
  duration: number
  description: string
  start_time: number
  end_time: number
  assignedVideo?: {
    title: string
    thumbnail_url: string
  }
}

interface TextOverlay {
  id: string
  content: string
  start_time: number
  end_time: number
  position: { x: number; y: number; anchor: string }
  style: {
    font_family: string
    font_size: number
    color: string
    bold: boolean
    italic: boolean
    shadow: boolean
    outline: boolean
    background: boolean
    opacity: number
  }
  textAlign?: 'left' | 'center' | 'right'
}

interface CanvasVideoEditorMasterclassProps {
  videoSlots: VideoSlot[]
  textOverlays: TextOverlay[]
  setTextOverlays: (overlays: TextOverlay[]) => void
  selectedTextId: string | null
  setSelectedTextId: (id: string | null) => void
  currentTime: number
  totalDuration: number
  onTimeChange: (time: number) => void
  onPlay?: () => void
  onPause?: () => void
  isPlaying?: boolean
  editorWidth?: number
  editorHeight?: number
}

export function CanvasVideoEditorMasterclass({
  videoSlots,
  textOverlays,
  setTextOverlays,
  selectedTextId,
  setSelectedTextId,
  currentTime,
  totalDuration,
  onTimeChange,
  onPlay,
  onPause,
  isPlaying = false,
  editorWidth = 270,
  editorHeight = 480
}: CanvasVideoEditorMasterclassProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  
  // Get current background based on time
  const getCurrentBackgroundImage = useCallback((time: number) => {
    for (const slot of videoSlots) {
      if (time >= slot.start_time && time < slot.end_time) {
        if (slot.assignedVideo?.thumbnail_url) {
          return slot.assignedVideo.thumbnail_url
        }
      }
    }
    return null
  }, [videoSlots])

  // Get visible texts at current time
  const getVisibleTexts = useCallback((time: number) => {
    return textOverlays.filter(text => 
      time >= text.start_time && time <= text.end_time
    )
  }, [textOverlays])

  // Canvas drawing
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Set canvas size
    canvas.width = editorWidth
    canvas.height = editorHeight

    // Clear canvas
    ctx.fillStyle = '#1a1a1a'
    ctx.fillRect(0, 0, editorWidth, editorHeight)

    // Draw background if available
    const backgroundUrl = getCurrentBackgroundImage(currentTime)
    if (backgroundUrl) {
      const img = new Image()
      img.onload = () => {
        ctx.drawImage(img, 0, 0, editorWidth, editorHeight)
        drawTexts() // Draw texts after background loads
      }
      img.src = backgroundUrl
    } else {
      drawTexts() // Draw texts on solid background
    }

    function drawTexts() {
      const visibleTexts = getVisibleTexts(currentTime)
      
      visibleTexts.forEach(text => {
        ctx.save()
        
        // Set text style
        ctx.font = `${text.style.bold ? 'bold ' : ''}${text.style.font_size}px ${text.style.font_family}`
        ctx.fillStyle = text.style.color
        ctx.globalAlpha = text.style.opacity / 100
        
        // Calculate position
        const x = (text.position.x / 100) * editorWidth
        const y = (text.position.y / 100) * editorHeight
        
        // Add text effects
        if (text.style.shadow) {
          ctx.shadowColor = 'rgba(0,0,0,0.5)'
          ctx.shadowBlur = 4
          ctx.shadowOffsetX = 2
          ctx.shadowOffsetY = 2
        }
        
        if (text.style.outline) {
          ctx.strokeStyle = '#000000'
          ctx.lineWidth = 2
          ctx.strokeText(text.content, x, y)
        }
        
        if (text.style.background) {
          const metrics = ctx.measureText(text.content)
          const padding = 8
          ctx.fillStyle = 'rgba(0,0,0,0.7)'
          ctx.fillRect(
            x - padding, 
            y - text.style.font_size - padding,
            metrics.width + padding * 2,
            text.style.font_size + padding * 2
          )
          ctx.fillStyle = text.style.color
        }
        
        // Draw text
        ctx.fillText(text.content, x, y)
        
        // Highlight selected text
        if (text.id === selectedTextId) {
          ctx.strokeStyle = '#ff914d'
          ctx.lineWidth = 2
          ctx.setLineDash([5, 5])
          const metrics = ctx.measureText(text.content)
          ctx.strokeRect(
            x - 4, 
            y - text.style.font_size - 4,
            metrics.width + 8,
            text.style.font_size + 8
          )
        }
        
        ctx.restore()
      })
    }
  }, [currentTime, videoSlots, textOverlays, selectedTextId, editorWidth, editorHeight, getCurrentBackgroundImage, getVisibleTexts])

  const handleCanvasClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    // Convert to percentage
    const xPercent = (x / editorWidth) * 100
    const yPercent = (y / editorHeight) * 100

    const visibleTexts = getVisibleTexts(currentTime)
    
    // Check if clicking on existing text
    for (const text of visibleTexts) {
      const textX = (text.position.x / 100) * editorWidth
      const textY = (text.position.y / 100) * editorHeight
      
      // Simple hit test
      if (Math.abs(x - textX) < 100 && Math.abs(y - textY) < 30) {
        setSelectedTextId(text.id)
        return
      }
    }

    // Deselect if clicking on empty area
    setSelectedTextId(null)
  }, [currentTime, editorWidth, editorHeight, getVisibleTexts, setSelectedTextId])

  return (
    <div className="flex flex-col items-center space-y-4">
      {/* Canvas Preview */}
      <div className="relative">
        <canvas
          ref={canvasRef}
          width={editorWidth}
          height={editorHeight}
          className="border border-gray-300 rounded-lg cursor-pointer bg-black"
          onClick={handleCanvasClick}
          style={{ width: editorWidth, height: editorHeight }}
        />
        
        {/* Play/Pause overlay */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          {!isPlaying && (
            <div className="bg-black/50 rounded-full p-4">
              <Play className="w-8 h-8 text-white" />
            </div>
          )}
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center space-x-2">
        <Button
          size="sm"
          onClick={isPlaying ? onPause : onPlay}
          className="flex items-center space-x-1"
        >
          {isPlaying ? (
            <>
              <Pause className="w-4 h-4" />
              <span>Pause</span>
            </>
          ) : (
            <>
              <Play className="w-4 h-4" />
              <span>Play</span>
            </>
          )}
        </Button>
      </div>
      
      {/* Time display */}
      <div className="text-sm text-gray-600">
        {currentTime.toFixed(1)}s / {totalDuration.toFixed(1)}s
      </div>
    </div>
  )
}