/** @type {import('next').NextConfig} */
const nextConfig = {
  typescript: {
    ignoreBuildErrors: false,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  experimental: {
    typedRoutes: true,
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '*.s3.amazonaws.com',
      },
      {
        protocol: 'https',
        hostname: 's3.eu-west-1.amazonaws.com',
      },
      {
        protocol: 'https',
        hostname: 'hospup-files.s3.eu-west-1.amazonaws.com',
      },
      {
        protocol: 'https',
        hostname: 'cdn.hospup.app',
      },
    ],
  },
}

module.exports = nextConfig