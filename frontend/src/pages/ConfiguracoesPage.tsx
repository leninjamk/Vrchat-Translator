import { Grid } from "@mui/material";
import PageContainer from "../components/common/PageContainer";
import OverlayCard from "../components/OverlayCard/OverlayCard";
import UiLanguageCard from "../components/UiLanguageCard/UiLanguageCard";
import { useT } from "../i18n";

// Overlay deixou de ser uma seção própria da Sidebar e passou pra cá —
// pedido do usuário depois de ver o app rodando ("essa aba de overlay tem
// que ser configurações"). ShaderSourceCard saiu daqui e virou a aba própria
// "Temas" (pedido do usuário depois de ver o app rodando).
export default function ConfiguracoesPage() {
  const { t } = useT();
  return (
    <PageContainer title={t("page.configuracoes.title")} subtitle={t("page.configuracoes.subtitle")}>
      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 6 }}>
          <OverlayCard />
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <UiLanguageCard />
        </Grid>
      </Grid>
    </PageContainer>
  );
}
