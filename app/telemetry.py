from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from fastapi import FastAPI
import time
import os
from .env_config import env_config


def init_telemetry(app: FastAPI):
    """初始化 FastAPI 的 OpenTelemetry instrumentation"""

    # 创建 New Relic OTLP HTTP 导出器
    otlp_exporter = OTLPSpanExporter(
        endpoint="https://otlp.nr-data.net:4318/v1/traces",
        headers={
            "api-key": os.environ.get("NEW_RELIC_LICENSE_KEY", ""),
        },
    )

    # 初始化 tracer provider
    resource = Resource.create(
        {
            ResourceAttributes.SERVICE_NAME: "llm-cache-server",
            "env": os.environ.get("ENV", "development"),
        }
    )

    tracer_provider = TracerProvider(resource=resource)

    # 使用批处理 span processor
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # 设置全局 tracer provider
    trace.set_tracer_provider(tracer_provider)

    # 初始化 FastAPI instrumentation
    FastAPIInstrumentor.instrument_app(app)


# 获取 tracer
tracer = trace.get_tracer(__name__)


class Timer:
    """用于测量时间的上下文管理器"""

    def __init__(self):
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()

    @property
    def duration(self):
        """返回持续时间（毫秒）"""
        if self.start_time is None or self.end_time is None:
            return 0
        return (self.end_time - self.start_time) * 1000  # 转换为毫秒
