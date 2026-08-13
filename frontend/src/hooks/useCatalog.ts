import { useEffect, useState } from "react";
import { useIpc } from "./useIpc";
import type { VoiceOption } from "../types/devices";
import type { TranslationKey } from "../i18n/pt";

/**
 * Nome "de gente" da voz (extraído do ID técnico do core/voices.py), e a
 * chave i18n do modelo por trás dela — em vez de mostrar o ID cru
 * ("pt-BR-FranciscaNeural") e um adjetivo de humor ("Amigável"), mostra o
 * nome original da voz ("Francisca") e o motor real ("EdgeTTS Neural").
 */
export function friendlyVoiceName(v: VoiceOption): string {
  const m = v.id.match(/^[a-z]{2}-[A-Z]{2}-(.+?)(?:Multilingual)?Neural$/);
  return m ? m[1] : v.id;
}

export function voiceModelKey(v: VoiceOption): TranslationKey {
  return /Multilingual/.test(v.id) ? "language.modelEdgeMultilingual" : "language.modelEdge";
}

/** core/languages.py::LANGS — {rótulo em português: código}. Buscado 1x via
 * catalog.languages (estático, não muda em runtime). */
export function useLanguageCatalog() {
  const { call, connected } = useIpc();
  const [langs, setLangs] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!connected) return;
    call<undefined, Record<string, string>>("catalog.languages").then(setLangs).catch(() => {});
  }, [connected, call]);

  return langs;
}

interface VoicesForLanguageResult {
  normalizedLang: string;
  voices: VoiceOption[];
}

/**
 * core/voices.py::voice_options_for(lang) — buscado sob demanda por idioma.
 * O backend também devolve `normalizedLang` (resultado de
 * normalize_lang_code(), ex.: "zh"→"zh-CN") — é a chave que voice_overrides
 * usa em settings.json, então o frontend nunca duplica essa regra de
 * normalização, só usa o valor que o Python já resolveu.
 */
export function useVoiceCatalog(langCode: string | undefined) {
  const { call, connected } = useIpc();
  const [result, setResult] = useState<VoicesForLanguageResult>({
    normalizedLang: langCode ?? "",
    voices: [],
  });

  useEffect(() => {
    if (!connected || !langCode) {
      setResult({ normalizedLang: langCode ?? "", voices: [] });
      return;
    }
    let cancelled = false;
    call<{ lang: string }, VoicesForLanguageResult>("catalog.voicesForLanguage", { lang: langCode })
      .then((r) => {
        if (!cancelled) setResult(r);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [connected, langCode, call]);

  return result;
}

