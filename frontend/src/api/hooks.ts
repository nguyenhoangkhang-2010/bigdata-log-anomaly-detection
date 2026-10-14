import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, unwrap, type S } from "./client";

type Q<T> = { [K in keyof T]?: T[K] };

export const useHealth = () =>
  useQuery({
    queryKey: ["health"],
    queryFn: () => unwrap(api.GET("/api/v1/health")),
    refetchInterval: 30_000,
    retry: false,
  });

export const useMeta = () =>
  useQuery({ queryKey: ["meta"], queryFn: () => unwrap(api.GET("/api/v1/meta")), staleTime: 60_000 });

export const useSummary = () =>
  useQuery({ queryKey: ["summary"], queryFn: () => unwrap(api.GET("/api/v1/overview/summary")) });

export const useTimeline = (bucket: S["Bucket"]) =>
  useQuery({
    queryKey: ["timeline", bucket],
    queryFn: () => unwrap(api.GET("/api/v1/overview/timeline", { params: { query: { bucket } } })),
    placeholderData: keepPreviousData,
  });

export const useComponents = (limit = 10) =>
  useQuery({
    queryKey: ["components", limit],
    queryFn: () => unwrap(api.GET("/api/v1/overview/components", { params: { query: { limit } } })),
  });

export const useAlerts = (severity?: S["Severity"], limit = 20) =>
  useQuery({
    queryKey: ["alerts", severity, limit],
    queryFn: () => unwrap(api.GET("/api/v1/alerts", { params: { query: { severity, limit } } })),
    placeholderData: keepPreviousData,
  });

export type AnomalyQuery = Q<{
  model: S["ModelName"];
  only_flagged: boolean;
  min_score: number;
  q: string;
  sort: "score_desc" | "score_asc" | "time_desc" | "time_asc" | "lines_desc";
  page: number;
  page_size: number;
}>;

export const useAnomalies = (query: AnomalyQuery) =>
  useQuery({
    queryKey: ["anomalies", query],
    queryFn: () => unwrap(api.GET("/api/v1/anomalies", { params: { query } })),
    placeholderData: keepPreviousData,
  });

export const useAnomaly = (blockId: string, model?: S["ModelName"]) =>
  useQuery({
    queryKey: ["anomaly", blockId, model],
    queryFn: () =>
      unwrap(api.GET("/api/v1/anomalies/{block_id}", { params: { path: { block_id: blockId }, query: { model } } })),
    retry: false,
  });

export const useEvents = (sort: "count_desc" | "lift_desc", limit = 50) =>
  useQuery({
    queryKey: ["events", sort, limit],
    queryFn: () => unwrap(api.GET("/api/v1/events", { params: { query: { sort, limit } } })),
    placeholderData: keepPreviousData,
  });

export const useModels = () =>
  useQuery({ queryKey: ["models"], queryFn: () => unwrap(api.GET("/api/v1/models")) });

export const useScoreDistribution = (model: S["ModelName"], bins = 40) =>
  useQuery({
    queryKey: ["score-dist", model, bins],
    queryFn: () =>
      unwrap(api.GET("/api/v1/models/{model}/score-distribution", { params: { path: { model }, query: { bins } } })),
    placeholderData: keepPreviousData,
  });

export type LogQuery = Q<{
  q: string;
  level: S["Level"];
  component: string;
  block_id: string;
  start: string;
  end: string;
  page: number;
  page_size: number;
}>;

export const useLogs = (query: LogQuery) =>
  useQuery({
    queryKey: ["logs", query],
    queryFn: () => unwrap(api.GET("/api/v1/logs", { params: { query } })),
    placeholderData: keepPreviousData,
  });
