from __future__ import annotations

from dataclasses import dataclass

from ssscreen_web.domain.errors import DomainError


@dataclass(frozen=True)
class PipelineSpec:
    name: str
    version: str
    stage: str
    task_type: str
    topic: str
    queue: str


PIPELINES = {
    "control-plane-demo": PipelineSpec(
        name="control-plane-demo",
        version="control-plane-v1",
        stage="control-plane-demo",
        task_type="example.generate-json",
        topic="ssscreen_web.example.generate_json",
        queue="control",
    ),
    "stage-1-mp-offline": PipelineSpec(
        name="stage-1-mp-offline",
        version="stage-1-mp-offline-v1",
        stage="stage-1-dataset",
        task_type="dataset.mp-offline",
        topic="ssscreen_web.dataset.mp_offline",
        queue="cpu",
    ),
    "stage-1-wbm-upload": PipelineSpec(
        name="stage-1-wbm-upload",
        version="stage-1-wbm-upload-v1",
        stage="stage-1-dataset",
        task_type="dataset.wbm-upload",
        topic="ssscreen_web.dataset.wbm_upload",
        queue="cpu",
    ),
    "stage-1a-composition": PipelineSpec(
        name="stage-1a-composition",
        version="stage-1a-composition-v1",
        stage="stage-1a-composition",
        task_type="composition.screen",
        topic="ssscreen_web.composition.screen",
        queue="cpu",
    ),
    "stage-2-condensation": PipelineSpec(
        name="stage-2-condensation",
        version="stage-2-condensation-v1",
        stage="stage-2-condensation",
        task_type="condensation.batch",
        topic="ssscreen_web.condensation.batch",
        queue="cpu",
    ),
}


def pipeline_spec(name: object) -> PipelineSpec:
    if not isinstance(name, str) or name not in PIPELINES:
        raise DomainError("pipeline.unsupported", "The requested pipeline is not supported")
    return PIPELINES[name]


def task_spec(task_type: str) -> PipelineSpec:
    for spec in PIPELINES.values():
        if spec.task_type == task_type:
            return spec
    raise DomainError("task.unsupported", "The requested task type is not supported")


def queue_for_topic(topic: str) -> str:
    for spec in PIPELINES.values():
        if spec.topic == topic:
            return spec.queue
    raise DomainError("outbox.unsupported_topic", "The outbox topic is not supported")
