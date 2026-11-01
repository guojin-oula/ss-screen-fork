import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const client = createClient<paths>({ baseUrl: API_BASE_URL });

export class ApiError extends Error {
  constructor(public code: string, message: string) {
    super(message);
  }
}

function unwrap<T>(data: T | undefined, error: unknown): T {
  if (error) {
    const body = error as { code?: string; message?: string };
    throw new ApiError(body.code ?? "api.error", body.message ?? "请求失败，请稍后重试。");
  }
  if (data === undefined) throw new ApiError("api.empty_response", "服务返回了空响应。");
  return data;
}

export async function getLive() {
  const { data, error } = await client.GET("/health/live");
  return unwrap(data, error);
}

export async function getMe() {
  const { data, error } = await client.GET("/api/v1/me");
  return unwrap(data, error);
}

export async function getProjects() {
  const { data, error } = await client.GET("/api/v1/projects");
  return unwrap(data, error);
}

export async function createProject(body: { name: string; description: string }) {
  const { data, error } = await client.POST("/api/v1/projects", { body });
  return unwrap(data, error);
}

export async function getProject(projectId: string) {
  const { data, error } = await client.GET("/api/v1/projects/{project_id}", {
    params: { path: { project_id: projectId } }
  });
  return unwrap(data, error);
}

export async function getRuns(projectId: string) {
  const { data, error } = await client.GET("/api/v1/projects/{project_id}/runs", {
    params: { path: { project_id: projectId } }
  });
  return unwrap(data, error);
}

export async function createRun(projectId: string, body: { message: string; simulate_failure: boolean }) {
  const { data, error } = await client.POST("/api/v1/projects/{project_id}/runs", {
    params: { path: { project_id: projectId } },
    body: { pipeline: "control-plane-demo", dataset_label: null, dataset_id: null, composition_run_id: null, batch_size: 16, max_e_hull: 0.01, nelems: 2, max_bandgap: 1.0, min_group_size: 2, min_x_elements: 2, ...body }
  });
  return unwrap(data, error);
}

export async function createMPOfflineDatasetRun(
  projectId: string,
  body: { dataset_label: string; max_e_hull: number }
) {
  const { data, error } = await client.POST("/api/v1/projects/{project_id}/runs", {
    params: { path: { project_id: projectId } },
    body: {
      pipeline: "stage-1-mp-offline",
      message: `准备数据集：${body.dataset_label}`,
      simulate_failure: false,
      dataset_id: null,
      composition_run_id: null,
      batch_size: 16,
      nelems: 2,
      max_bandgap: 1.0,
      min_group_size: 2,
      min_x_elements: 2,
      ...body
    }
  });
  return unwrap(data, error);
}

export async function createCompositionRun(
  projectId: string,
  body: {
    dataset_id: string;
    nelems: number;
    max_bandgap: number;
    max_e_hull: number;
    min_group_size: number;
    min_x_elements: number;
  }
) {
  const { data, error } = await client.POST("/api/v1/projects/{project_id}/runs", {
    params: { path: { project_id: projectId } },
    body: {
      pipeline: "stage-1a-composition",
      message: "准备组成筛选",
      simulate_failure: false,
      dataset_label: null,
      composition_run_id: null,
      batch_size: 16,
      ...body
    }
  });
  return unwrap(data, error);
}

export async function createCondensationRun(
  projectId: string,
  body: { composition_run_id: string; batch_size: number }
) {
  const { data, error } = await client.POST("/api/v1/projects/{project_id}/runs", {
    params: { path: { project_id: projectId } },
    body: {
      pipeline: "stage-2-condensation",
      message: "准备结构描述",
      simulate_failure: false,
      dataset_label: null,
      dataset_id: null,
      nelems: 2,
      max_bandgap: 1.0,
      max_e_hull: 0.01,
      min_group_size: 2,
      min_x_elements: 2,
      ...body
    }
  });
  return unwrap(data, error);
}

