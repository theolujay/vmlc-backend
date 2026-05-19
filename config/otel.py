"""OpenTelemetry configuration for Django."""

from opentelemetry.instrumentation.logging import LoggingInstrumentor


# This gets called when Django starts up
def configure_opentelemetry():
    """Configure OpenTelemetry for Django application."""

    # Enable logging instrumentation
    LoggingInstrumentor().instrument(set_logging_format=True)

    # logger = logging.getLogger(__name__)
    # logger.info("OpenTelemetry logging instrumentation initialized")
