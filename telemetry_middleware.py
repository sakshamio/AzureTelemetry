"""
Custom middleware for handling correlation context and telemetry
"""

import uuid
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from opentelemetry import trace
from utils.correlation_context import CorrelationContext

class TelemetryMiddleware(BaseHTTPMiddleware):
    """Middleware to handle correlation context and request tracing"""
    
    def __init__(self, app):
        super().__init__(app)
        self.tracer = trace.get_tracer(__name__)
    
    async def dispatch(self, request: Request, call_next):
        """Process request with correlation context"""
        start_time = time.time()
        
        # Extract or generate request_id
        request_id = request.headers.get("x-request-id") or request.headers.get("request-id")
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Create correlation context
        correlation_ctx = CorrelationContext(
            request_id=request_id,
            operation_id=trace.get_current_span().get_span_context().trace_id,
            start_time=start_time
        )
        
        # Store in request state
        request.state.correlation_context = correlation_ctx
        
        # Start a span for the entire request
        with self.tracer.start_as_current_span(
            f"{request.method} {request.url.path}",
            kind=trace.SpanKind.SERVER
        ) as span:
            # Set span attributes
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.scheme", request.url.scheme)
            span.set_attribute("http.host", request.url.hostname or "")
            span.set_attribute("http.target", request.url.path)
            span.set_attribute("request_id", request_id)
            span.set_attribute("user_agent", request.headers.get("user-agent", ""))
            
            # Add request start event
            span.add_event("Request started", {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path
            })
            
            try:
                # Process the request
                response = await call_next(request)
                
                # Calculate total request duration
                duration = time.time() - start_time
                
                # Set response attributes
                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("request.duration_ms", duration * 1000)
                
                # Set span status based on response
                if response.status_code >= 400:
                    span.set_status(trace.Status(
                        trace.StatusCode.ERROR,
                        f"HTTP {response.status_code}"
                    ))
                else:
                    span.set_status(trace.Status(trace.StatusCode.OK))
                
                # Add completion event
                span.add_event("Request completed", {
                    "status_code": response.status_code,
                    "duration_ms": duration * 1000
                })
                
                # Add request_id to response headers for client tracking
                response.headers["x-request-id"] = request_id
                
                return response
                
            except Exception as e:
                # Record exception in span
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                span.add_event("Request failed with exception", {
                    "exception_type": type(e).__name__,
                    "exception_message": str(e)
                })
                raise