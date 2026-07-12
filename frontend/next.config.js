/** @type {import('next').NextConfig} */
const API = process.env.PROMPTER_API_URL || "http://127.0.0.1:8400";
module.exports = {
  reactStrictMode: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};
