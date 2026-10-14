import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Every route sits behind Supabase auth (reads cookies at request time),
  // so there is nothing to statically prerender — keep rendering dynamic
  // rather than wrapping every page in Suspense just to satisfy Cache
  // Components.
  cacheComponents: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
