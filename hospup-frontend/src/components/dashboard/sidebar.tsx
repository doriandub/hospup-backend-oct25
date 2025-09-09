'use client'

import React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { 
  Home, 
  Building2, 
  Video, 
  Stars, 
  FolderOpen,
  Lightbulb,
  Menu, 
  X,
  Wand2
} from 'lucide-react'

interface NavItem {
  name: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  badge?: string
  description?: string
}

const navigation: NavItem[] = [
  { 
    name: "Dashboard", 
    href: "/dashboard", 
    icon: Home
  },
  { 
    name: "Properties", 
    href: "/dashboard/properties", 
    icon: Building2
  },
  { 
    name: "Videos", 
    href: "/dashboard/videos", 
    icon: Video
  },
  { 
    name: "AI Generator", 
    href: "/dashboard/generate", 
    icon: Wand2
  },
  { 
    name: "Assets", 
    href: "/dashboard/assets", 
    icon: FolderOpen
  },
  { 
    name: "Viral Inspiration", 
    href: "/dashboard/viral-inspiration", 
    icon: Lightbulb
  },
]

interface SidebarProps {
  isMobileOpen: boolean
  setIsMobileOpen: (open: boolean) => void
}

export function Sidebar({ isMobileOpen, setIsMobileOpen }: SidebarProps) {
  const pathname = usePathname()

  return (
    <>
      {/* Mobile sidebar overlay */}
      {isMobileOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className={`fixed inset-y-0 left-0 z-50 bg-white border-r border-gray-200 shadow-sm transform transition-all duration-300 lg:translate-x-0 lg:static lg:inset-0 ${
        isMobileOpen ? 'translate-x-0' : '-translate-x-full'
      } w-64 xl:w-64 lg:w-24 md:w-64`}>
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center justify-center lg:justify-center xl:justify-between h-20 px-6 border-b border-gray-200">
            <div className="flex items-center lg:justify-center xl:justify-start">
              <div className="w-10 h-10 xl:hidden lg:w-12 lg:h-12 lg:block bg-primary rounded-lg flex items-center justify-center">
                <Building2 className="w-6 h-6 text-white" />
              </div>
              <div className="xl:block lg:hidden hidden">
                <span className="text-xl font-bold text-gray-900">Hospup</span>
              </div>
            </div>
            <div className="flex items-center space-x-2 xl:block lg:hidden">
              {/* Mobile close button */}
              <button
                onClick={() => setIsMobileOpen(false)}
                className="lg:hidden p-2 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 py-6 space-y-2 overflow-y-auto px-4 xl:px-4 lg:px-3">
            {navigation.map((item) => {
              const isActive = pathname === item.href
              return (
                <Link
                  key={item.name}
                  href={item.href as any}
                  className={`flex items-center text-base font-medium rounded-lg transition-colors relative ${
                    isActive
                      ? 'text-primary bg-primary/5'
                      : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
                  } px-4 py-3 xl:px-4 xl:py-3 lg:px-3 lg:py-4 xl:justify-start lg:justify-center`}
                  onClick={() => setIsMobileOpen(false)}
                  title={item.name}
                >
                  {/* Active indicator */}
                  {isActive && (
                    <div className="absolute left-0 top-0 bottom-0 w-1 bg-primary rounded-r-full"></div>
                  )}
                  <item.icon className={`h-6 w-6 ${
                    isActive ? 'text-primary' : 'text-gray-500'
                  } xl:mr-4 lg:mr-0 mr-4`} />
                  <span className="xl:block lg:hidden block text-base font-medium">{item.name}</span>
                </Link>
              )
            })}
          </nav>

          {/* Bottom Section */}
          <div className="p-4 border-t border-gray-200 xl:block lg:hidden block">
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="flex items-center space-x-2">
                <div className="w-6 h-6 bg-primary rounded flex items-center justify-center">
                  <Stars className="w-3 h-3 text-white" />
                </div>
                <div className="text-xs text-gray-600">Powered by AI</div>
              </div>
            </div>
          </div>

        </div>
      </div>
    </>
  )
}

export function MobileMenuButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="lg:hidden p-2 rounded-md text-gray-600 hover:text-gray-800 hover:bg-gray-100/50 transition-all duration-200"
    >
      <Menu className="h-5 w-5" />
    </button>
  )
}