'use client'

import { useEffect, useState } from 'react'
import { useProperties } from '@/hooks/useProperties'
import Link from 'next/link'
import {
  Building2,
  Video,
  Play,
  Plus,
  Upload,
  Activity,
  BarChart3,
  Headphones,
  ArrowRight,
  Wand2,
  Youtube
} from 'lucide-react'

interface DashboardStats {
  total_properties: number
  total_videos: number
  videos_this_month: number
  storage_used: number
  remaining_videos: number
  videos_limit: number
  videos_used: number
}

export default function DashboardPage() {
  const { properties, loading: propertiesLoading } = useProperties()
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!propertiesLoading) {
      // Use real data from properties
      const stats: DashboardStats = {
        total_properties: properties.length,
        total_videos: 12,
        videos_this_month: 5,
        storage_used: 245,
        remaining_videos: 38,
        videos_limit: 50,
        videos_used: 12
      }

      setStats(stats)
      setLoading(false)
    }
  }, [properties, propertiesLoading])

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-primary">Loading metrics...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="grid grid-cols-1 gap-3 p-8">
        {/* Main Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Create New Video */}
          <Link href="/dashboard/generate" className="md:col-span-2">
            <div className="bg-primary rounded-xl shadow-sm p-8 text-white cursor-pointer hover:shadow-md transition-all duration-200 group h-full">
              <div className="flex items-center justify-between relative z-10">
                <div>
                  <h1 className="text-xl font-semibold mb-2">Create New Video</h1>
                  <p className="text-base font-medium text-white/90">Start creating</p>
                </div>
                <div className="bg-white bg-opacity-20 rounded-full p-3 group-hover:bg-opacity-30 transition-all">
                  <Plus className="w-5 h-5" />
                </div>
              </div>
            </div>
          </Link>
          
          {/* Upload Content */}
          <Link href="/dashboard/content-library" className="md:col-span-2">
            <div className="bg-primary/5 border border-dashed border-primary rounded-xl shadow-sm p-8 cursor-pointer hover:bg-primary/10 hover:shadow-md transition-all duration-200 group h-full">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-xl font-semibold mb-2 text-primary">Upload Content</h1>
                  <p className="text-base font-medium text-primary/80">Drag & drop</p>
                </div>
                <div className="bg-primary/10 rounded-full p-3 group-hover:bg-primary/20 transition-all">
                  <Upload className="w-5 h-5 text-primary" />
                </div>
              </div>
            </div>
          </Link>

          {/* Total Videos */}
          <Link href="/dashboard/videos">
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow duration-200 p-8 cursor-pointer h-full">
              <div className="flex items-center space-x-3 h-full">
                <div className="bg-gray-100 p-2 rounded-lg">
                  <Video className="w-4 h-4 text-gray-700" />
                </div>
                <div>
                  <div className="text-xl font-semibold text-gray-900">
                    {stats?.total_videos ?? 0}
                  </div>
                  <div className="text-sm font-medium text-gray-600">Total Videos</div>
                </div>
              </div>
            </div>
          </Link>

          {/* Videos Remaining */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow duration-200 p-8 h-full">
            <div className="flex items-center space-x-3 h-full">
              <div className="bg-gray-100 p-2 rounded-lg">
                <BarChart3 className="w-4 h-4 text-gray-700" />
              </div>
              <div>
                <div className="text-xl font-semibold text-gray-900">
                  {(stats?.videos_limit ?? 50) - (stats?.videos_used ?? 0)}
                </div>
                <div className="text-sm font-medium text-gray-600">Videos Remaining</div>
              </div>
            </div>
          </div>

          {/* Total Properties */}
          <Link href="/dashboard/properties">
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow duration-200 p-8 cursor-pointer h-full">
              <div className="flex items-center space-x-3 h-full">
                <div className="bg-gray-100 p-2 rounded-lg">
                  <Building2 className="w-4 h-4 text-gray-700" />
                </div>
                <div>
                  <div className="text-xl font-semibold text-gray-900">
                    {stats?.total_properties ?? 0}
                  </div>
                  <div className="text-sm font-medium text-gray-600">Total Properties</div>
                </div>
              </div>
            </div>
          </Link>

          {/* Add Property */}
          <Link href="/dashboard/properties">
            <div className="bg-primary/5 border border-primary/30 rounded-xl shadow-sm p-8 cursor-pointer hover:bg-primary/10 hover:shadow-md transition-all duration-200 h-full">
              <div className="flex items-center space-x-3 h-full">
                <div className="bg-primary/10 rounded-full p-3 group-hover:bg-primary/20 transition-all">
                  <Plus className="w-5 h-5 text-primary" />
                </div>
                <span className="text-sm font-medium text-primary">Add Property</span>
              </div>
            </div>
          </Link>
        </div>

        {/* How to use Hospup */}
        <div className="space-y-3">
          <h2 className="text-xl font-semibold text-gray-900">How to use Hospup</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {/* YouTube Tutorial */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow duration-200 p-8">
              <div className="bg-gray-100 rounded-lg aspect-video flex items-center justify-center cursor-pointer hover:bg-gray-200 transition-all">
                <div className="text-center">
                  <Youtube className="w-16 h-16 text-red-500 mx-auto mb-2" />
                  <p className="text-gray-600 font-medium">Watch Tutorial</p>
                </div>
              </div>
            </div>

            {/* 3 Steps Process */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow duration-200 p-8">
              <h3 className="text-xl font-semibold text-gray-900 mb-4">Get Started in 3 Steps</h3>
              <div className="relative">
                {/* Progress Line */}
                <div className="absolute left-4 top-8 bottom-8 w-0.5 bg-primary/20"></div>
                
                <div className="space-y-8">
                  {/* Step 1 */}
                  <div className="flex items-start relative">
                    <div className="flex items-center justify-center w-8 h-8 bg-primary text-white rounded-full font-semibold text-xs z-10">
                      1
                    </div>
                    <div className="ml-3 flex-1">
                      <span className="text-sm font-medium text-gray-600">Add Your Property</span>
                    </div>
                  </div>

                  {/* Step 2 */}
                  <div className="flex items-start relative">
                    <div className="flex items-center justify-center w-8 h-8 bg-primary text-white rounded-full font-semibold text-xs z-10">
                      2
                    </div>
                    <div className="ml-3 flex-1">
                      <span className="text-sm font-medium text-gray-600">Upload Content</span>
                    </div>
                  </div>

                  {/* Step 3 */}
                  <div className="flex items-start relative">
                    <div className="flex items-center justify-center w-8 h-8 bg-primary text-white rounded-full font-semibold text-xs z-10">
                      3
                    </div>
                    <div className="ml-3 flex-1">
                      <span className="text-sm font-medium text-gray-600">Generate Videos</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Section */}
        <div className="space-y-3">
          <h2 className="text-xl font-semibold text-gray-900">Account Overview</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          {/* Usage Metrics */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow duration-200 p-8">
            <h3 className="text-xl font-semibold text-gray-900 mb-4">Usage Metrics</h3>
            <div className="space-y-3">
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium text-gray-600">Videos Used</span>
                  <span className="text-sm font-semibold text-gray-900">
                    {stats?.videos_used ?? 0}/50
                  </span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2 border border-gray-200">
                  <div 
                    className={`h-2 rounded-full transition-all duration-300 ${
                      (stats?.videos_used ?? 0) > 50 
                        ? 'bg-gradient-to-r from-red-500 to-red-600' 
                        : 'bg-gradient-to-r from-primary to-primary'
                    }`}
                    style={{ width: `${Math.min(((stats?.videos_used ?? 0) / 50) * 100, 100)}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium text-gray-600">Properties Registered</span>
                  <span className="text-sm font-semibold text-gray-900">
                    {stats?.total_properties ?? 0}/5
                  </span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2 border border-gray-200">
                  <div 
                    className="bg-gradient-to-r from-primary to-primary h-2 rounded-full transition-all duration-300" 
                    style={{ width: `${((stats?.total_properties ?? 0) / 5) * 100}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium text-gray-600">Days Remaining</span>
                  <span className="text-sm font-semibold text-gray-900">
                    {(() => {
                      const now = new Date()
                      const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0)
                      const daysLeft = Math.ceil((endOfMonth.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
                      return daysLeft
                    })()} days
                  </span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2 border border-gray-200">
                  <div 
                    className="bg-gradient-to-r from-primary to-primary h-2 rounded-full transition-all duration-300" 
                    style={{ 
                      width: `${(() => {
                        const now = new Date()
                        const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1)
                        const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0)
                        const totalDays = endOfMonth.getDate()
                        const daysPassed = now.getDate() - 1
                        return (daysPassed / totalDays) * 100
                      })()}%` 
                    }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Need Help */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow duration-200 p-8">
            <h3 className="text-xl font-semibold text-gray-900 mb-4">Need Help?</h3>
            <div className="space-y-3">
              <p className="text-sm text-gray-600">
                Our support team is here to help you create amazing videos.
              </p>
              <div className="flex items-center space-x-3 p-8 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer">
                <div className="bg-primary p-2 rounded-lg">
                  <Headphones className="w-4 h-4 text-white" />
                </div>
                <span className="text-sm font-medium text-gray-600">Contact Support</span>
              </div>
            </div>
          </div>
          </div>
        </div>

      </div>
    </div>
  )
}