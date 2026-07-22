'use client'

/**
 * Lightweight, dependency-free i18n. A React context holds the active language
 * and exposes t() plus locale-aware date/number formatters, so switching
 * language re-renders every consumer instantly (no reload). Both dictionaries
 * are bundled (a few KB total — smaller than a lazy-load round-trip would cost),
 * and the choice persists in localStorage. Architecture is direction-aware
 * (dir is derived per language) so an RTL language can be added later.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import en from './en.json'
import hi from './hi.json'

export type Lang = 'en' | 'hi'

const DICTS: Record<Lang, Record<string, unknown>> = { en, hi }
const RTL_LANGS: Lang[] = [] // none yet; e.g. add 'ur'/'ar' here later
// Devanagari numerals + Indian digit grouping for Hindi; standard for English.
const INTL_LOCALE: Record<Lang, string> = { en: 'en-US', hi: 'hi-IN-u-nu-deva' }

function resolve(dict: Record<string, unknown>, key: string): string | undefined {
  let node: unknown = dict
  for (const part of key.split('.')) {
    if (node && typeof node === 'object' && part in (node as object)) {
      node = (node as Record<string, unknown>)[part]
    } else {
      return undefined
    }
  }
  return typeof node === 'string' ? node : undefined
}

function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template
  return template.replace(/\{(\w+)\}/g, (_, name) => (name in vars ? String(vars[name]) : `{${name}}`))
}

interface I18nValue {
  lang: Lang
  dir: 'ltr' | 'rtl'
  setLang: (lang: Lang) => void
  t: (key: string, vars?: Record<string, string | number>) => string
  formatNumber: (value: number) => string
  formatDate: (iso: string) => string
}

const I18nContext = createContext<I18nValue | null>(null)

function dirFor(lang: Lang): 'ltr' | 'rtl' {
  return RTL_LANGS.includes(lang) ? 'rtl' : 'ltr'
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>('en')

  // Adopt the language the no-flash inline script already resolved (localStorage
  // or browser), so the first client render matches what the user expects.
  useEffect(() => {
    const initial = (document.documentElement.lang as Lang) || 'en'
    setLangState(initial === 'hi' ? 'hi' : 'en')
  }, [])

  const setLang = useCallback((next: Lang) => {
    setLangState(next)
    try {
      localStorage.setItem('lang', next)
    } catch {
      /* storage may be unavailable; language still applies for the session */
    }
    document.documentElement.lang = next
    document.documentElement.dir = dirFor(next)
  }, [])

  const value = useMemo<I18nValue>(() => {
    const t = (key: string, vars?: Record<string, string | number>): string => {
      const str = resolve(DICTS[lang], key) ?? resolve(DICTS.en, key) ?? key
      return interpolate(str, vars)
    }
    const formatNumber = (n: number) => new Intl.NumberFormat(INTL_LOCALE[lang]).format(n)
    const formatDate = (iso: string) => {
      try {
        return new Intl.DateTimeFormat(INTL_LOCALE[lang], {
          day: 'numeric',
          month: 'short',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        }).format(new Date(iso))
      } catch {
        return iso
      }
    }
    return { lang, dir: dirFor(lang), setLang, t, formatNumber, formatDate }
  }, [lang, setLang])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n must be used within I18nProvider')
  return ctx
}
