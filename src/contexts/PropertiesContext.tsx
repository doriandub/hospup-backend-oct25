'use client'

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { api } from '@/lib/api'
import { Property, CreatePropertyRequest } from '@/types'

interface PropertiesContextType {
  properties: Property[]
  loading: boolean
  error: string | null
  fetchProperties: () => Promise<void>
  createProperty: (propertyData: CreatePropertyRequest | any) => Promise<Property>
  updateProperty: (id: number, propertyData: Partial<CreatePropertyRequest> | any) => Promise<Property>
  deleteProperty: (id: number) => Promise<void>
}

const PropertiesContext = createContext<PropertiesContextType | undefined>(undefined)

export function useProperties() {
  const context = useContext(PropertiesContext)
  if (context === undefined) {
    throw new Error('useProperties must be used within a PropertiesProvider')
  }
  return context
}

interface PropertiesProviderProps {
  children: ReactNode
}

export function PropertiesProvider({ children }: PropertiesProviderProps) {
  const [properties, setProperties] = useState<Property[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchProperties = async () => {
    try {
      setLoading(true)
      setError(null)
      
      // Always try to fetch, but handle gracefully if it fails
      const data = await api.getProperties() as Property[]
      
      // Ensure data is an array
      if (Array.isArray(data)) {
        setProperties(data)
      } else {
        console.warn('API returned non-array data:', data)
        setProperties([])
      }
    } catch (error) {
      console.error('Error fetching properties:', error)
      setProperties([])
      setError(error instanceof Error ? error.message : 'Failed to fetch properties')
    } finally {
      setLoading(false)
    }
  }

  const createProperty = async (propertyData: CreatePropertyRequest | any): Promise<Property> => {
    try {
      setError(null)
      
      console.log('Creating property with data:', propertyData)
      const newProperty = await api.createProperty(propertyData) as Property
      setProperties(prev => [...prev, newProperty])
      return newProperty
    } catch (error) {
      console.error('Error creating property:', error)
      setError(error instanceof Error ? error.message : 'Failed to create property')
      throw error
    }
  }

  const updateProperty = async (id: number, propertyData: Partial<CreatePropertyRequest> | any): Promise<Property> => {
    try {
      setError(null)
      const updatedProperty = await api.updateProperty(id, propertyData) as Property
      setProperties(prev => 
        prev.map(property => 
          property.id === id ? updatedProperty : property
        )
      )
      return updatedProperty
    } catch (error) {
      console.error('Error updating property:', error)
      setError(error instanceof Error ? error.message : 'Failed to update property')
      throw error
    }
  }

  const deleteProperty = async (id: number): Promise<void> => {
    try {
      setError(null)
      await api.deleteProperty(id)
      setProperties(prev => prev.filter(property => property.id !== id))
    } catch (error) {
      console.error('Error deleting property:', error)
      setError(error instanceof Error ? error.message : 'Failed to delete property')
      throw error
    }
  }

  useEffect(() => {
    fetchProperties()
  }, [])

  return (
    <PropertiesContext.Provider value={{
      properties,
      loading,
      error,
      fetchProperties,
      createProperty,
      updateProperty,
      deleteProperty,
    }}>
      {children}
    </PropertiesContext.Provider>
  )
}