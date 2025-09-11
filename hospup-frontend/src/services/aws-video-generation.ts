/**
 * AWS MediaConvert Video Generation Service
 * Remplace le système FFmpeg par AWS MediaConvert pour une scalabilité infinie
 */

export interface VideoSegment {
  id: string
  video_url: string
  start_time: number
  end_time: number
  duration: number
  order: number
}

export interface TextOverlay {
  id: string
  content: string
  start_time: number
  end_time: number
  position: {
    x: number // Pourcentage 0-100
    y: number // Pourcentage 0-100
  }
  style: {
    font_family: string
    font_size: number
    color: string
    bold: boolean
    italic: boolean
    shadow: boolean
    outline: boolean
    opacity: number
    text_align: 'left' | 'center' | 'right'
  }
}

export interface VideoGenerationRequest {
  property_id: string
  source_type?: string
  source_data: {
    template_id: string
    text_overlays: TextOverlay[]
    total_duration: number
    slot_assignments?: any[]
    custom_script?: any
  }
  language?: string
}

export interface VideoGenerationResponse {
  job_id: string
  video_id: string
  status: 'SUBMITTED' | 'PROGRESSING' | 'COMPLETE' | 'ERROR'
  video_url?: string
  progress?: number
  error?: string
}

/**
 * Service de génération vidéo via AWS MediaConvert
 */
export class AWSVideoGenerationService {
  private readonly API_ENDPOINT = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://web-production-b52f.up.railway.app'

  /**
   * Get stored authentication token from localStorage
   */
  private getStoredToken(): string | null {
    if (typeof window === 'undefined') return null
    return localStorage.getItem('access_token')
  }

  /**
   * Lance la génération vidéo via AWS MediaConvert
   */
  async generateVideo(request: VideoGenerationRequest): Promise<VideoGenerationResponse> {
    try {
      console.log('🚀 Starting AWS video generation:', {
        slot_assignments: request.source_data.slot_assignments?.length || 0,
        texts: request.source_data.text_overlays.length,
        duration: request.source_data.total_duration
      })

      // Get token for authentication
      const token = this.getStoredToken()
      
      const response = await fetch(`${this.API_ENDPOINT}/api/v1/video-generation/aws-generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify(request)
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const result = await response.json()
      
      console.log('✅ AWS video generation initiated:', result)
      return result
    } catch (error: any) {
      console.error('❌ AWS video generation failed:', error)
      throw new Error(`Video generation failed: ${error.message}`)
    }
  }

  /**
   * Vérifie le statut d'une génération vidéo
   */
  async checkGenerationStatus(jobId: string): Promise<VideoGenerationResponse> {
    try {
      // Get token for authentication
      const token = this.getStoredToken()
      
      const response = await fetch(`${this.API_ENDPOINT}/api/v1/video-generation/aws-status/${jobId}`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      return await response.json()
    } catch (error: any) {
      console.error('❌ Status check failed:', error)
      throw new Error(`Status check failed: ${error.message}`)
    }
  }

  /**
   * Convertit les données de la timeline vers le format AWS
   */
  static convertTimelineToAWS(
    templateSlots: any[],
    assignments: any[],
    textOverlays: TextOverlay[],
    contentVideos: any[]
  ): VideoGenerationRequest {
    // Valider les assignments
    if (assignments.filter(assignment => assignment.videoId).length === 0) {
      throw new Error('No video segments assigned')
    }

    // Calculer la durée totale à partir des slots
    const totalDuration = templateSlots.reduce((sum, slot) => sum + slot.duration, 0)

    // Convertir segments en slot_assignments selon le format backend
    const slot_assignments = assignments
      .filter(assignment => assignment.videoId)
      .map(assignment => ({
        slotId: assignment.slotId,
        videoId: assignment.videoId, 
        confidence: 1.0, // Confidence max puisque c'est un choix manuel
        reasoning: "Manual selection"
      }))

    return {
      property_id: '', // À remplir par l'appelant
      source_type: "viral_template_composer",
      source_data: {
        template_id: '', // À remplir par l'appelant
        text_overlays: textOverlays,
        total_duration: totalDuration,
        slot_assignments,
        custom_script: { total_duration: totalDuration }
      },
      language: "fr"
    }
  }
}

// Instance singleton
export const awsVideoService = new AWSVideoGenerationService()