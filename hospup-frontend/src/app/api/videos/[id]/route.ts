import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'https://hospup-backend-production.up.railway.app'

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const authHeader = request.headers.get('authorization')
    
    if (!authHeader) {
      return NextResponse.json({ error: 'Authorization required' }, { status: 401 })
    }

    const videoId = params.id

    // Forward delete request to Railway backend
    const response = await fetch(`${BACKEND_URL}/api/v1/videos/${videoId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': authHeader,
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      return NextResponse.json(
        { error: 'Failed to delete video' }, 
        { status: response.status }
      )
    }

    return NextResponse.json({ success: true })

  } catch (error) {
    console.error('API proxy error:', error)
    return NextResponse.json(
      { error: 'Internal server error' }, 
      { status: 500 }
    )
  }
}