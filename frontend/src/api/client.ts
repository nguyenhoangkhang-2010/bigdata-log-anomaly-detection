import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

/** Kiểu dữ liệu lấy thẳng từ api/openapi.yaml (npm run gen:api). */
export type S = components["schemas"];

export const api = createClient<paths>({ baseUrl: import.meta.env.VITE_API_URL ?? "" });

export class ApiError extends Error {
  constructor(public status: number, title: string, public detail?: string | null) {
    super(title);
  }
}

export async function unwrap<T>(
  p: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let res;
  try {
    res = await p;
  } catch {
    throw new ApiError(0, "Không kết nối được tới API", "Backend đã chạy chưa? (uvicorn app.main:app --port 8000)");
  }
  if (res.data === undefined) {
    const e = res.error as Partial<S["Problem"]> | undefined;
    throw new ApiError(res.response.status, e?.title ?? res.response.statusText, e?.detail);
  }
  return res.data;
}
