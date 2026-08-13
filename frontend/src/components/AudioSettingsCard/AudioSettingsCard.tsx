import { useMemo } from "react";
import {
  Box,
  IconButton,
  MenuItem,
  Select,
  Stack,
  Switch,
  Tooltip,
  Typography,
} from "@mui/material";
import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";
import TuneRoundedIcon from "@mui/icons-material/TuneRounded";
import GlassCard from "../common/GlassCard";
import LevelMeter from "../common/LevelMeter";
import { useSettings } from "../../hooks/useSettings";
import { useIpc } from "../../hooks/useIpc";
import { useDevices } from "../../hooks/useDevices";
import { useLanguageCatalog, useVoiceCatalog, friendlyVoiceName, voiceModelKey } from "../../hooks/useCatalog";
import { useStore } from "../../state/store";
import { useT } from "../../i18n";

/** Card "Fala Recebida — Config." — dispositivo de loopback, fonte do áudio
 * (todo o pc vs. app específico), idiomas candidatos, teste, TTS da fala
 * recebida. Equivalente ao topo de _build_settings_panel() em ui/app.py. */
export default function AudioSettingsCard() {
  const { settings, update } = useSettings();
  const { call } = useIpc();
  const { t } = useT();
  const { loopbackDevices, sessionApps, refreshSessionApps, audioOutputDevices } = useDevices();
  const langs = useLanguageCatalog();

  const testInProgress = useStore((s) => s.testInProgress);
  const setTestInProgress = useStore((s) => s.setTestInProgress);
  const testResult = useStore((s) => s.testResult);
  const levelMeter = useStore((s) => s.levelMeter);

  const { normalizedLang, voices: receivedVoices } = useVoiceCatalog(langs[settings.from_lang]);
  const receivedVoice = settings.voice_overrides[normalizedLang] ?? "";

  // Trocar dispositivo/fonte/app com a escuta JÁ rodando não reconfigura a
  // captura ao vivo (diferente de idioma/overlay/TTS, que são lidos a cada
  // ciclo) — o pipeline continua preso no alvo antigo até parar e iniciar de
  // novo. Bug real reportado pelo usuário: trocou pra "Discord" na UI mas a
  // captura continuou vindo do app anterior. Trava os campos nesse meio
  // tempo em vez de deixar a UI mentir sobre o que está sendo escutado.
  const receivedRunning = useStore((s) => s.receivedRunning);

  const appOptions = useMemo(() => {
    const opts = sessionApps.map((a) => ({ value: a.executable, label: `${a.display_name} — ${a.executable}` }));
    const savedExe = settings.speaker_target_executable;
    if (savedExe && !opts.some((o) => o.value === savedExe)) {
      opts.unshift({ value: savedExe, label: `${savedExe}${t("audioSettings.waitingApp")}` });
    }
    return opts;
  }, [sessionApps, settings.speaker_target_executable, t]);

  const isAppMode = settings.speaker_audio_source_mode === "application";

  const runTest = async () => {
    setTestInProgress(true);
    try {
      await call("received.test", { duration: 4 });
    } catch {
      setTestInProgress(false);
    }
  };

  return (
    <GlassCard title={t("audioSettings.title")} dense>
      <Stack spacing={1.5}>
        <Stack spacing={0.75}>
          <Typography variant="body2" sx={{ color: "text.secondary" }}>
            {t("audioSettings.device")}
          </Typography>
          <Select
            fullWidth
            size="small"
            value={settings.received_device}
            displayEmpty
            disabled={receivedRunning}
            onChange={(e) => update({ received_device: e.target.value })}
          >
            {loopbackDevices.length === 0 && <MenuItem value="">{t("audioSettings.noDevice")}</MenuItem>}
            {loopbackDevices.map((d) => (
              <MenuItem key={d.index} value={d.name}>
                {d.name}
              </MenuItem>
            ))}
          </Select>
        </Stack>

        <Stack spacing={0.75}>
          <Tooltip title={t("audioSettings.sourceTooltip")} placement="right">
            <Typography variant="body2" sx={{ color: "text.secondary", width: "fit-content" }}>
              {t("audioSettings.source")}
            </Typography>
          </Tooltip>
          <Select
            fullWidth
            size="small"
            value={settings.speaker_audio_source_mode}
            disabled={receivedRunning}
            onChange={(e) => update({ speaker_audio_source_mode: e.target.value as any })}
          >
            <MenuItem value="full_device">{t("audioSettings.sourceFullDevice")}</MenuItem>
            <MenuItem value="application">{t("audioSettings.sourceApplication")}</MenuItem>
          </Select>
        </Stack>

        {isAppMode && (
          <Stack direction="row" spacing={1}>
            <Select
              fullWidth
              size="small"
              value={settings.speaker_target_executable}
              displayEmpty
              disabled={receivedRunning}
              onChange={(e) => update({ speaker_target_executable: e.target.value })}
            >
              {appOptions.length === 0 && <MenuItem value="">{t("audioSettings.noApp")}</MenuItem>}
              {appOptions.map((o) => (
                <MenuItem key={o.value} value={o.value}>
                  {o.label}
                </MenuItem>
              ))}
            </Select>
            <Tooltip title={t("audioSettings.refreshApps")}>
              {/* span: IconButton disabled não dispara eventos de mouse — sem
                  esse wrapper o Tooltip nunca aparece nesse estado (MUI). O
                  Tooltip clona o filho direto sem nó extra, então é o span
                  (não mais o IconButton) que vira o item flex de verdade
                  dentro do Stack — o flexShrink precisa estar aqui, senão o
                  ícone pode ser espremido num Select vizinho com nome longo. */}
              <span style={{ flexShrink: 0 }}>
                <IconButton onClick={() => refreshSessionApps()} disabled={receivedRunning}>
                  <RefreshRoundedIcon fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          </Stack>
        )}
        {receivedRunning && (
          <Typography variant="caption" sx={{ color: "text.secondary" }}>
            {t("audioSettings.sourceLockedHint")}
          </Typography>
        )}

        <Stack spacing={1}>
          <Tooltip title={t("audioSettings.testTooltip")}>
            <span>
              <Box
                component="button"
                onClick={runTest}
                disabled={testInProgress}
                sx={{
                  width: "100%",
                  cursor: testInProgress ? "default" : "pointer",
                  border: "1px solid rgba(255,255,255,0.12)",
                  borderRadius: 999,
                  background: "rgba(255,255,255,0.04)",
                  color: "inherit",
                  py: 0.9,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 1,
                  fontFamily: "inherit",
                  fontWeight: 600,
                  "&:hover": { background: testInProgress ? undefined : "rgba(0,229,255,0.08)" },
                }}
              >
                <TuneRoundedIcon fontSize="small" />
                {testInProgress ? t("audioSettings.testing") : t("audioSettings.test")}
              </Box>
            </span>
          </Tooltip>
          <LevelMeter level={levelMeter} />
          {testResult && (
            <Typography variant="caption" sx={{ color: testResult.error ? "#FF3B5C" : "text.secondary" }}>
              {testResult.error
                ? `${t("audioSettings.testFailed")} ${testResult.error}`
                : testResult.text || t("audioSettings.testNoSpeech")}
            </Typography>
          )}
        </Stack>

        <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between" }}>
          <Tooltip title={t("audioSettings.receivedTtsTooltip")} placement="right">
            <Typography variant="body2">{t("audioSettings.receivedTts")}</Typography>
          </Tooltip>
          <Switch checked={settings.received_tts} onChange={(e) => update({ received_tts: e.target.checked })} />
        </Stack>

        <Stack spacing={0.75}>
          <Tooltip title={t("audioSettings.receivedTtsOutputTooltip")} placement="right">
            <Typography variant="body2" sx={{ color: "text.secondary", width: "fit-content" }}>
              {t("audioSettings.receivedTtsOutput")}
            </Typography>
          </Tooltip>
          <Select
            fullWidth
            size="small"
            value={settings.received_tts_output}
            displayEmpty
            onChange={(e) => update({ received_tts_output: e.target.value })}
          >
            {audioOutputDevices.map((d) => (
              <MenuItem key={d.index} value={`${d.index} - ${d.name}`}>
                {d.index} - {d.name}
              </MenuItem>
            ))}
          </Select>
        </Stack>

        <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
          <Typography variant="body2" sx={{ color: "text.secondary", flexShrink: 0 }}>
            {t("audioSettings.voice")}
          </Typography>
          <Select
            fullWidth
            size="small"
            value={receivedVoice}
            displayEmpty
            onChange={(e) =>
              update({ voice_overrides: { ...settings.voice_overrides, [normalizedLang]: e.target.value } })
            }
          >
            {receivedVoices.map((v) => (
              <MenuItem key={v.id} value={v.id}>
                {v.gender === "F" ? "♀" : "♂"} {friendlyVoiceName(v)} — {t(voiceModelKey(v))}
              </MenuItem>
            ))}
          </Select>
        </Stack>
      </Stack>
    </GlassCard>
  );
}
