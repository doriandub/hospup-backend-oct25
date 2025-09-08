'use client'

import { useState } from 'react'
import { Play, Trash2, Edit, Download, Eye, Video, Building2, MapPin } from 'lucide-react'
import { Button } from '@/components/ui/button'
import Image from 'next/image'

interface VideoCardProps {
  video: {
    id: string
    title: string
    thumbnail_url?: string | null
    video_url: string
    status: string
    created_at: string
    property_id: string | number
    description?: string
    duration?: number | null
    size?: number
  }
  property?: {
    id: number
    name: string
    city?: string
    country?: string
  }
  viewMode: 'grid' | 'list'
  showProperty?: boolean
  onDelete?: (videoId: string) => void
  onEdit?: (video: any) => void
  onView?: (video: any) => void
}

export function VideoCard({ 
  video, 
  property, 
  viewMode, 
  showProperty = true,
  onDelete,
  onEdit,
  onView 
}: VideoCardProps) {
  const [imageError, setImageError] = useState(false)

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return 'Unknown size'
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    if (bytes === 0) return '0 Bytes'
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i]
  }

  const formatDuration = (duration?: number | null) => {
    if (!duration) return 'Unknown'
    const minutes = Math.floor(duration / 60)
    const seconds = duration % 60
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  }

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'completed':
      case 'ready':
        return 'bg-green-100 text-green-800'
      case 'processing':
      case 'uploaded':
        return 'bg-yellow-100 text-yellow-800'
      case 'failed':
      case 'error':
        return 'bg-red-100 text-red-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const handleView = () => {
    if (onView) {
      onView(video)
    } else {
      // Default view behavior - open video in modal or new tab
      if (video.video_url) {
        window.open(video.video_url, '_blank')
      }
    }
  }

  const handleDelete = () => {
    if (onDelete && confirm('Are you sure you want to delete this video?')) {
      onDelete(video.id)
    }
  }

  if (viewMode === 'list') {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow duration-200">
        <div className="p-4">
          <div className="flex items-center space-x-4">
            {/* Thumbnail */}
            <div className="flex-shrink-0 w-24 h-16 bg-gray-200 rounded-lg overflow-hidden relative">
              {video.thumbnail_url && !imageError ? (
                <Image
                  src={video.thumbnail_url}
                  alt={video.title}
                  fill
                  className="object-cover"
                  onError={() => setImageError(true)}
                  sizes="96px"
                />
              ) : (
                <div className="w-full h-full bg-gradient-to-br from-[#09725c]/10 to-[#ff914d]/10 flex items-center justify-center">
                  <Video className="w-6 h-6 text-gray-400" />
                </div>
              )}
              <div className="absolute inset-0 bg-black bg-opacity-20 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity cursor-pointer" onClick={handleView}>
                <Play className="w-6 h-6 text-white" />
              </div>
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <h3 className="text-lg font-semibold text-gray-900 truncate mb-1">{video.title}</h3>
                  {showProperty && property && (
                    <div className="flex items-center text-sm text-gray-600 mb-2">
                      <Building2 className="w-3 h-3 mr-1" />
                      <span className="truncate">{property.name}</span>
                      {property.city && property.country && (
                        <>
                          <MapPin className="w-3 h-3 ml-2 mr-1" />
                          <span className="truncate">{property.city}, {property.country}</span>
                        </>
                      )}
                    </div>
                  )}
                  <div className="flex items-center space-x-4 text-sm text-gray-600">
                    <span>Duration: {formatDuration(video.duration)}</span>
                    <span>Size: {formatFileSize(video.size)}</span>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(video.status)}`}>
                      {video.status}
                    </span>
                  </div>
                </div>
                <div className="flex items-center space-x-2 ml-4">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleView}
                    className="text-gray-500 hover:text-gray-700"
                  >
                    <Eye className="w-4 h-4" />
                  </Button>
                  {onEdit && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onEdit(video)}
                      className="text-gray-500 hover:text-gray-700"
                    >
                      <Edit className="w-4 h-4" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleDelete}
                    className="text-gray-500 hover:text-red-600"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Grid view
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow duration-200 overflow-hidden">
      {/* Thumbnail */}
      <div className="relative aspect-[16/9] bg-gray-100">
        {video.thumbnail_url && !imageError ? (
          <Image
            src={video.thumbnail_url}
            alt={video.title}
            fill
            className="object-cover"
            onError={() => setImageError(true)}
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 25vw"
          />
        ) : (
          <div className="w-full h-full bg-gradient-to-br from-[#09725c]/10 to-[#ff914d]/10 flex items-center justify-center">
            <div className="text-center">
              <Video className="w-12 h-12 text-gray-300 mx-auto mb-2" />
              <p className="text-gray-500 text-sm">No preview</p>
            </div>
          </div>
        )}
        <div className="absolute inset-0 bg-black bg-opacity-20 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity cursor-pointer" onClick={handleView}>
          <Play className="w-12 h-12 text-white drop-shadow-lg" />
        </div>
        
        {/* Status badge */}
        <div className="absolute top-3 left-3">
          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(video.status)}`}>
            {video.status}
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-gray-900 truncate mb-1">{video.title}</h3>
            {showProperty && property && (
              <div className="flex items-center text-sm text-gray-600 mb-2">
                <Building2 className="w-3 h-3 mr-1" />
                <span className="truncate">{property.name}</span>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-2 text-sm text-gray-600 mb-4">
          <div className="flex justify-between">
            <span>Duration:</span>
            <span>{formatDuration(video.duration)}</span>
          </div>
          <div className="flex justify-between">
            <span>Size:</span>
            <span>{formatFileSize(video.size)}</span>
          </div>
          <div className="flex justify-between">
            <span>Created:</span>
            <span>{new Date(video.created_at).toLocaleDateString()}</span>
          </div>
        </div>

        <div className="flex items-center justify-between pt-3 border-t border-gray-100">
          <Button
            variant="outline"
            size="sm"
            onClick={handleView}
            className="text-[#09725c] hover:text-[#09725c]/80"
          >
            <Play className="w-4 h-4 mr-1" />
            View
          </Button>
          <div className="flex items-center space-x-1">
            {onEdit && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onEdit(video)}
                className="text-gray-500 hover:text-gray-700"
              >
                <Edit className="w-4 h-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDelete}
              className="text-gray-500 hover:text-red-600"
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}