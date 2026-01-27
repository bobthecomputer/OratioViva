import { createContext, useContext, useState, useEffect, useCallback } from 'react';

const I18nContext = createContext(null);

const storage = {
  get(key) {
    if (typeof window === "undefined") return null;
    try {
      return window.localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  set(key, value) {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(key, value);
    } catch {}
  },
};

const loadLocale = async (lang) => {
  try {
    const module = await import(`./locales/${lang}.json`);
    return module.default || module;
  } catch {
    console.warn(`Failed to load locale: ${lang}`);
    return {};
  }
};

export function I18nProvider({ children, defaultLang = 'en' }) {
  const [lang, setLang] = useState(defaultLang);
  const [translations, setTranslations] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const savedLang = storage.get("oratioviva_lang");
    const initialLang = savedLang || defaultLang;
    setLang(initialLang);
  }, [defaultLang]);

  useEffect(() => {
    loadLocale(lang).then((t) => {
      setTranslations(t);
      setLoading(false);
    });
  }, [lang]);

  const t = useCallback((key, params = {}) => {
    const keys = key.split('.');
    let result = translations;
    for (const k of keys) {
      result = result?.[k];
      if (result === undefined) return key;
    }
    
    if (typeof result === 'string') {
      return result.replace(/\{(\w+)\}/g, (_, paramKey) => params[paramKey] ?? `{${paramKey}}`);
    }
    return key;
  }, [translations]);

  const changeLanguage = useCallback((newLang) => {
    setLang(newLang);
    storage.set("oratioviva_lang", newLang);
  }, []);

  return (
    <I18nContext.Provider value={{ lang, t, changeLanguage, loading, translations }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useTranslation() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useTranslation must be used within I18nProvider');
  }
  return context;
}

export default I18nContext;
