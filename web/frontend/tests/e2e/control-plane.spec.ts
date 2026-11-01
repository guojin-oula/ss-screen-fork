import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { expect, test, type Page } from "@playwright/test";

async function createProject(page: Page, name: string) {
  await page.goto("/projects");
  await page.getByRole("button", { name: "新建项目" }).click();
  await page.getByLabel("项目名称").fill(name);
  await page.getByRole("button", { name: "创建", exact: true }).click();
  await expect(page.getByText(name)).toBeVisible();
  await page.getByLabel(`打开项目 ${name}`).click();
  return page.url().split("/").at(-1)!;
}

async function waitForRun(page: Page, runId: string) {
  await expect.poll(async () => {
    const response = await page.request.get(`http://localhost:8000/api/v1/runs/${runId}`);
    return (await response.json() as { status: string }).status;
  }, { timeout: 20000 }).toBe("SUCCEEDED");
}

async function expectNoPageOverflow(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth
  );
  expect(overflow).toBe(false);
}

test("creates a project, runs the worker, and downloads the demo artifact", async ({ page }) => {
  const name = `E2E ${Date.now()}`;
  await createProject(page, name);
  await page.getByRole("link", { name: "Demo Run" }).click();
  await page.getByRole("button", { name: "创建草稿 Run" }).click();
  await expect(page.getByRole("button", { name: "启动" })).toBeVisible();
  await page.getByRole("button", { name: "启动" }).click();
  await expect(page.getByText("已完成").first()).toBeVisible({ timeout: 20000 });
  await expect(page.getByText("control-plane-demo.json")).toBeVisible();
  await expectNoPageOverflow(page);
  await page.getByLabel("查看 control-plane-demo.json").click();
  const expectedSha = await page.locator(".hash").innerText();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "下载" }).click()
  ]);
  const content = await readFile(await download.path());
  expect(createHash("sha256").update(content).digest("hex")).toBe(expectedSha);
});

test("shows deterministic failure and succeeds only after explicit retry", async ({ page }) => {
  const name = `Retry ${Date.now()}`;
  await createProject(page, name);
  await page.getByRole("link", { name: "Demo Run" }).click();
  await page.getByLabel("首次 Attempt 模拟失败").check();
  await page.getByRole("button", { name: "创建草稿 Run" }).click();
  await page.getByRole("button", { name: "启动" }).click();
  await expect(page.getByText("失败").first()).toBeVisible({ timeout: 20000 });
  await page.getByRole("button", { name: "重试 Task" }).click();
  await expect(page.getByText("已完成").first()).toBeVisible({ timeout: 20000 });
  await expect(page.getByText("#2 SUCCEEDED")).toBeVisible();
});

test("does not overflow the viewport", async ({ page }) => {
  await page.goto("/projects");
  await expectNoPageOverflow(page);
});

test("creates an auditable Stage 1 draft without exposing the server path", async ({ page }) => {
  const name = `Dataset ${Date.now()}`;
  await createProject(page, name);
  await page.getByRole("link", { name: "准备数据集" }).click();
  await expect(page.getByText("服务端 MP 离线快照")).toBeVisible();
  await page.getByLabel("数据集名称").fill("MP e-hull 0.02");
  await page.getByLabel("最大能量高于凸包值").fill("0.02");
  await page.getByRole("button", { name: "创建 Stage 1 草稿" }).click();
  await expect(page.getByText("Stage 1 · MP offline")).toBeVisible();
  await expect(page.getByText(/Core 1\.0/)).toBeVisible();
  await expect(page.getByText("0.02 eV/atom")).toBeVisible();
  await expect(page.locator("body")).not.toContainText("/vepfs-");
  await expectNoPageOverflow(page);
  await page.getByRole("button", { name: "取消" }).click();
  await expect(page.getByText("已取消").first()).toBeVisible();
});

test("shows frozen composition settings and a bounded candidate preview", async ({ page }) => {
  const projectId = await createProject(page, `Composition ${Date.now()}`);
  const xyz = Buffer.from(`2
Lattice="3 0 0 0 3 0 0 0 3" Properties=species:S:1:pos:R:3 WBM_idx=0 WBM_gap=0.2 WBM_e_hull=0.0 pbc="T T T"
Na 0 0 0
Cl 1.5 1.5 1.5
2
Lattice="3 0 0 0 3 0 0 0 3" Properties=species:S:1:pos:R:3 WBM_idx=1 WBM_gap=0.5 WBM_e_hull=0.0 pbc="T T T"
K 0 0 0
Cl 1.5 1.5 1.5
`);
  const datasetRunResponse = await page.request.post(
    `http://localhost:8000/api/v1/projects/${projectId}/datasets/wbm-upload`,
    {
      multipart: {
        dataset_label: "Two salts browser fixture",
        xyz_file: { name: "two-salts.extxyz", mimeType: "chemical/x-xyz", buffer: xyz }
      }
    }
  );
  expect(datasetRunResponse.ok()).toBe(true);
  const datasetRun = await datasetRunResponse.json() as { id: string };
  expect((await page.request.post(
    `http://localhost:8000/api/v1/runs/${datasetRun.id}/actions/start`
  )).ok()).toBe(true);
  await waitForRun(page, datasetRun.id);
  const datasets = await (await page.request.get(
    `http://localhost:8000/api/v1/projects/${projectId}/datasets`
  )).json() as Array<{ id: string }>;
  const compositionResponse = await page.request.post(
    `http://localhost:8000/api/v1/projects/${projectId}/runs`,
    {
      data: {
        pipeline: "stage-1a-composition",
        dataset_id: datasets[0].id,
        nelems: 2,
        max_bandgap: 1,
        max_e_hull: 0,
        min_group_size: 2,
        min_x_elements: 2
      }
    }
  );
  expect(compositionResponse.ok()).toBe(true);
  const compositionRun = await compositionResponse.json() as { id: string };
  expect((await page.request.post(
    `http://localhost:8000/api/v1/runs/${compositionRun.id}/actions/start`
  )).ok()).toBe(true);
  await waitForRun(page, compositionRun.id);

  await page.goto(`/runs/${compositionRun.id}`);
  await expect(page.getByLabel("组成筛选冻结配置")).toContainText("Stage 1a · Composition");
  await expect(page.getByLabel("组成筛选冻结配置")).toContainText("Two salts browser fixture");
  await expect(page.getByRole("heading", { name: "候选预览" })).toBeVisible();
  await expect(page.getByText("Cl2X1").first()).toBeVisible();
  await expect(page.getByRole("link", { name: "查看完整 CSV" })).toBeVisible();
  await expectNoPageOverflow(page);

  await page.getByRole("link", { name: "生成结构描述" }).click();
  await expect(page.getByRole("heading", { name: "生成结构描述" })).toBeVisible();
  await expect(page.getByText("2 条候选")).toBeVisible();
  await page.getByLabel("每批材料数").fill("1");
  await page.getByRole("button", { name: "创建结构描述草稿" }).click();
  await expect(page.getByLabel("结构描述冻结配置")).toContainText("Stage 2 · Condensation");
  await expect(page.getByLabel("结构描述冻结配置")).toContainText("Two salts browser fixture");
  await expect(page.getByRole("heading", { name: "结构凝聚进度" })).toBeVisible();
  await expect(page.getByText("按材料检查点续跑")).toBeVisible();
  await expectNoPageOverflow(page);
});
