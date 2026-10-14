import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

/** Đo bề rộng phần tử để vẽ SVG vừa khít. */
export function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(720);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(280, Math.floor(e.contentRect.width))));
    ro.observe(el);
    setW(Math.max(280, Math.floor(el.getBoundingClientRect().width)));
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

export function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function useDocumentTitle(title: string) {
  useEffect(() => {
    document.title = `${title} — LogAD`;
  }, [title]);
}

/** Trạng thái bộ lọc nằm trên URL (chia sẻ/refresh vẫn giữ). Đổi bộ lọc thì về trang 1. */
export function useUrlState<T extends Record<string, string>>(defaults: T) {
  const [sp, setSp] = useSearchParams();
  const state = Object.fromEntries(
    Object.keys(defaults).map((k) => [k, sp.get(k) ?? defaults[k]]),
  ) as T;
  const patch = useCallback(
    (next: Partial<T>) => {
      setSp(
        (prev) => {
          const out = new URLSearchParams(prev);
          for (const [k, v] of Object.entries(next)) {
            if (v === undefined || v === defaults[k]) out.delete(k);
            else out.set(k, v);
          }
          if (!("page" in next)) out.delete("page");
          return out;
        },
        { replace: true },
      );
    },
    [setSp, defaults],
  );
  return [state, patch] as const;
}
