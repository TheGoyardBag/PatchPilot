import type { NextConfig } from "next";
const target = process.env.PATCHPILOT_BACKEND ?? "http://127.0.0.1:8000";
const url = new URL(target);
if (!['127.0.0.1','localhost'].includes(url.hostname) || url.protocol !== 'http:') {
  throw new Error('This local development proxy only accepts an HTTP loopback backend.');
}
const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() { return [{ source: "/api/:path*", destination: `${url.origin}/api/:path*` }]; },
  async headers() { return [{source:'/:path*',headers:[{key:'X-Content-Type-Options',value:'nosniff'},{key:'X-Frame-Options',value:'DENY'},{key:'Referrer-Policy',value:'no-referrer'}]}]; }
};
export default config;
