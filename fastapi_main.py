"""
FastAPI Application with Azure Application Insights and OpenTelemetry Integration
"""

import os
import uuid
import time
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# OpenTelemetry imports
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat

# Azure Monitor
from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter, AzureMonitorMetricExporter

# Import our custom modules
from services.chatbot_service import ChatbotService
from services.external_service import ExternalAPIService
from utils.telemetry_middleware import TelemetryMiddleware
from utils.correlation_context import CorrelationContext
from models.request_models import ChatbotRequest, ChatbotResponse

# Configuration
AZURE_APPLICATION_INSIGHTS_CONNECTION_STRING = os.getenv(
    "APPLICATIONINSIGHTS_CONNECTION_STRING",
    "InstrumentationKey=your-key-here;IngestionEndpoint=https://your-region.in.applicationinsights.azure.com/"
)

class TelemetrySetup:
    """Centralized telemetry configuration"""
    
    @staticmethod
    def setup_telemetry():
        # Create resource with service information
        resource = Resource.create({
            "service.name": "chatbot-api",
            "service.version": "1.0.0",
            "service.instance.id": str(uuid.uuid4())
        })
        
        # Setup tracing
        trace_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(trace_provider)
        
        # Azure Monitor trace exporter
        azure_trace_exporter = AzureMonitorTraceExporter(
            connection_string=AZURE_APPLICATION_INSIGHTS_CONNECTION_STRING
        )
        trace_provider.add_span_processor(BatchSpanProcessor(azure_trace_exporter))
        
        # Setup metrics
        azure_metric_exporter = AzureMonitorMetricExporter(
            connection_string=AZURE_APPLICATION_INSIGHTS_CONNECTION_STRING
        )
        metric_reader = PeriodicExportingMetricReader(
            exporter=azure_metric_exporter,
            export_interval_millis=30000  # Export every 30 seconds
        )
        metrics.set_meter_provider(MeterProvider(
            resource=resource,
            metric_readers=[metric_reader]
        ))
        
        # Setup propagation
        set_global_textmap(B3MultiFormat())
        
        # Auto-instrument external HTTP calls
        RequestsInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    TelemetrySetup.setup_telemetry()
    yield
    # Shutdown - cleanup if needed

# Create FastAPI application
app = FastAPI(
    title="Chatbot API with Azure App Insights",
    description="Sample application demonstrating comprehensive telemetry",
    version="1.0.0",
    lifespan=lifespan
)

# Add telemetry middleware
app.add_middleware(TelemetryMiddleware)

# Initialize services
chatbot_service = ChatbotService()
external_service = ExternalAPIService()

# Get telemetry instances
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Create custom metrics
request_counter = meter.create_counter(
    name="http_requests_total",
    description="Total number of HTTP requests",
    unit="1"
)

request_duration = meter.create_histogram(
    name="http_request_duration_seconds",
    description="HTTP request duration in seconds",
    unit="s"
)

dependency_duration = meter.create_histogram(
    name="dependency_call_duration_seconds",
    description="External dependency call duration in seconds",
    unit="s"
)

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Middleware to collect metrics"""
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Record metrics
    request_counter.add(1, {
        "method": request.method,
        "endpoint": str(request.url.path),
        "status_code": str(response.status_code)
    })
    
    request_duration.record(duration, {
        "method": request.method,
        "endpoint": str(request.url.path),
        "status_code": str(response.status_code)
    })
    
    return response

def get_correlation_context(request: Request) -> CorrelationContext:
    """Dependency to get correlation context"""
    return request.state.correlation_context

@app.get("/healthcheck")
async def healthcheck(correlation_ctx: CorrelationContext = Depends(get_correlation_context)):
    """Health check endpoint"""
    with tracer.start_as_current_span("healthcheck_processing") as span:
        span.set_attribute("request_id", correlation_ctx.request_id)
        span.set_attribute("operation", "healthcheck")
        
        # Simulate some processing
        await external_service.check_external_dependencies(correlation_ctx)
        
        span.add_event("Health check completed successfully")
        
        return {
            "status": "healthy",
            "request_id": correlation_ctx.request_id,
            "timestamp": time.time()
        }

@app.post("/chatbot_message", response_model=ChatbotResponse)
async def chatbot_message(
    request_data: ChatbotRequest,
    correlation_ctx: CorrelationContext = Depends(get_correlation_context)
):
    """Main chatbot endpoint"""
    with tracer.start_as_current_span("chatbot_message_processing") as span:
        try:
            span.set_attribute("request_id", correlation_ctx.request_id)
            span.set_attribute("user_message_length", len(request_data.message))
            span.set_attribute("user_id", request_data.user_id or "anonymous")
            
            span.add_event("Processing chatbot message request")
            
            # Process the message through our chatbot service
            response = await chatbot_service.process_message(
                request_data.message, 
                request_data.user_id,
                correlation_ctx
            )
            
            span.set_attribute("response_length", len(response.response))
            span.add_event("Chatbot message processed successfully")
            
            return response
            
        except ValueError as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise HTTPException(status_code=500, detail="Internal server error")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler with telemetry"""
    correlation_ctx = getattr(request.state, 'correlation_context', None)
    
    with tracer.start_as_current_span("exception_handler") as span:
        if correlation_ctx:
            span.set_attribute("request_id", correlation_ctx.request_id)
        
        span.record_exception(exc)
        span.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
        span.add_event("Unhandled exception occurred")
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "request_id": correlation_ctx.request_id if correlation_ctx else None
            }
        )

# Instrument FastAPI with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)