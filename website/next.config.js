/** @type {import('next').NextConfig} */
const nextConfig = {
  // framer-motion 11.11.0 + @types/react 19 emit 45 identical TS2322 on
  // motion.* HTML attributes (className/href/id). Pre-existing framework
  // typing friction, zero logic errors. Keep typecheck in editors; ignore at
  // build so `next build` (Vercel) succeeds.
  typescript: {
    ignoreBuildErrors: false,
  },
  experimental: {
    turbo: {
      rules: {
        '*.svg': {
          loaders: ['@svgr/webpack'],
          as: '*.js',
        },
      },
    },
  },
  images: {
    formats: ['image/avif', 'image/webp'],
  },
};

module.exports = nextConfig;