from deep_translator import GoogleTranslator

LANG_FIX = {
    "zh": "zh-CN",
    "cn": "zh-CN",
    "tw": "zh-TW",
    "zh-cn": "zh-CN",
    "zh-tw": "zh-TW",
    "jp": "ja",
    "kr": "ko",
}

def translate(text, target="en", source="auto"):
    try:
        target = LANG_FIX.get(target, target)
        source = LANG_FIX.get(source, source) if source else "auto"
        return GoogleTranslator(source=source, target=target).translate(text)
    except Exception as e:
        print("❌ translate error:", e)
        return text