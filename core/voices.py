"""
Catalogo de vozes de TTS por idioma. Cada idioma tem uma lista de opcoes —
a PRIMEIRA da lista e sempre a voz que o app ja usava antes desse catalogo
existir (garante que ninguem que nao mexer na escolha de voz note diferenca).

Engine: "edge" (voz Neural do edge-tts / Microsoft) — sempre disponível, gratuita, sem instalar nada extra.
"""
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class VoiceOption:
    id: str            # ID da voz: "pt-BR-FranciscaNeural" (edge)
    engine: str         # "edge"
    gender: str         # "F" | "M"
    style: str          # rotulo curto pra exibir na combo


# Normaliza um codigo de idioma pro formato usado como chave do catalogo
# (ex: "zh" -> "zh-CN", "jp" -> "ja") — usado tanto pra escolher a voz quanto
# pra popular os seletores da UI, entao fica num lugar so.
_LANG_FIX = {
    "zh": "zh-CN", "cn": "zh-CN", "zh-cn": "zh-CN",
    "zh-tw": "zh-TW", "tw": "zh-TW",
    "jp": "ja", "kr": "ko",
}


def normalize_lang_code(lang: str) -> str:
    lang = (lang or "en").strip()
    return _LANG_FIX.get(lang.lower(), lang)


