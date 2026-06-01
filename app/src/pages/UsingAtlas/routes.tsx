import { Route, Routes } from "react-router-dom";
import { UsingAtlasLayout } from "./Layout";
import { EhiIgniteChallenge } from "./EhiIgniteChallenge";
import { GettingStarted } from "./GettingStarted";
import { ThePipeline } from "./ThePipeline";
import { PdfExtraction } from "./PdfExtraction";
import { Harmonization } from "./Harmonization";
import { TrustworthyAi } from "./TrustworthyAi";
import { Standards } from "./Standards";
import { FhirContextLab } from "./FhirContextLab";

export function UsingAtlasRoutes() {
  return (
    <Routes>
      <Route element={<UsingAtlasLayout />}>
        <Route index element={<EhiIgniteChallenge />} />
        <Route path="get-started" element={<GettingStarted />} />
        <Route path="pipeline" element={<ThePipeline />} />
        <Route path="pdf-extraction" element={<PdfExtraction />} />
        <Route path="harmonization" element={<Harmonization />} />
        <Route path="fhir-context-lab" element={<FhirContextLab />} />
        <Route path="trustworthy-ai" element={<TrustworthyAi />} />
        <Route path="standards" element={<Standards />} />
      </Route>
    </Routes>
  );
}
