import { useEffect, useState } from "react";
import { AppHeader, type AppPage } from "./components/AppHeader";
import { DashboardShell } from "./components/DashboardShell";
import { BacktestPage } from "./components/BacktestPage";
import { MlDatasetPage } from "./components/MlDatasetPage";
import { MlModelLabPage } from "./components/MlModelLabPage";
import { RiskManagementPage } from "./components/RiskPanel";
import { LivePaperTradePage } from "./components/LivePaperTradePage";
import { DEFAULT_SYMBOL, type TradeSymbol } from "./lib/symbols";
import { applyInstrumentTheme } from "./lib/theme";

export default function App() {
  const [page, setPage] = useState<AppPage>("dashboard");
  const [symbol, setSymbol] = useState<TradeSymbol>(DEFAULT_SYMBOL);

  useEffect(() => {
    applyInstrumentTheme(symbol);
  }, [symbol]);

  return (
    <div className="min-h-screen overflow-x-hidden">
      <AppHeader
        page={page}
        onNavigate={setPage}
        symbol={symbol}
        onSymbolChange={setSymbol}
      />
      {page === "dashboard" ? (
        <DashboardShell symbol={symbol} onSymbolChange={setSymbol} />
      ) : null}
      {page === "backtest" ? <BacktestPage /> : null}
      {page === "ml" ? <MlDatasetPage /> : null}
      {page === "ml-lab" ? <MlModelLabPage /> : null}
      {page === "risk" ? <RiskManagementPage /> : null}
      {page === "paper" ? (
        <LivePaperTradePage symbol={symbol} onSymbolChange={setSymbol} />
      ) : null}
    </div>
  );
}
