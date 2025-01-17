from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from fastapi import FastAPI
import time

# 初始化 tracer provider
resource = Resource.create({ResourceAttributes.SERVICE_NAME: "llm-cache-server"})

tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(tracer_provider)

# 获取 tracer
tracer = trace.get_tracer(__name__)


def init_telemetry(app: FastAPI):
    """初始化 FastAPI 的 OpenTelemetry instrumentation"""
    FastAPIInstrumentor.instrument_app(app)


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
