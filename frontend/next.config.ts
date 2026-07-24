import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable React strict mode for development
  reactStrictMode: true,

  // Optimize production builds
  compiler: {
    // Remove console.log in production (keeps console.error)
    removeConsole: process.env.NODE_ENV === "production" ? { exclude: ["error", "warn"] } : false,
  },

  // Enable gzip/brotli compression for static assets
  compress: true,

  // Configure image optimization
  images: {
    // Allow blob URLs for design upload previews
    remotePatterns: [],
    // Unoptimized needed for blob: URLs
    unoptimized: true,
  },

  // Experimental features for performance
  experimental: {
    // Optimize package imports for tree-shaking
    optimizePackageImports: [
      "@monaco-editor/react",
      "react-markdown",
      "remark-gfm",
    ],
  },
};

export default nextConfig;
