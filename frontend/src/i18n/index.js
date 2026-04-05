import { reactive } from 'vue'

const state = reactive({
  locale: localStorage.getItem('depl0y_locale') || 'en',
  messages: {}
})

export function useI18n() {
  const t = (key, params = {}) => {
    const msg = state.messages[state.locale]?.[key]
      || state.messages['en']?.[key]
      || key
    return msg.replace(/\{(\w+)\}/g, (_, k) => params[k] ?? `{${k}}`)
  }
  return { t, locale: state.locale }
}

export function setLocale(locale) {
  state.locale = locale
  localStorage.setItem('depl0y_locale', locale)
}

export function loadMessages(locale, messages) {
  state.messages[locale] = messages
}

export function getCurrentLocale() {
  return state.locale
}
