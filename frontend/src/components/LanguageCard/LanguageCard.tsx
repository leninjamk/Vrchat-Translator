import { useMemo, useState } from "react";
import { MenuItem, Select, Slider, Stack, Typography } from "@mui/material";
import GlassCard from "../common/GlassCard";
import { useSettings } from "../../hooks/useSettings";
import { useIpc } from "../../hooks/useIpc";
import { useLanguageCatalog, useVoiceCatalog, friendlyVoiceName, voiceModelKey } from "../../hooks/useCatalog";
import { useT } from "../../i18n";

/** Card "Idiomas e voz" — origem, destino, voz da minha fala, pitch.
 * Equivalente a _build_language_voice_card() em ui/app.py. Pitch NÃO é
 * persistido (mesmo comportamento do app original — sempre volta a 0). */
export default function LanguageCard() {
  const { settings, update } = useSettings();
  const { call } = useIpc();
  const { t } = useT();
  const langs = useLanguageCatalog();
  const [pitch, setPitch] = useState(0);

  const toLangCode = langs[settings.to_lang];
  const { normalizedLang, voices } = useVoiceCatalog(toLangCode);
  const currentVoice = settings.voice_overrides[normalizedLang] ?? "";

  const originOptions = useMemo(() => Object.keys(langs), [langs]);
  const destOptions = useMemo(() => Object.keys(langs).filter((l) => l !== "Auto Detect"), [langs]);

  return (
    <GlassCard title={t("language.title")}>
      <Stack spacing={2.5}>
        <Stack spacing={0.75}>
          <Typography variant="body2" sx={{ color: "text.secondary" }}>
            {t("language.origin")}
          </Typography>
          <Select fullWidth size="small" value={settings.from_lang} onChange={(e) => update({ from_lang: e.target.value })}>
            {originOptions.map((label) => (
              <MenuItem key={label} value={label}>
                {label}
              </MenuItem>
            ))}
          </Select>
        </Stack>

        <Stack spacing={0.75}>
          <Typography variant="body2" sx={{ color: "text.secondary" }}>
            {t("language.destination")}
          </Typography>
          <Select fullWidth size="small" value={settings.to_lang} onChange={(e) => update({ to_lang: e.target.value })}>
            {destOptions.map((label) => (
              <MenuItem key={label} value={label}>
                {label}
              </MenuItem>
            ))}
          </Select>
        </Stack>

        <Stack spacing={0.75}>
          <Typography variant="body2" sx={{ color: "text.secondary" }}>
            {t("language.voice")}
          </Typography>
          <Select
            fullWidth
            size="small"
            value={currentVoice}
            displayEmpty
            onChange={(e) =>
              update({ voice_overrides: { ...settings.voice_overrides, [normalizedLang]: e.target.value } })
            }
          >
            {voices.map((v) => (
              <MenuItem key={v.id} value={v.id}>
                {v.gender === "F" ? "♀" : "♂"} {friendlyVoiceName(v)} — {t(voiceModelKey(v))}
              </MenuItem>
            ))}
          </Select>
        </Stack>

        <Stack spacing={0.5}>
          <Typography variant="body2" sx={{ color: "text.secondary" }}>
            {t("language.pitch")}
          </Typography>
          <Slider
            value={pitch}
            min={-50}
            max={50}
            onChange={(_, v) => setPitch(v as number)}
            onChangeCommitted={(_, v) => call("mic.setPitch", { pitch: v as number }).catch(() => {})}
          />
          <Stack direction="row" sx={{ justifyContent: "space-between" }}>
            <Typography variant="caption" sx={{ color: "text.secondary" }}>
              {t("language.pitchGrave")}
            </Typography>
            <Typography variant="caption" sx={{ color: "text.secondary" }}>
              {t("language.pitchAgudo")}
            </Typography>
          </Stack>
        </Stack>
      </Stack>
    </GlassCard>
  );
}
