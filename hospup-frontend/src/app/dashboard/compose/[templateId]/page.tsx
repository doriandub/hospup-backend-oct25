'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { VideoTimelineEditor } from '@/components/video-timeline-editor'
import { VideoGenerationNavbar } from '@/components/video-generation/VideoGenerationNavbar'
import { useProperties } from '@/hooks/useProperties'
import { useAssets } from '@/hooks/useAssets'
import { Loader2, ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { TextOverlay } from '@/types/text-overlay'

interface ViralTemplate {
  id: string
  title: string
  hotel_name: string
  duration: number
  script: string
}

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

export default function ComposePage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const { properties } = useProperties()
  
  const [template, setTemplate] = useState<ViralTemplate | null>(null)
  const [templateSlots, setTemplateSlots] = useState<TemplateSlot[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedProperty, setSelectedProperty] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  
  // ✅ Use proper useAssets hook instead of direct API call
  const { 
    assets: allAssets, 
    loading: assetsLoading,
    error: assetsError 
  } = useAssets(selectedProperty, 'uploaded')
  

  const templateId = params.templateId as string
  const propertyFromUrl = searchParams.get('property')
  const promptFromUrl = searchParams.get('prompt')
  
  // Convert to ContentVideo format for VideoTimelineEditor compatibility (direct from allAssets)
  const contentVideos: ContentVideo[] = allAssets.map((asset) => ({
    id: asset.id,
    title: asset.title,
    thumbnail_url: asset.thumbnail_url || '',
    video_url: asset.file_url,
    duration: asset.duration || 10,
    description: asset.description || ''
  }))

  // Auto-select property from URL parameter
  useEffect(() => {
    if (propertyFromUrl && properties.length > 0) {
      const propertyId = parseInt(propertyFromUrl)
      const propertyExists = properties.find(p => p.id === propertyId)
      if (propertyExists) {
        setSelectedProperty(propertyFromUrl)
      }
    }
  }, [propertyFromUrl, properties])

  useEffect(() => {
    loadTemplateAndSegments()
  }, [templateId])


  // Auto-match when both templateSlots and contentVideos are loaded
  useEffect(() => {
    if (templateSlots.length > 0 && contentVideos.length > 0) {
    }
  }, [templateSlots, contentVideos])

  const loadTemplateAndSegments = async () => {
    try {
      // Load template info
      const templateData = await api.get<ViralTemplate>(`/api/v1/viral-matching/viral-templates/${templateId}`)
      setTemplate(templateData)

      // Parse slots from script
      if (templateData.script) {
        const parsedSlots = parseTemplateScript(templateData.script)
        setTemplateSlots(parsedSlots)
      } else {
        setError('Ce template ne contient pas de structure de vidéo valide.')
      }
    } catch (error: any) {
      console.error('Error loading template:', error)
      setError(error.message || 'Impossible de charger ce template. Il se peut qu\'il n\'existe pas ou soit temporairement indisponible.')
    } finally {
      setLoading(false)
    }
  }


  const parseTemplateScript = (script: any): TemplateSlot[] => {
    try {
      
      let scriptData: any = script
      
      // Handle both string and object formats
      if (typeof script === 'string') {
        let cleanScript = script.trim()
        
        // Remove '=' prefixes if they exist (can be == or =)
        while (cleanScript.startsWith('=')) {
          cleanScript = cleanScript.slice(1).trim()
        }
        
        
        // Check if it's valid JSON
        if (!cleanScript.startsWith('{') && !cleanScript.startsWith('[')) {
          console.warn('Script does not appear to be valid JSON:', cleanScript.substring(0, 100))
          return []
        }
        
        scriptData = JSON.parse(cleanScript)
      }
      
      const clips = scriptData.clips || []

      if (clips.length === 0) {
        console.warn('⚠️ No clips found in script data')
        return []
      }

      let currentTime = 0
      return clips.map((clip: any, index: number) => {
        // Use template duration for slot structure (will be overridden by user video choices)
        const duration = clip.duration || clip.end - clip.start || 2
        
        const slot: TemplateSlot = {
          id: `slot_${index}`,
          order: clip.order || index + 1,
          duration: duration,
          description: clip.description || `Slot ${index + 1}`,
          start_time: currentTime,
          end_time: currentTime + duration
        }
        currentTime += duration
        return slot
      })
    } catch (error) {
      console.error('Error parsing template script:', error)
      console.error('Original script:', script.substring(0, 200))
      return []
    }
  }

  const createScriptFromTimeline = (assignments: any[], textOverlays: any[]) => {
    const clips = assignments
      .filter(assignment => assignment.videoId) // Only slots with assigned videos
      .sort((a, b) => {
        // Sort by slot order
        const slotA = templateSlots.find(slot => slot.id === a.slotId)
        const slotB = templateSlots.find(slot => slot.id === b.slotId)
        return (slotA?.order || 0) - (slotB?.order || 0)
      })
      .map((assignment, index) => {
        const slot = templateSlots.find(slot => slot.id === assignment.slotId)
        const video = contentVideos.find(video => video.id === assignment.videoId)
        
        // 🎯 CRITICAL FIX: Use user's video duration, ignore template slot duration
        // This respects user's video choice and creates proper timing
        const videoDuration = video?.duration || 0
        const userDuration = videoDuration > 0 
          ? Math.min(Math.max(videoDuration, 1.5), 6) // Use video duration: 1.5s min, 6s max
          : 2.0 // Default 2s if no video duration available
        
        console.log(`📊 Segment ${index + 1}: video=${videoDuration}s → using ${userDuration}s (ignoring template)`)
        
        return {
          order: index + 1,
          duration: userDuration,
          description: slot?.description || `Segment ${index + 1}`,
          video_url: video?.video_url || '',
          video_id: video?.id || '',
          start_time: 0, // Reset timing for user composition
          end_time: userDuration
        }
      })

    const texts = textOverlays.map(text => ({
      content: text.content,
      start_time: text.start_time,
      end_time: text.end_time || text.start_time + 3,
      // Include all position and style data
      position: text.position,
      style: text.style
    }))

    // Calculate real total duration from actual clips generated
    const realTotalDuration = clips.reduce((sum, clip) => sum + clip.duration, 0)
    
    console.log(`🎬 Generated custom script: ${clips.length} clips, total: ${realTotalDuration}s`)
    
    return {
      clips,
      texts,
      total_duration: realTotalDuration
    }
  }

  const handleGenerate = async (assignments: any[], textOverlays: any[]) => {
    if (isGenerating) return
    
    console.log('🎬 handleGenerate called with:', { assignments, textOverlays })
    console.log('📍 Text overlays positions:')
    textOverlays.forEach((text, i) => {
      console.log(`   Text ${i+1}: "${text.content}" -> x:${text.position.x}, y:${text.position.y} (${text.position.anchor})`)
    })
    try {
      setIsGenerating(true)
      setError(null)
      
      // Create custom script based on timeline (like working version)
      const customScript = createScriptFromTimeline(assignments, textOverlays)
      console.log('📜 Generated custom script:', customScript)
      
      const generationData = {
        property_id: selectedProperty,
        source_type: 'viral_template_composer',
        source_data: {
          template_id: templateId,
          slot_assignments: assignments,
          text_overlays: textOverlays,
          custom_script: customScript,
          total_duration: customScript.total_duration,
          user_input: promptFromUrl || ''
        },
        language: 'fr'
      }
      
      console.log('📤 Sending generation request:', generationData)

      const response = await api.post('/api/v1/video-generation/aws-generate', generationData)
      
      const result = response.data
      console.log('✅ Video generation successful:', result)
      
      if (result.video_id) {
        router.push(`/dashboard/videos/${result.video_id}/preview`)
      } else {
        router.push('/dashboard/videos')
      }
    } catch (error: any) {
      console.error('Error generating video:', error)
      setError(error.message || 'Erreur lors de la génération de la vidéo')
    } finally {
      setIsGenerating(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-gray-600">Chargement du template...</p>
        </div>
      </div>
    )
  }

  if (!template) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600 mb-4">Template non trouvé</p>
          <Button onClick={() => router.back()}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Retour
          </Button>
        </div>
      </div>
    )
  }

  if (!selectedProperty) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-2xl mx-auto">
          <div className="bg-white rounded-lg shadow-sm border p-8">
            <h1 className="text-2xl font-bold text-gray-900 mb-4">Choisir une Propriété</h1>
            <p className="text-gray-600 mb-6">
              Sélectionnez la propriété pour laquelle vous voulez créer cette vidéo :
            </p>
            
            <div className="space-y-3">
              {properties.map((property) => (
                <div
                  key={property.id}
                  onClick={() => setSelectedProperty(property.id.toString())}
                  className="p-4 border-2 border-gray-200 rounded-lg cursor-pointer hover:border-primary hover:bg-primary/5 transition-all"
                >
                  <h3 className="font-medium text-gray-900">{property.name}</h3>
                  <p className="text-sm text-gray-600">{property.city || 'No location'}</p>
                </div>
              ))}
            </div>

            {properties.length === 0 && (
              <div className="text-center py-8">
                <p className="text-gray-500">Aucune propriété trouvée</p>
                <Button 
                  onClick={() => router.push('/dashboard/properties/new')}
                  className="mt-4"
                >
                  Ajouter une Propriété
                </Button>
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <VideoGenerationNavbar 
        currentStep={3}
        propertyId={selectedProperty}
        templateId={templateId}
        showGenerationButtons={true}
        onRandomTemplate={() => {
          // Add text functionality
          if ((window as any).videoTimelineAddText) {
            (window as any).videoTimelineAddText()
          }
        }}
        onGenerateTemplate={() => {
          // Create video functionality
          if ((window as any).videoTimelineGenerateVideo) {
            (window as any).videoTimelineGenerateVideo()
          }
        }}
        isGenerating={isGenerating}
      />
      
      {/* Error display */}
      {error && (
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-red-700">{error}</p>
                <button 
                  onClick={() => setError(null)}
                  className="mt-2 text-sm text-red-600 underline hover:text-red-800"
                >
                  Fermer
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Assets loading error fallback */}
      {assetsError && (
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-yellow-700">
                  Impossible de charger les assets. Vous pouvez continuer sans assets ou 
                  <button className="ml-1 underline hover:text-yellow-900" onClick={() => window.location.reload()}>
                    recharger la page
                  </button>.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
      
      <VideoTimelineEditor
        templateTitle={template.title}
        templateSlots={templateSlots}
        contentVideos={contentVideos}
        onGenerate={handleGenerate}
        propertyId={selectedProperty}
        templateId={templateId}
        onAddText={() => {}}
        onGenerateVideo={() => {}}
      />
    </div>
  )
}