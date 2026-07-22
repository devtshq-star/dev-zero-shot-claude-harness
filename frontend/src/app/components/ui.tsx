'use client'

/**
 * Design-system primitives. One place for buttons, cards, badges, skeletons,
 * empty/alert states, the theme toggle and the app header — so every screen
 * shares the same look and the markup stays declarative.
 */
import { useEffect, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { useI18n, type Lang } from '../i18n/I18nProvider'
import {
  AlertIcon,
  CheckIcon,
  InboxIcon,
  InfoIcon,
  MoonIcon,
  ShieldIcon,
  SunIcon,
  XIcon,
} from './icons'

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ')
}

/* ----------------------------- Button ----------------------------- */
type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md' | 'lg' | 'icon'

const VARIANT: Record<Variant, string> = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  ghost: 'btn-ghost',
  danger: 'btn-danger',
}
const SIZE: Record<Size, string> = { sm: 'btn-sm', md: 'btn-md', lg: 'btn-lg', icon: 'btn-icon' }

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  leftIcon?: ReactNode
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  leftIcon,
  disabled,
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={cx('btn', VARIANT[variant], SIZE[size], className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <Spinner className="h-4 w-4" /> : leftIcon}
      {children}
    </button>
  )
}

/* ----------------------------- Spinner ---------------------------- */
export function Spinner({ className }: { className?: string }) {
  return (
    <svg className={cx('animate-spin-slow', className)} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" strokeOpacity="0.2" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  )
}

/* ------------------------------ Card ------------------------------ */
export function Card({
  className,
  hover = false,
  children,
  ...rest
}: { hover?: boolean } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cx('card', hover && 'card-hover', className)} {...rest}>
      {children}
    </div>
  )
}

/* ----------------------------- Badge ------------------------------ */
type Tone = 'neutral' | 'primary' | 'success' | 'warning' | 'danger' | 'info'
export function Badge({ tone = 'neutral', className, children }: { tone?: Tone; className?: string; children: ReactNode }) {
  return <span className={cx('badge', `badge-${tone}`, className)}>{children}</span>
}

/* --------------------------- Skeleton ----------------------------- */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cx('skeleton', className)} />
}

/* --------------------------- EmptyState --------------------------- */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="animate-fade-in flex flex-col items-center justify-center rounded-xl border border-dashed border-line px-6 py-12 text-center">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-surface-2 text-faint">
        {icon ?? <InboxIcon className="h-6 w-6" />}
      </div>
      <p className="text-sm font-semibold text-foreground">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

/* ----------------------------- Alert ------------------------------ */
const ALERT_TONE: Record<'danger' | 'warning' | 'info' | 'success', { box: string; icon: ReactNode }> = {
  danger: { box: 'border-danger/30 bg-danger-soft text-danger-fg', icon: <AlertIcon className="h-4 w-4" /> },
  warning: { box: 'border-warning/30 bg-warning-soft text-warning-fg', icon: <AlertIcon className="h-4 w-4" /> },
  info: { box: 'border-info/30 bg-info-soft text-info-fg', icon: <InfoIcon className="h-4 w-4" /> },
  success: { box: 'border-success/30 bg-success-soft text-success-fg', icon: <CheckIcon className="h-4 w-4" /> },
}

export function Alert({
  tone = 'info',
  children,
  action,
  className,
}: {
  tone?: 'danger' | 'warning' | 'info' | 'success'
  children: ReactNode
  action?: ReactNode
  className?: string
}) {
  const t = ALERT_TONE[tone]
  return (
    <div
      role="alert"
      className={cx('animate-rise-in flex items-start gap-3 rounded-lg border px-3.5 py-3 text-sm', t.box, className)}
    >
      <span className="mt-0.5 shrink-0">{t.icon}</span>
      <div className="min-w-0 flex-1">{children}</div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

/* -------------------------- ThemeToggle --------------------------- */
export function ThemeToggle() {
  const { t } = useI18n()
  const [dark, setDark] = useState<boolean | null>(null)

  useEffect(() => {
    setDark(document.documentElement.classList.contains('dark'))
  }, [])

  function toggle() {
    const next = !document.documentElement.classList.contains('dark')
    document.documentElement.classList.toggle('dark', next)
    try {
      localStorage.setItem('theme', next ? 'dark' : 'light')
    } catch {
      /* storage may be unavailable; theme still applies for the session */
    }
    setDark(next)
  }

  const label = dark ? t('theme.toLight') : t('theme.toDark')
  return (
    <button
      type="button"
      onClick={toggle}
      className="btn btn-ghost btn-icon border border-line"
      aria-label={label}
      title={label}
    >
      {dark ? <SunIcon className="h-[18px] w-[18px]" /> : <MoonIcon className="h-[18px] w-[18px]" />}
    </button>
  )
}

/* ------------------------- LanguageToggle ------------------------- */
export function LanguageToggle() {
  const { lang, setLang, t } = useI18n()
  const options: { code: Lang; short: string; full: string }[] = [
    { code: 'en', short: t('lang.englishShort'), full: t('lang.english') },
    { code: 'hi', short: t('lang.hindiShort'), full: t('lang.hindi') },
  ]
  return (
    <div
      role="group"
      aria-label={t('lang.label')}
      className="inline-flex items-center rounded-lg border border-line bg-surface p-0.5 text-xs font-semibold"
    >
      {options.map(o => {
        const active = lang === o.code
        return (
          <button
            key={o.code}
            type="button"
            lang={o.code}
            onClick={() => setLang(o.code)}
            aria-pressed={active}
            aria-label={o.full}
            title={o.full}
            className={cx(
              'rounded-md px-2.5 py-1 transition-all duration-150',
              active ? 'bg-primary text-primary-fg shadow-[var(--shadow-xs)]' : 'text-muted hover:text-foreground'
            )}
          >
            {o.short}
          </button>
        )
      })}
    </div>
  )
}

/* ---------------------------- AppHeader --------------------------- */
export function AppHeader({ right }: { right?: ReactNode }) {
  const { t } = useI18n()
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-canvas/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-5xl items-center justify-between gap-4 px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-fg shadow-[var(--shadow-primary)]">
            <ShieldIcon className="h-5 w-5" />
          </div>
          <div className="leading-tight">
            <p className="text-sm font-semibold tracking-tight text-foreground">{t('common.appName')}</p>
            <p className="text-xs text-muted">{t('common.appSubtitle')}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {right}
          <LanguageToggle />
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}

/* ------------------------------ Toast ----------------------------- */
/** Minimal ephemeral toast: render <Toast msg={...} /> from local state. */
export function Toast({ message, onDone }: { message: string; onDone: () => void }) {
  useEffect(() => {
    const id = setTimeout(onDone, 2200)
    return () => clearTimeout(id)
  }, [message, onDone])
  return (
    <div className="animate-rise-in fixed bottom-5 left-1/2 z-50 -translate-x-1/2">
      <div className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3.5 py-2 text-sm font-medium text-foreground shadow-[var(--shadow-lg)]">
        <CheckIcon className="h-4 w-4 text-success" />
        {message}
        <button onClick={onDone} className="ml-1 text-faint hover:text-foreground" aria-label="Dismiss">
          <XIcon className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
