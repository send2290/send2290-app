/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Remove the broken `serverActions` flag entirely
  // experimental: {
  //   serverActions: true
  // },

  // Proxy `/build-xml`, `/download-xml`, and `/download-pdf` to your Flask API
  async rewrites() {
    return [
      {
        source: '/build-xml',
        destination: `${process.env.NEXT_PUBLIC_API_URL}/build-xml`,
      },
      {
        source: '/download-xml',
        destination: `${process.env.NEXT_PUBLIC_API_URL}/download-xml`,
      },
      {
        source: '/download-pdf',
        destination: `${process.env.NEXT_PUBLIC_API_URL}/download-pdf`,
      },
    ]
  }
}

export default nextConfig