VOICE_CATALOG: Dict[str, List[VoiceOption]] = {
    "pt": [
        VoiceOption("pt-BR-FranciscaNeural", "edge", "F", "Amigável"),
        VoiceOption("pt-BR-AntonioNeural", "edge", "M", "Amigável"),
        VoiceOption("pt-BR-ThalitaMultilingualNeural", "edge", "F", "Multilíngue"),
    ],
    "en": [
        VoiceOption("en-US-JennyNeural", "edge", "F", "Gentil"),
        VoiceOption("en-US-GuyNeural", "edge", "M", "Enérgico"),
        VoiceOption("en-US-AriaNeural", "edge", "F", "Confiante"),
        VoiceOption("en-US-AndrewNeural", "edge", "M", "Caloroso"),
        VoiceOption("en-US-EmmaNeural", "edge", "F", "Alegre"),
        VoiceOption("en-US-BrianNeural", "edge", "M", "Casual"),
        VoiceOption("en-US-AvaMultilingualNeural", "edge", "F", "Multilíngue"),
        VoiceOption("en-US-AndrewMultilingualNeural", "edge", "M", "Multilíngue"),
    ],
    "es": [
        VoiceOption("es-ES-ElviraNeural", "edge", "F", "Amigável"),
        VoiceOption("es-ES-AlvaroNeural", "edge", "M", "Amigável"),
        VoiceOption("es-ES-XimenaNeural", "edge", "F", "Amigável"),
    ],
    "fr": [
        VoiceOption("fr-FR-DeniseNeural", "edge", "F", "Amigável"),
        VoiceOption("fr-FR-HenriNeural", "edge", "M", "Amigável"),
        VoiceOption("fr-FR-EloiseNeural", "edge", "F", "Amigável"),
        VoiceOption("fr-FR-VivienneMultilingualNeural", "edge", "F", "Multilíngue"),
        VoiceOption("fr-FR-RemyMultilingualNeural", "edge", "M", "Multilíngue"),
    ],
    "de": [
        VoiceOption("de-DE-KatjaNeural", "edge", "F", "Amigável"),
        VoiceOption("de-DE-ConradNeural", "edge", "M", "Amigável"),
        VoiceOption("de-DE-AmalaNeural", "edge", "F", "Amigável"),
        VoiceOption("de-DE-KillianNeural", "edge", "M", "Amigável"),
        VoiceOption("de-DE-SeraphinaMultilingualNeural", "edge", "F", "Multilíngue"),
        VoiceOption("de-DE-FlorianMultilingualNeural", "edge", "M", "Multilíngue"),
    ],
    "it": [
        VoiceOption("it-IT-ElsaNeural", "edge", "F", "Amigável"),
        VoiceOption("it-IT-DiegoNeural", "edge", "M", "Amigável"),
        VoiceOption("it-IT-IsabellaNeural", "edge", "F", "Amigável"),
        VoiceOption("it-IT-GiuseppeMultilingualNeural", "edge", "M", "Multilíngue"),
    ],
    "ja": [
        VoiceOption("ja-JP-NanamiNeural", "edge", "F", "Amigável"),
        VoiceOption("ja-JP-KeitaNeural", "edge", "M", "Amigável"),
    ],
    "ko": [
        VoiceOption("ko-KR-SunHiNeural", "edge", "F", "Amigável"),
        VoiceOption("ko-KR-InJoonNeural", "edge", "M", "Amigável"),
        VoiceOption("ko-KR-HyunsuMultilingualNeural", "edge", "M", "Multilíngue"),
    ],
    "zh-CN": [
        VoiceOption("zh-CN-XiaoxiaoNeural", "edge", "F", "Calorosa"),
        VoiceOption("zh-CN-YunxiNeural", "edge", "M", "Animado"),
        VoiceOption("zh-CN-XiaoyiNeural", "edge", "F", "Animada"),
        VoiceOption("zh-CN-YunyangNeural", "edge", "M", "Profissional"),
    ],
    "zh-TW": [
        VoiceOption("zh-TW-HsiaoChenNeural", "edge", "F", "Amigável"),
        VoiceOption("zh-TW-YunJheNeural", "edge", "M", "Amigável"),
        VoiceOption("zh-TW-HsiaoYuNeural", "edge", "F", "Amigável"),
    ],
    "ru": [
        VoiceOption("ru-RU-SvetlanaNeural", "edge", "F", "Amigável"),
        VoiceOption("ru-RU-DmitryNeural", "edge", "M", "Amigável"),
    ],
    "ar": [
        VoiceOption("ar-SA-ZariyahNeural", "edge", "F", "Amigável"),
        VoiceOption("ar-SA-HamedNeural", "edge", "M", "Amigável"),
    ],
    "hi": [
        VoiceOption("hi-IN-SwaraNeural", "edge", "F", "Amigável"),
        VoiceOption("hi-IN-MadhurNeural", "edge", "M", "Amigável"),
    ],
    "tr": [
        VoiceOption("tr-TR-EmelNeural", "edge", "F", "Amigável"),
        VoiceOption("tr-TR-AhmetNeural", "edge", "M", "Amigável"),
    ],
    "nl": [
        VoiceOption("nl-NL-ColetteNeural", "edge", "F", "Amigável"),
        VoiceOption("nl-NL-MaartenNeural", "edge", "M", "Amigável"),
        VoiceOption("nl-NL-FennaNeural", "edge", "F", "Amigável"),
    ],
    "pl": [
        VoiceOption("pl-PL-ZofiaNeural", "edge", "F", "Amigável"),
        VoiceOption("pl-PL-MarekNeural", "edge", "M", "Amigável"),
    ],
    "sv": [
        VoiceOption("sv-SE-SofieNeural", "edge", "F", "Amigável"),
        VoiceOption("sv-SE-MattiasNeural", "edge", "M", "Amigável"),
    ],
}

# Compatibilidade com o codigo existente: dict simples idioma -> voz padrao
# (sempre a primeira/original de cada lista, entao o comportamento de quem
# nao mexer em nada continua identico a antes desse catalogo existir).
VOICES: Dict[str, str] = {lang: opts[0].id for lang, opts in VOICE_CATALOG.items()}


def voice_options_for(lang: str) -> List[VoiceOption]:
    return VOICE_CATALOG.get(normalize_lang_code(lang), VOICE_CATALOG["en"])


def find_voice_option(lang: str, voice_id: str) -> "VoiceOption | None":
    if not voice_id:
        return None
    for opt in voice_options_for(lang):
        if opt.id == voice_id:
            return opt
    return None
