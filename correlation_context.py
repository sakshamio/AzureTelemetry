"""
Correlation context for tracking requests across the application
"""

import time
from dataclasses import dataclass
from typing import Optional, Dict, Any
from opentelemetry import trace

@dataclass
class CorrelationContext:
    """Context object to correlate logs, traces, and metrics across a request"""
    
    request_id: str
    operation_id: Optional[int] = None
    start_time: float = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    additional_properties: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.start_time is None:
            self.start_time = time.time()
        
        if self.operation_id is None:
            current_span = trace.get_current_span()
            if current_span and current_span.get_span_context():
                self.operation_id = current_span.get_span_context().trace_id
        
        if self.additional_properties is None:
            self.additional_properties = {}
    
    def add_property(self, key: str, value: Any):
        """Add additional property to context"""
        self.additional_properties[key] = value
    
    def get_property(self, key: str, default: Any = None):
        """Get property from context"""
        return self.additional_properties.get(key, default)
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time since request start"""
        return time.time() - self.start_time
    
    def to_dict(self) -> dict:
        """Convert context to dictionary for logging"""
        return {
            "request_id": self.request_id,
            "operation_id": self.operation_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "elapsed_time_ms": self.get_elapsed_time() * 1000,
            **self.additional_properties
        }