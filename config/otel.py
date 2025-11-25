"""OpenTelemetry configuration for Django."""
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# This gets called when Django starts up
def configure_opentelemetry():
    """Configure OpenTelemetry for Django application."""
    
    # Enable logging instrumentation
    LoggingInstrumentor().instrument(set_logging_format=True)
    
    logger = logging.getLogger(__name__)
    logger.info("OpenTelemetry logging instrumentation initialized")