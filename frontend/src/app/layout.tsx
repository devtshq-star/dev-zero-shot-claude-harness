import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'UP Police Data Analyst Agent',
  description: 'Upload CSV datasets and ask questions in a chat interface',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 antialiased">{children}</body>
    </html>
  )
}