export async function createWBMUploadRun(
  projectId: string,
  body: { datasetLabel: string; xyzFile: File; summaryFile?: File }
) {
  const form = new FormData();
  form.set("dataset_label", body.datasetLabel);
  form.set("xyz_file", body.xyzFile);
  if (body.summaryFile) form.set("summary_file", body.summaryFile);
  const response = await fetch(
    `${API_BASE_URL}/api/v1/projects/${encodeURIComponent(projectId)}/datasets/wbm-upload`,
    { method: "POST", body: form }
  );
  const payload = await response.json() as components["schemas"]["RunResponse"] | { code?: string; message?: string };
  if (!response.ok) {
    const error = payload as { code?: string; message?: string };
    throw new ApiError(error.code ?? "api.error", error.message ?? "上传失败，请稍后重试。");
  }
  return payload as components["schemas"]["RunResponse"];
}

export async function getDatasets(projectId: string) {
  const { data, error } = await client.GET("/api/v1/projects/{project_id}/datasets", {
    params: { path: { project_id: projectId } }
  });
  return unwrap(data, error);
}

export async function getDataset(datasetId: string) {
  const { data, error } = await client.GET("/api/v1/datasets/{dataset_id}", {
    params: { path: { dataset_id: datasetId } }
  });
  return unwrap(data, error);
}

export async function getRun(runId: string) {
  const { data, error } = await client.GET("/api/v1/runs/{run_id}", {
    params: { path: { run_id: runId } }
  });
  return unwrap(data, error);
}

export async function startRun(runId: string) {
  const { data, error } = await client.POST("/api/v1/runs/{run_id}/actions/start", {
    params: { path: { run_id: runId } }
  });
  return unwrap(data, error);
}

export async function cancelRun(runId: string) {
  const { data, error } = await client.POST("/api/v1/runs/{run_id}/actions/cancel", {
    params: { path: { run_id: runId } }
  });
  return unwrap(data, error);
}

export async function getTasks(runId: string) {
  const { data, error } = await client.GET("/api/v1/runs/{run_id}/tasks", {
    params: { path: { run_id: runId } }
  });
  return unwrap(data, error);
}

export async function getTask(taskId: string) {
  const { data, error } = await client.GET("/api/v1/tasks/{task_id}", {
    params: { path: { task_id: taskId } }
  });
  return unwrap(data, error);
}

export async function retryTask(taskId: string) {
  const { data, error } = await client.POST("/api/v1/tasks/{task_id}/actions/retry", {
    params: { path: { task_id: taskId } }
  });
  return unwrap(data, error);
}

export async function cancelTask(taskId: string) {
  const { data, error } = await client.POST("/api/v1/tasks/{task_id}/actions/cancel", {
    params: { path: { task_id: taskId } }
  });
  return unwrap(data, error);
}

export async function getArtifacts(runId: string) {
  const { data, error } = await client.GET("/api/v1/runs/{run_id}/artifacts", {
    params: { path: { run_id: runId } }
  });
  return unwrap(data, error);
}

export async function getCompositionPreview(runId: string, limit = 20) {
  const { data, error } = await client.GET("/api/v1/runs/{run_id}/composition-preview", {
    params: { path: { run_id: runId }, query: { limit } }
  });
  return unwrap(data, error);
}

export async function getCondensationPreview(runId: string, failureLimit = 20) {
  const { data, error } = await client.GET("/api/v1/runs/{run_id}/condensation-preview", {
    params: { path: { run_id: runId }, query: { failure_limit: failureLimit } }
  });
  return unwrap(data, error);
}

export async function getArtifact(artifactId: string) {
  const { data, error } = await client.GET("/api/v1/artifacts/{artifact_id}", {
    params: { path: { artifact_id: artifactId } }
  });
  return unwrap(data, error);
}

export function artifactDownloadUrl(artifactId: string) {
  return `${API_BASE_URL}/api/v1/artifacts/${artifactId}/download`;
}
