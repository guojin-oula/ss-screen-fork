import { createRootRoute, createRoute, createRouter, Navigate } from "@tanstack/react-router";
import { Shell } from "./Shell";
import { ProjectsPage } from "../features/ProjectsPage";
import { ProjectPage } from "../features/ProjectPage";
import { NewRunPage } from "../features/NewRunPage";
import { RunPage } from "../features/RunPage";
import { ArtifactPage } from "../features/ArtifactPage";
import { DatasetPage } from "../features/DatasetPage";
import { NewDatasetPage } from "../features/NewDatasetPage";
import { NewWBMDatasetPage } from "../features/NewWBMDatasetPage";
import { NewCompositionPage } from "../features/NewCompositionPage";
import { NewCondensationPage } from "../features/NewCondensationPage";

const rootRoute = createRootRoute({ component: Shell });
const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: "/", component: () => <Navigate to="/projects" /> });
const projectsRoute = createRoute({ getParentRoute: () => rootRoute, path: "/projects", component: ProjectsPage });
const projectRoute = createRoute({ getParentRoute: () => rootRoute, path: "/projects/$projectId", component: ProjectPage });
const newRunRoute = createRoute({ getParentRoute: () => rootRoute, path: "/projects/$projectId/runs/new", component: NewRunPage });
const newDatasetRoute = createRoute({ getParentRoute: () => rootRoute, path: "/projects/$projectId/datasets/new", component: NewDatasetPage });
const newWBMDatasetRoute = createRoute({ getParentRoute: () => rootRoute, path: "/projects/$projectId/datasets/wbm/new", component: NewWBMDatasetPage });
const datasetRoute = createRoute({ getParentRoute: () => rootRoute, path: "/datasets/$datasetId", component: DatasetPage });
const newCompositionRoute = createRoute({ getParentRoute: () => rootRoute, path: "/datasets/$datasetId/composition/new", component: NewCompositionPage });
const newCondensationRoute = createRoute({ getParentRoute: () => rootRoute, path: "/runs/$runId/condensation/new", component: NewCondensationPage });
const runRoute = createRoute({ getParentRoute: () => rootRoute, path: "/runs/$runId", component: RunPage });
const artifactRoute = createRoute({ getParentRoute: () => rootRoute, path: "/artifacts/$artifactId", component: ArtifactPage });
const routeTree = rootRoute.addChildren([indexRoute, projectsRoute, projectRoute, newRunRoute, newDatasetRoute, newWBMDatasetRoute, datasetRoute, newCompositionRoute, newCondensationRoute, runRoute, artifactRoute]);
export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" { interface Register { router: typeof router; } }
