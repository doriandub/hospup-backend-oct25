'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Play,
  Pause,
  Video
} from 'lucide-react'

interface TemplateSlot {
  id: string
  order: number
  duration: number
  description: string
  start_time: number
  end_time: number
}

interface ContentVideo {
  id: string
  title: string
  thumbnail_url: string
  video_url: string
  duration: number
  description: string
}

interface SlotAssignment {
  slotId: string
  videoId: string | null
  confidence?: number
}

interface TimelineEditorProps {
  templateTitle: string
  templateSlots: TemplateSlot[]
  contentVideos: ContentVideo[]
  onGenerate: (assignments: SlotAssignment[], texts: any[]) => void
  propertyId: string
  templateId: string
  onAddText?: () => void
  onGenerateVideo?: () => void
  onTimelineUpdate?: (assignments: SlotAssignment[], texts: any[]) => void
  draggedVideo?: ContentVideo | null
}

export function VideoTimelineEditor({
  templateTitle,
  templateSlots,
  contentVideos,
  onGenerate,
  propertyId,
  templateId,
  onAddText,
  onGenerateVideo,
  onTimelineUpdate,
  draggedVideo
}: TimelineEditorProps) {
  const [assignments, setAssignments] = useState<SlotAssignment[]>([])
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null)
  const [dragOverSlot, setDragOverSlot] = useState<string | null>(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)

  const totalDuration = templateSlots.reduce((sum, slot) => sum + slot.duration, 0)

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const getVideoForSlot = (slotId: string): ContentVideo | null => {
    const assignment = assignments.find(a => a.slotId === slotId)
    if (!assignment?.videoId) return null
    return contentVideos.find(v => v.id === assignment.videoId) || null
  }

  const assignVideoToSlot = (slotId: string, videoId: string) => {
    const newAssignments = assignments.filter(a => a.slotId !== slotId)
    newAssignments.push({ slotId, videoId })
    setAssignments(newAssignments)
    onTimelineUpdate?.(newAssignments, [])
  }

  const canVideoFitSlot = (video: ContentVideo, slot: TemplateSlot): boolean => {
    return video.duration >= slot.duration * 0.8
  }

  return (
    <div className="h-full bg-gray-50 font-inter flex flex-col">
      {/* Main content area with video preview */}
      <div className="flex-1 flex items-center justify-center p-8">
        {/* Video Preview Area */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 max-w-4xl w-full">
          <div className="aspect-video bg-gray-900 rounded-lg flex items-center justify-center">
            <div className="text-white text-center">
              <Video className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium">Video Preview</p>
              <p className="text-sm opacity-75">Preview will be displayed here</p>
            </div>
          </div>

          {/* Play Controls */}
          <div className="flex items-center justify-center gap-4 mt-6">
            <span className="text-sm text-gray-600 min-w-[40px]">
              {formatTime(currentTime)}
            </span>

            <Button
              variant="outline"
              size="lg"
              onClick={() => setIsPlaying(!isPlaying)}
              className="flex items-center gap-2 px-6"
            >
              {isPlaying ? (
                <Pause className="w-5 h-5" />
              ) : (
                <Play className="w-5 h-5" />
              )}
              {isPlaying ? 'Pause' : 'Play'}
            </Button>

            <span className="text-sm text-gray-600 min-w-[40px]">
              {formatTime(totalDuration)}
            </span>
          </div>
        </div>
      </div>

      {/* Gray Separator with Timing */}
      <div className="border-t border-gray-300 bg-gray-100 px-8 py-2">
        <div className="flex justify-between items-center">
          <div className="text-xs text-gray-600">0s</div>
          {templateSlots.map((slot, index) => {
            const cumulativeTime = templateSlots.slice(0, index + 1).reduce((sum, s) => sum + s.duration, 0)
            return (
              <div key={slot.id} className="text-xs text-gray-600">
                {cumulativeTime.toFixed(1)}s
              </div>
            )
          })}
        </div>
      </div>

      {/* Compact Timeline at Bottom */}
      <div className="bg-white border-t border-gray-200 p-4">
        <div className="flex rounded-lg overflow-hidden border">
          {templateSlots.map((slot) => {
            const video = getVideoForSlot(slot.id)

            return (
              <div
                key={slot.id}
                className={`relative border-r border-gray-200 last:border-r-0 h-16 transition-all duration-200 ${
                  video ? 'bg-white' : 'bg-gray-100'
                } ${
                  selectedSlot === slot.id ? 'ring-2 ring-[#09725c] ring-opacity-50' : ''
                } ${
                  dragOverSlot === slot.id ? 'ring-2 ring-[#ff914d] bg-orange-50' : ''
                }`}
                style={{
                  width: `${(slot.duration / totalDuration) * 100}%`,
                  minWidth: '60px'
                }}
                onClick={() => setSelectedSlot(slot.id)}
                onDragOver={(e) => {
                  e.preventDefault()
                  setDragOverSlot(slot.id)
                }}
                onDragLeave={() => setDragOverSlot(null)}
                onDrop={(e) => {
                  e.preventDefault()
                  if (draggedVideo) {
                    if (canVideoFitSlot(draggedVideo, slot)) {
                      assignVideoToSlot(slot.id, draggedVideo.id)
                    } else {
                      alert(`This video (${draggedVideo.duration}s) is too short for this slot (${slot.duration}s)`)
                    }
                    setDragOverSlot(null)
                  }
                }}
              >
                {video ? (
                  <>
                    <img
                      src={video.thumbnail_url || '/placeholder-video.jpg'}
                      alt={video.title}
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-75 text-white px-1">
                      <p className="text-xs truncate">{formatTime(slot.duration)}</p>
                    </div>
                  </>
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-gray-500">
                    <Video className="w-4 h-4 mb-1" />
                    <p className="text-xs">{formatTime(slot.duration)}</p>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}