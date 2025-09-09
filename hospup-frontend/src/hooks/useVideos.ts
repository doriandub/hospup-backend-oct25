'use client'

import { useState, useEffect, useRef } from 'react'
import { api } from '@/lib/api'

interface Video {
  id: string
  title: string
  thumbnail_url: string | null
  file_url: string
  duration: number | null
  status: string
  created_at: string
  property_id: string | number
  description?: string
}

export function useVideos(propertyId?: string, videoType?: string) {
  const [videos, setVideos] = useState<Video[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const recoveryIntervalRef = useRef<NodeJS.Timeout | null>(null)

  const fetchVideos = async () => {
    try {
      setLoading(true)
      setError(null)
      
      // Use the dedicated API method for getting videos
      const propertyIdNumber = propertyId ? parseInt(propertyId) : undefined
      const response = await api.getVideos(propertyIdNumber, videoType) as { videos?: Video[], data?: Video[] } | Video[]
      
      // Handle different response formats from the API
      let videosData: Video[] = []
      if (Array.isArray(response)) {
        videosData = response
      } else if (response && typeof response === 'object') {
        if (Array.isArray(response.videos)) {
          videosData = response.videos
        } else if (Array.isArray(response.data)) {
          videosData = response.data
        }
      }
      
      // Debug logging for URL analysis
      if (videosData.length > 0) {
        console.log('🔍 Videos Debug Info:', {
          count: videosData.length,
          sampleVideo: videosData[0],
          allUrls: videosData.map(v => ({ id: v.id, file_url: v.file_url }))
        })
      }
      
      setVideos(videosData)
    } catch (err: any) {
      console.error('Videos fetch error:', err)
      const errorMessage = err.message || 'Failed to fetch videos'
      setError(errorMessage)
      
      // If authentication error, redirect to login
      if (err.message?.includes('401') || err.message?.includes('Not authenticated')) {
        if (typeof window !== 'undefined') {
          window.location.href = '/auth/login'
        }
      }
    } finally {
      setLoading(false)
    }
  }

  const deleteVideo = async (id: string): Promise<void> => {
    try {
      await api.delete(`/api/v1/videos/${id}`)
      setVideos(prev => prev.filter(video => video.id !== id))
    } catch (err: any) {
      throw new Error(err.message || 'Failed to delete video')
    }
  }

  // Recovery system every 90 seconds for stuck videos
  useEffect(() => {
    // Always start the recovery system
    recoveryIntervalRef.current = setInterval(async () => {
      const currentVideos = videos
      
      // Look for problematic videos
      const problematicVideos = currentVideos.filter(video => {
        const createdAt = new Date(video.created_at)
        const now = new Date()
        const minutesSinceCreation = (now.getTime() - createdAt.getTime()) / (1000 * 60)
        
        // Video in processing for more than 5 minutes = problematic
        return (video.status === 'processing' || video.status === 'uploaded') && minutesSinceCreation > 5
      })

      if (problematicVideos.length > 0) {
        // Try to restart processing
        for (const video of problematicVideos) {
          try {
            const token = localStorage.getItem('access_token')
            const response = await fetch(`/api/v1/videos/${video.id}/restart-processing`, {
              method: 'POST',
              headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
              }
            })
            
            if (!response.ok) {
              console.error(`Failed to restart video ${video.id}:`, await response.text())
            }
          } catch (error) {
            console.error(`Error restarting video ${video.id}:`, error)
          }
        }
      }
      
      // Always refetch to check statuses
      await fetchVideos()
      
    }, 90000) // 90 seconds
    
    // Cleanup
    return () => {
      if (recoveryIntervalRef.current) {
        clearInterval(recoveryIntervalRef.current)
        recoveryIntervalRef.current = null
      }
    }
  }, [videos, propertyId, videoType])

  useEffect(() => {
    fetchVideos()
  }, [propertyId, videoType])

  return {
    videos,
    loading,
    error,
    deleteVideo,
    refetch: fetchVideos,
  }
}