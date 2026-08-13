import { MenuItem, Select, Stack, Typography } from "@mui/material";
import GlassCard from "../common/GlassCard";
import { useSettings } from "../../hooks/useSettings";
import { useT, UI_LANGUAGES, type UiLanguage } from "../../i18n";

/** Idioma da INTERFACE do app (17 opções, ver i18n/index.ts::UI_LANGUAGES) —
 * pedido do usuário pra deixar o programa "compatível com outros idiomas"
 * além do português. Não confundir com a página Idiomas, que é sobre os
 * idiomas de TRADUÇÃO DE FALA. */
export default function UiLanguageCard() {
  const { settings, update } = useSettings();
  const { t } = useT();

  return (
    <GlassCard title={t("uiLanguage.title")}>
      <Stack spacing={1}>
        <Typography variant="body2" sx={{ color: "text.secondary" }}>
          {t("uiLanguage.description")}
        </Typography>
        <Select
          size="small"
          value={settings.ui_language}
          onChange={(e) => update({ ui_language: e.target.value })}
          sx={{ maxWidth: 240 }}
        >
          {(Object.keys(UI_LANGUAGES) as UiLanguage[]).map((code) => (
            <MenuItem key={code} value={code}>
              {UI_LANGUAGES[code]}
            </MenuItem>
          ))}
        </Select>
      </Stack>
    </GlassCard>
  );
}
