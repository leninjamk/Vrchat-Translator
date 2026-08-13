import { useCallback } from "react";
import pt, { type TranslationKey } from "./pt";
import en from "./en";
import ja from "./ja";
import es from "./es";
import fr from "./fr";
import de from "./de";
import it from "./it";
import ko from "./ko";
import zh from "./zh";
import zhTW from "./zh-TW";
import ru from "./ru";
import ar from "./ar";
import hi from "./hi";
import tr from "./tr";
import nl from "./nl";
import pl from "./pl";
import sv from "./sv";
import { useSettings } from "../hooks/useSettings";

export type UiLanguage =
  | "pt"
  | "en"
  | "ja"
  | "es"
  | "fr"
  | "de"
  | "it"
  | "ko"
  | "zh"
  | "zh-TW"
  | "ru"
  | "ar"
  | "hi"
  | "tr"
  | "nl"
  | "pl"
  | "sv";

export const UI_LANGUAGES: Record<UiLanguage, string> = {
  pt: "Português",
  en: "English",
  ja: "日本語",
  es: "Español",
  fr: "Français",
  de: "Deutsch",
  it: "Italiano",
  ko: "한국어",
  zh: "中文（简体）",
  "zh-TW": "中文（繁體）",
  ru: "Русский",
  ar: "العربية",
  hi: "हिन्दी",
  tr: "Türkçe",
  nl: "Nederlands",
  pl: "Polski",
  sv: "Svenska",
};

const DICTIONARIES: Record<UiLanguage, Record<TranslationKey, string>> = {
  pt,
  en,
  ja,
  es,
  fr,
  de,
  it,
  ko,
  zh,
  "zh-TW": zhTW,
  ru,
  ar,
  hi,
  tr,
  nl,
  pl,
  sv,
};

export type { TranslationKey };

/** Idioma da INTERFACE do app — não confundir com os idiomas de tradução de
 * fala (página Idiomas). Persistido em settings.json (chave ui_language),
 * mesmo canal settings.get/settings.set de tudo mais (ver plano). */
export function useT() {
  const { settings } = useSettings();
  const lang = (settings.ui_language ?? "pt") as UiLanguage;
  const dict = DICTIONARIES[lang] ?? pt;

  const t = useCallback((key: TranslationKey) => dict[key] ?? pt[key] ?? key, [dict]);

  return { t, lang };
}
