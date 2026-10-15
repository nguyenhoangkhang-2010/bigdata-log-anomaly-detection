import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import { Shell } from "./components/Shell";
import { PageTitle } from "./components/ui";
import Alerts from "./pages/Alerts";
import AnomalyDetail from "./pages/AnomalyDetail";
import Anomalies from "./pages/Anomalies";
import Events from "./pages/Events";
import Logs from "./pages/Logs";
import Models from "./pages/Models";
import Overview from "./pages/Overview";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false, retry: 1 } },
});

function NotFound() {
  return (
    <>
      <PageTitle title="Không tìm thấy trang" lede="Địa chỉ này không có trong hệ thống. Chọn một mục ở thanh điều hướng, hoặc quay về tổng quan." />
      <Link className="btn back" to="/">← Về tổng quan</Link>
    </>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Shell />}>
            <Route index element={<Overview />} />
            <Route path="anomalies" element={<Anomalies />} />
            <Route path="anomalies/:blockId" element={<AnomalyDetail />} />
            <Route path="alerts" element={<Alerts />} />
            <Route path="events" element={<Events />} />
            <Route path="models" element={<Models />} />
            <Route path="logs" element={<Logs />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
