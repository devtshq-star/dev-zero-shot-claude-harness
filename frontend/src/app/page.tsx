'use client'

import { useEffect, useState } from 'react'
import ChatView from './components/ChatView'
import UploadLibrary from './components/UploadLibrary'

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null)

  // Support deep-linking / reload via ?session=<id> without pulling in
  // next/navigation's useSearchParams (which requires a Suspense boundary
  // and complicates the static export). Plain window APIs are enough here.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const fromUrl = params.get('session')
    if (fromUrl) setSessionId(fromUrl)
  }, [])

  function openSession(id: string) {
    setSessionId(id)
    const url = new URL(window.location.href)
    url.searchParams.set('session', id)
    window.history.pushState({}, '', url)
  }

  function backToLibrary() {
    setSessionId(null)
    const url = new URL(window.location.href)
    url.searchParams.delete('session')
    window.history.pushState({}, '', url)
  }

  if (sessionId) {
    return <ChatView sessionId={sessionId} onBack={backToLibrary} />
  }

  return <UploadLibrary onOpenSession={openSession} />
}
