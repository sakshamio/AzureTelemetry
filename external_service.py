"""
External API service with automatic dependency tracking via OpenTelemetry
"""

import asyncio
import time
import random
from typing import Dict, Any
import httpx
import requests
from opentelemetry import trace, metrics
from utils.correlation_context import CorrelationContext

class ExternalAPIService:
    """Service for making external API calls with comprehensive telemetry"""
    
    def __init__(self):
        self.tracer = trace.get_tracer(__name__)
        self.meter = metrics.get_meter(__name__)
        
        # Create custom metrics for dependencies
        self.dependency_calls_counter = self.meter.create_counter(
            name="external_dependency_calls_total",
            description="Total number of external dependency calls",
            unit="1"
        )
        
        self.dependency_duration = self.meter.create_histogram(
            name="external_dependency_duration_seconds",
            description="Duration of external dependency calls",
            unit="s"
        )
        
        self.dependency_errors_counter = self.meter.create_counter(
            name="external_dependency_errors_total",
            description="Total number of external dependency errors",
            unit="1"
        )
    
    async def check_external_dependencies(self, correlation_ctx: CorrelationContext) -> Dict[str, Any]:
        """Check health of external dependencies"""
        with self.tracer.start_as_current_span("check_external_dependencies") as span:
            span.set_attribute("request_id", correlation_ctx.request_id)
            span.add_event("Starting dependency health check")
            
            # Check multiple services concurrently
            tasks = [
                self._check_weather_service(correlation_ctx),
                self._check_news_service(correlation_ctx),
                self._check_stock_service(correlation_ctx)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            health_status = {
                "weather_service": not isinstance(results[0], Exception),
                "news_service": not isinstance(results[1], Exception),
                "stock_service": not isinstance(results[2], Exception)
            }
            
            span.set_attribute("all_services_healthy", all(health_status.values()))
            span.add_event("Dependency health check completed", health_status)
            
            return health_status
    
    async def get_weather_data(self, correlation_ctx: CorrelationContext) -> Dict[str, Any]:
        """Get weather data from external API"""
        with self.tracer.start_as_current_span("get_weather_data", kind=trace.SpanKind.CLIENT) as span:
            return await self._make_external_call(
                "weather_api",
                "https://api.openweathermap.org/data/2.5/weather",
                {"q": "London", "appid": "dummy_key"},
                span,
                correlation_ctx
            )
    
    async def get_news_data(self, correlation_ctx: CorrelationContext) -> Dict[str, Any]:
        """Get news data from external API"""
        with self.tracer.start_as_current_span("get_news_data", kind=trace.SpanKind.CLIENT) as span:
            return await self._make_external_call(
                "news_api",
                "https://newsapi.org/v2/top-headlines",
                {"country": "us", "apiKey": "dummy_key"},
                span,
                correlation_ctx
            )
    
    async def get_stock_data(self, correlation_ctx: CorrelationContext) -> Dict[str, Any]:
        """Get stock price data from external API"""
        with self.tracer.start_as_current_span("get_stock_data", kind=trace.SpanKind.CLIENT) as span:
            return await self._make_external_call(
                "stock_api",
                "https://api.finnhub.io/api/v1/quote",
                {"symbol": "AAPL", "token": "dummy_token"},
                span,
                correlation_ctx
            )
    
    async def _check_weather_service(self, correlation_ctx: CorrelationContext) -> bool:
        """Check weather service health"""
        with self.tracer.start_as_current_span("check_weather_service_health") as span:
            span.set_attribute("request_id", correlation_ctx.request_id)
            span.set_attribute("service_name", "weather_api")
            
            try:
                # Simulate health check call
                await asyncio.sleep(random.uniform(0.05, 0.15))
                
                # Simulate occasional failures
                if random.random() < 0.1:  # 10% failure rate
                    raise Exception("Weather service unavailable")
                
                span.add_event("Weather service health check passed")
                return True
                
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                return False
    
    async def _check_news_service(self, correlation_ctx: CorrelationContext) -> bool:
        """Check news service health"""
        with self.tracer.start_as_current_span("check_news_service_health") as span:
            span.set_attribute("request_id", correlation_ctx.request_id)
            span.set_attribute("service_name", "news_api")
            
            try:
                await asyncio.sleep(random.uniform(0.03, 0.12))
                
                if random.random() < 0.05:  # 5% failure rate
                    raise Exception("News service unavailable")
                
                span.add_event("News service health check passed")
                return True
                
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                return False
    
    async def _check_stock_service(self, correlation_ctx: CorrelationContext) -> bool:
        """Check stock service health"""
        with self.tracer.start_as_current_span("check_stock_service_health") as span:
            span.set_attribute("request_id", correlation_ctx.request_id)
            span.set_attribute("service_name", "stock_api")
            
            try:
                await asyncio.sleep(random.uniform(0.08, 0.20))
                
                if random.random() < 0.08:  # 8% failure rate
                    raise Exception("Stock service unavailable")
                
                span.add_event("Stock service health check passed")
                return True
                
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                return False
    
    async def _make_external_call(
        self,
        service_name: str,
        url: str,
        params: Dict[str, Any],
        span: trace.Span,
        correlation_ctx: CorrelationContext
    ) -> Dict[str, Any]:
        """Make external API call with comprehensive telemetry"""
        start_time = time.time()
        
        # Set span attributes for dependency
        span.set_attribute("request_id", correlation_ctx.request_id)
        span.set_attribute("http.method", "GET")
        span.set_attribute("http.url", url)
        span.set_attribute("service.name", service_name)
        span.set_attribute("dependency.type", "http")
        
        try:
            span.add_event(f"Starting external call to {service_name}", {
                "url": url,
                "params_count": len(params)
            })
            
            # For demo purposes, we'll simulate the API calls instead of making real ones
            # In production, these would be actual HTTP calls that are auto-instrumented
            response_data = await self._simulate_api_call(service_name, url, params, span)
            
            # Calculate call duration
            duration = time.time() - start_time
            
            # Record successful call metrics
            self.dependency_calls_counter.add(1, {
                "service": service_name,
                "status": "success",
                "method": "GET"
            })
            
            self.dependency_duration.record(duration, {
                "service": service_name,
                "status": "success"
            })
            
            # Set success attributes
            span.set_attribute("http.status_code", 200)
            span.set_attribute("dependency.success", True)
            span.set_attribute("dependency.duration_ms", duration * 1000)
            span.set_attribute("response.size", len(str(response_data)))
            
            span.add_event(f"External call to {service_name} completed successfully", {
                "duration_ms": duration * 1000,
                "response_size": len(str(response_data))
            })
            
            return response_data
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Record failed call metrics
            self.dependency_calls_counter.add(1, {
                "service": service_name,
                "status": "error",
                "method": "GET"
            })
            
            self.dependency_errors_counter.add(1, {
                "service": service_name,
                "error_type": type(e).__name__
            })
            
            self.dependency_duration.record(duration, {
                "service": service_name,
                "status": "error"
            })
            
            # Set error attributes
            span.set_attribute("dependency.success", False)
            span.set_attribute("dependency.duration_ms", duration * 1000)
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            
            span.add_event(f"External call to {service_name} failed", {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "duration_ms": duration * 1000
            })
            
            # Return empty data on failure for demo purposes
            return {}
    
    async def _simulate_api_call(
        self,
        service_name: str,
        url: str,
        params: Dict[str, Any],
        span: trace.Span
    ) -> Dict[str, Any]:
        """Simulate external API calls with realistic delays and occasional failures"""
        
        # Simulate network delay
        delay = random.uniform(0.1, 0.8)
        await asyncio.sleep(delay)
        
        # Simulate occasional failures
        failure_rate = 0.15 if service_name == "stock_api" else 0.1
        if random.random() < failure_rate:
            error_types = [
                "Connection timeout",
                "Service unavailable",
                "Rate limit exceeded",
                "Invalid API key"
            ]
            raise Exception(f"{service_name}: {random.choice(error_types)}")
        
        # Return simulated response data
        if "weather" in service_name:
            return {
                "condition": random.choice(["sunny", "cloudy", "rainy", "snowy"]),
                "temperature": random.randint(-10, 35),
                "humidity": random.randint(30, 90),
                "location": "London"
            }
        elif "news" in service_name:
            headlines = [
                "Tech stocks surge amid AI breakthrough",
                "Climate summit reaches historic agreement",
                "New medical discovery shows promise",
                "Economic indicators point to growth"
            ]
            return {
                "headline": random.choice(headlines),
                "source": "Demo News",
                "published_at": time.time()
            }
        elif "stock" in service_name:
            base_price = 150.0
            change = random.uniform(-10, 10)
            return {
                "price": round(base_price + change, 2),
                "change": round(change, 2),
                "symbol": "AAPL",
                "timestamp": time.time()
            }
        else:
            return {"status": "success", "data": f"Response from {service_name}"}