import { Link } from "react-router-dom";
import type { S } from "../api/client";
import { fmtShort } from "../lib/format";
import { Empty } from "./ui";

export function AlertList({ alerts }: { alerts: S["Alert"][] }) {
  if (alerts.length === 0) return <Empty>Không có cảnh báo nào ở mức này.</Empty>;
  return (
    <ul className="alerts">
      {alerts.map((a) => (
        <li key={a.id}>
          <span className="sev" data-s={a.severity} title={a.severity === "critical" ? "Nghiêm trọng" : "Cảnh báo"} />
          <div>
            {a.block_id ? (
              <Link className="alerts__t" to={`/anomalies/${encodeURIComponent(a.block_id)}`}>{a.title}</Link>
            ) : (
              <span className="alerts__t">{a.title}</span>
            )}
            <div className="alerts__d">{a.detail}</div>
          </div>
          <time className="alerts__w" dateTime={a.ts}>{fmtShort(a.ts)}</time>
        </li>
      ))}
    </ul>
  );
}
