'use client'

import { useState, useEffect } from 'react'
import { Property, CreatePropertyRequest } from '@/types'
import { api } from '@/lib/api'

export function useProperties() {
  const [properties, setProperties] = useState<Property[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchProperties = async () => {
    try {
      setLoading(true)
      setError(null)
      
      console.log('Fetching properties from Railway API...')
      const response = await api.getProperties() as any
      
      console.log('Railway API response:', response)
      
      // Railway backend returns PropertyListResponse with properties in .properties field
      let propertiesData: Property[] = []
      
      if (response && typeof response === 'object') {
        if (Array.isArray(response.properties)) {
          // PropertyListResponse format from Railway
          propertiesData = response.properties
          console.log(`Found ${propertiesData.length} properties from PropertyListResponse`)
        } else if (Array.isArray(response.data)) {
          // Fallback: response wrapped in .data property
          propertiesData = response.data
          console.log(`Found ${propertiesData.length} properties from .data`)
        } else if (Array.isArray(response)) {
          // Fallback: direct array response
          propertiesData = response
          console.log(`Found ${propertiesData.length} properties from direct array`)
        } else {
          console.warn('Unexpected Railway API response format:', response)
          console.log('Response keys:', Object.keys(response))
        }
      } else {
        console.warn('Invalid response from Railway API:', typeof response, response)
      }
      
      console.log('Final properties data to set:', propertiesData)
      setProperties(propertiesData)
    } catch (err: any) {
      console.error('Properties fetch error:', err)
      const errorMessage = err.message || 'Failed to fetch properties'
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

  const createProperty = async (data: CreatePropertyRequest | any): Promise<Property> => {
    try {
      console.log('Creating property with data:', data)
      const response = await api.createProperty(data) as any
      
      // Handle different response formats
      let newProperty: Property
      if (response && typeof response === 'object') {
        if (response.data && typeof response.data === 'object') {
          newProperty = response.data
        } else if (response.id) {
          newProperty = response
        } else {
          throw new Error('Invalid response format for created property')
        }
      } else {
        throw new Error('Invalid response format for created property')
      }
      
      setProperties(prev => [...prev, newProperty])
      return newProperty
    } catch (err: any) {
      console.error('Error creating property:', err)
      throw new Error(err.message || 'Failed to create property')
    }
  }

  const updateProperty = async (id: number, data: Partial<CreatePropertyRequest> | any): Promise<Property> => {
    try {
      console.log('Updating property:', id, data)
      const response = await api.updateProperty(id, data) as any
      
      // Handle different response formats
      let updatedProperty: Property
      if (response && typeof response === 'object') {
        if (response.data && typeof response.data === 'object') {
          updatedProperty = response.data
        } else if (response.id) {
          updatedProperty = response
        } else {
          throw new Error('Invalid response format for updated property')
        }
      } else {
        throw new Error('Invalid response format for updated property')
      }
      
      setProperties(prev => 
        prev.map(property => 
          property.id === id ? updatedProperty : property
        )
      )
      return updatedProperty
    } catch (err: any) {
      console.error('Error updating property:', err)
      throw new Error(err.message || 'Failed to update property')
    }
  }

  const deleteProperty = async (id: number): Promise<void> => {
    try {
      console.log('Deleting property:', id)
      await api.deleteProperty(id)
      setProperties(prev => prev.filter(property => property.id !== id))
    } catch (err: any) {
      console.error('Error deleting property:', err)
      throw new Error(err.message || 'Failed to delete property')
    }
  }

  useEffect(() => {
    fetchProperties()
  }, [])

  return {
    properties,
    loading,
    error,
    createProperty,
    updateProperty,
    deleteProperty,
    refetch: fetchProperties,
  }
}