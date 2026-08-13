import { useMemo } from "react";
import { Box, Grid, MenuItem, Select, Stack, Switch, Typography } from "@mui/material";
import RecordVoiceOverRoundedIcon from "@mui/icons-material/RecordVoiceOverRounded";
import PageContainer from "../components/common/PageContainer";
import GlassCard from "../components/common/GlassCard";
import ActionButtons from "../components/ActionButtons/ActionButtons";
import StatusChip from "../components/StatusChip/StatusChip";
import { useStore } from "../state/store";
import { SECTIONS } from "../navigation";
import { neon } from "../theme/palette";
import { useT } from "../i18n";
import { useSettings } from "../hooks/useSettings";
import { useReceivedService } from "../hooks/useReceivedService";
import { useLanguageCatalog, useVoiceCatalog, friendlyVoiceName, voiceModelKey } from "../hooks/useCatalog";

const quickSelectSx = {
  minWidth: 128,
  "& .MuiSelect-select": { py: 0.5, fontSize: 13 },
};

export default function InicioPage() {
  const micStatus = useStore((s) => s.micStatus);
  const setActiveSection = useStore((s) => s.setActiveSection);
  const { t } = useT();
  const { running: receivedRunning, toggle: toggleReceived } = useReceivedService();
  const { settings, update } = useSettings();
  const langs = useLanguageCatalog();
  const toLangCode = langs[settings.to_lang];
  const { normalizedLang, voices } = useVoiceCatalog(toLangCode);
  const currentVoice = settings.voice_overrides[normalizedLang] ?? "";

  const originOptions = useMemo(() => Object.keys(langs), [langs]);
  const destOptions = useMemo(() => Object.keys(langs).filter((l) => l !== "Auto Detect"), [langs]);

  return (
    <PageContainer title={t("page.inicio.title")} subtitle={t("page.inicio.subtitle")}>
      <Stack spacing={3}>
        <GlassCard>
          <Stack spacing={2}>
            <Stack
              direction="row"
              sx={{ alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 2 }}
            >
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 700 }}>
                  {t("hero.title")}
                </Typography>
                <Typography variant="body2" sx={{ color: "text.secondary" }}>
                  {t("hero.description")}
                </Typography>
              </Box>
              <Stack spacing={1} sx={{ alignItems: "flex-end" }}>
                <StatusChip status={micStatus} />
                <Tooltip title={t("resources.listenOthersTooltip")}>
                  <Stack
                    direction="row"
                    spacing={0.5}
                    sx={{ alignItems: "center", color: receivedRunning ? neon.cyan : "text.secondary" }}
                  >
                    <RecordVoiceOverRoundedIcon sx={{ fontSize: 15 }} />
                    <Typography variant="caption">
                      {receivedRunning ? t("hero.receivedActive") : t("hero.receivedStopped")}
                    </Typography>
                    <Switch size="small" checked={receivedRunning} onChange={toggleReceived} />
                  </Stack>
                </Tooltip>
                <Stack direction="row" spacing={1}>
                  <Select
                    size="small"
                    value={settings.from_lang}
                    onChange={(e) => update({ from_lang: e.target.value })}
                    sx={quickSelectSx}
                  >
                    {originOptions.map((label) => (
                      <MenuItem key={label} value={label}>
                        {label}
                      </MenuItem>
                    ))}
                  </Select>
                  <Select
                    size="small"
                    value={settings.to_lang}
                    onChange={(e) => update({ to_lang: e.target.value })}
                    sx={quickSelectSx}
                  >
                    {destOptions.map((label) => (
                      <MenuItem key={label} value={label}>
                        {label}
                      </MenuItem>
                    ))}
                  </Select>
                </Stack>
                <Select
                  size="small"
                  displayEmpty
                  value={currentVoice}
                  onChange={(e) =>
                    update({ voice_overrides: { ...settings.voice_overrides, [normalizedLang]: e.target.value } })
                  }
                  sx={{ ...quickSelectSx, minWidth: 264 }}
                >
                  {voices.map((v) => (
                    <MenuItem key={v.id} value={v.id}>
                      {v.gender === "F" ? "♀" : "♂"} {friendlyVoiceName(v)} — {t(voiceModelKey(v))}
                    </MenuItem>
                  ))}
                </Select>
              </Stack>
            </Stack>
            <ActionButtons />
          </Stack>
        </GlassCard>

        <Grid container spacing={2}>
          {SECTIONS.filter((s) => s.id !== "inicio").map(({ id, labelKey, icon: Icon }) => (
            <Grid key={id} size={{ xs: 12, sm: 6, md: 3 }}>
              <GlassCard>
                <Stack
                  spacing={1}
                  onClick={() => setActiveSection(id)}
                  sx={{ alignItems: "flex-start", cursor: "pointer" }}
                >
                  <Box
                    sx={{
                      width: 38,
                      height: 38,
                      borderRadius: 2,
                      display: "grid",
                      placeItems: "center",
                      background: `linear-gradient(135deg, ${neon.cyan}22, ${neon.indigo}22)`,
                      color: neon.cyan,
                    }}
                  >
                    <Icon fontSize="small" />
                  </Box>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                    {t(labelKey)}
                  </Typography>
                </Stack>
              </GlassCard>
            </Grid>
          ))}
        </Grid>
      </Stack>
    </PageContainer>
  );
}
