'use client'

import { usePathname } from 'next/navigation'
import { Sidebar, MobileMenuButton } from '@/components/dashboard/sidebar'
import { UserMenu } from '@/components/dashboard/user-menu'
import { ProtectedRoute } from '@/components/auth/protected-route'
import { useState } from 'react'

// Function to get page title from pathname
function getPageTitle(pathname: string): string {
  const routes: { [key: string]: string } = {
    '/dashboard': 'Dashboard',
    '/dashboard/properties': 'Properties',
    '/dashboard/videos': 'Videos',
    '/dashboard/generate': 'AI Generator',
    '/dashboard/assets': 'Assets',
    '/dashboard/viral-inspiration': 'Viral Inspiration',
    '/dashboard/settings': 'Settings',
    '/dashboard/billing': 'Billing & Usage',
    '/dashboard/admin': 'Admin Panel'
  }
  
  // Check for exact matches first
  if (routes[pathname]) {
    return routes[pathname]
  }
  
  // Check for partial matches (for dynamic routes)
  for (const [route, title] of Object.entries(routes)) {
    if (pathname.startsWith(route + '/')) {
      return title
    }
  }
  
  return 'Dashboard'
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const pathname = usePathname()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const pageTitle = getPageTitle(pathname)

  return (
    <ProtectedRoute>
      <div className="flex h-screen bg-gray-50 overflow-hidden">
      
      <Sidebar 
        isMobileOpen={sidebarOpen} 
        setIsMobileOpen={setSidebarOpen} 
      />
      
      {/* Main content area */}
      <div className="flex-1 flex flex-col overflow-hidden relative">
        {/* Mobile header */}
        <div className="lg:hidden bg-gray-50" style={{ height: '80px' }}>
          <div className="flex items-center justify-between h-full px-8">
            <div className="flex items-center">
              <MobileMenuButton onClick={() => setSidebarOpen(true)} />
            </div>
            <div className="flex-1 flex items-center justify-center">
              <div className="text-lg font-bold text-gray-900">
                {pageTitle}
              </div>
            </div>
            <div className="flex items-center">
              <UserMenu />
            </div>
          </div>
        </div>

        {/* Desktop header */}
        <div className="hidden lg:block bg-gray-50" style={{ height: '80px' }}>
          <div className="px-8 h-full">
            <div className="flex items-center justify-between h-full">
              <div className="flex items-center">
                <h1 className="text-2xl font-bold text-gray-900">
                  {pageTitle}
                </h1>
              </div>
              <div className="pr-8 flex items-center">
                <UserMenu />
              </div>
            </div>
          </div>
        </div>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
      </div>
    </ProtectedRoute>
  )
}