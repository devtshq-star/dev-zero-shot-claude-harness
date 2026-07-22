import type { Metadata } from 'next'
import { Inter, Noto_Sans_Devanagari } from 'next/font/google'
import './globals.css'
import { I18nProvider } from './i18n/I18nProvider'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

// Devanagari glyphs for Hindi — Inter has none, so this fills them in via the
// font stack (Latin text still uses Inter; Hindi falls through to this).
const notoDevanagari = Noto_Sans_Devanagari({
  subsets: ['devanagari'],
  variable: '--font-noto-deva',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'UP Police Data Analyst Agent',
  description: 'Upload CSV datasets and ask questions in a chat interface',
}

// Runs before first paint to apply the saved (or OS/browser) theme and language,
// avoiding a flash. Kept tiny and inline so there is no extra request.
const preInit = `(function(){try{
var t=localStorage.getItem('theme');
var d=t?t==='dark':window.matchMedia('(prefers-color-scheme: dark)').matches;
document.documentElement.classList.toggle('dark',d);
var l=localStorage.getItem('lang');
if(!l){l=(navigator.language||'en').toLowerCase().indexOf('hi')===0?'hi':'en';}
document.documentElement.lang=l;
document.documentElement.dir=l==='ur'||l==='ar'?'rtl':'ltr';
}catch(e){}})();`

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${notoDevanagari.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: preInit }} />
      </head>
      <body className="min-h-screen font-sans antialiased">
        <I18nProvider>{children}</I18nProvider>
      </body>
    </html>
  )
}
