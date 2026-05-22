import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.gcp_trace import CloudTraceSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

def setup_telemetry(app):
    try:
        # Check if project ID is available for Cloud Trace
        project_id = os.getenv("PROJECT_ID")
        if project_id:
            trace.set_tracer_provider(TracerProvider())
            cloud_exporter = CloudTraceSpanExporter(project_id=project_id)
            trace.get_tracer_provider().add_span_processor(
                BatchSpanProcessor(cloud_exporter)
            )
            FastAPIInstrumentor.instrument_app(app)
            logging.info("OpenTelemetry setup with Cloud Trace")
        else:
            logging.warning("PROJECT_ID not found, skipping Cloud Trace exporter")
    except Exception as e:
        logging.error(f"Failed to setup telemetry: {e}")

def get_tracer(name):
    return trace.get_tracer(name)
