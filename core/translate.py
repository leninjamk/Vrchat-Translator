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

def translate(text, target="en"):
    try:
        target = LANG_FIX.get(target, target)
        return GoogleTranslator(source="auto", target=target).translate(text)
    except Exception as e:
        print("❌ translate error:", e)
        return text