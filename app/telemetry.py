from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import ReadableSpan
from typing import Sequence
from fastapi import FastAPI
import time
from .env_config import env_config


class PrettyConsoleExporter(SpanExporter):
    """自定义的控制台导出器，提供更易读的输出格式"""

    def export(self, spans: Sequence[ReadableSpan]) -> None:
        for span in spans:
            if not span or not span.context:
                continue
            # if "http send" in span.name.lower():
            #     continue

            # 打印基本信息
            print("\n" + "=" * 80)
            print(f"Span: {span.name}")

            # 计算持续时间
            if span.start_time is not None and span.end_time is not None:
                duration = (span.end_time - span.start_time) / 1e6
                print(f"Duration: {duration:.2f}ms")

            # 打印属性
            if span.attributes:
                print("\nAttributes:")
                for key, value in span.attributes.items():
                    print(f"  {key}: {value}")

            # 打印事件
            if span.events:
                print("\nEvents:")
                for event in span.events:
                    print(f"  {event.name} at {event.timestamp}")
                    if event.attributes:
                        for key, value in event.attributes.items():
                            print(f"    {key}: {value}")

            print("=" * 80)

    def shutdown(self) -> None:
        pass


def init_telemetry(app: FastAPI):
    """初始化 FastAPI 的 OpenTelemetry instrumentation"""
    resource = Resource.create(
        {ResourceAttributes.SERVICE_NAME: "llm-cache-server", "env": env_config.ENV}
    )
    tracer_provider = TracerProvider(resource=resource)

    if env_config.NEW_RELIC_LICENSE_KEY:
        otlp_exporter = OTLPSpanExporter(
            endpoint="https://otlp.nr-data.net:4318/v1/traces",
            headers={
                "api-key": env_config.NEW_RELIC_LICENSE_KEY,
            },
        )
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    console_exporter = PrettyConsoleExporter()
    tracer_provider.add_span_processor(SimpleSpanProcessor(console_exporter))

    trace.set_tracer_provider(tracer_provider)
    FastAPIInstrumentor.instrument_app(app, exclude_spans=["send"])


# 获取 tracer
tracer = trace.get_tracer(__name__)


class Timer:
    """用于测量时间的上下文管理器"""

    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.ended = False

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.ended:
            self.end_time = time.time()
            self.ended = True

    @property
    def duration(self):
        """返回持续时间（毫秒）"""
        if self.start_time is None or self.end_time is None:
            return 0
        return (self.end_time - self.start_time) * 1000  # 转换为毫秒
