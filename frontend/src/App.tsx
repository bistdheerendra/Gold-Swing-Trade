import { useState } from "react";
import { DashboardShell } from "./components/DashboardShell";
import { BacktestPage } from "./components/BacktestPage";
import { MlDatasetPage } from "./components/MlDatasetPage";
import { MlModelLabPage } from "./components/MlModelLabPage";
import { RiskManagementPage } from "./components/RiskPanel";

export default function App() {
  const [page, setPage] = useState<
    "dashboard" | "backtest" | "ml" | "ml-lab" | "risk"
  >("dashboard");

  if (page === "backtest") {
    return <BacktestPage onBack={() => setPage("dashboard")} />;
  }
  if (page === "ml") {
    return <MlDatasetPage onBack={() => setPage("dashboard")} />;
  }
  if (page === "ml-lab") {
    return <MlModelLabPage onBack={() => setPage("dashboard")} />;
  }
  if (page === "risk") {
    return <RiskManagementPage onBack={() => setPage("dashboard")} />;
  }

  return (
    <DashboardShell
      onOpenBacktest={() => setPage("backtest")}
      onOpenMlDataset={() => setPage("ml")}
      onOpenMlLab={() => setPage("ml-lab")}
      onOpenRisk={() => setPage("risk")}
    />
  );
}
