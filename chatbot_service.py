"""
Chatbot service with comprehensive telemetry and external dependencies
"""

import time
import asyncio
import random
from typing import Optional
from opentelemetry import trace, metrics
from services.external_service import ExternalAPIService
from services.nlp_service import NLPService
from utils.correlation_context import CorrelationContext
from models.request_models import ChatbotResponse

class ChatbotService:
    """Main chatbot service with telemetry integration"""
    
    def __init__(self):
        self.tracer = trace.get_tracer(__name__)
        self.meter = metrics.get_meter(__name__)
        self.external_service = ExternalAPIService()
        self.nlp_service = NLPService()
        
        # Create custom metrics
        self.message_processing_counter = self.meter.create_counter(
            name="chatbot_messages_processed_total",
            description="Total number of chatbot messages processed",
            unit="1"
        )
        
        self.processing_duration = self.meter.create_histogram(
            name="chatbot_processing_duration_seconds",
            description="Time taken to process chatbot messages",
            unit="s"
        )
        
        self.intent_recognition_counter = self.meter.create_counter(
            name="chatbot_intents_recognized_total",
            description="Total number of intents recognized",
            unit="1"
        )
    
    async def process_message(
        self, 
        message: str, 
        user_id: Optional[str],
        correlation_ctx: CorrelationContext
    ) -> ChatbotResponse:
        """Process a chatbot message with comprehensive telemetry"""
        
        with self.tracer.start_as_current_span("chatbot_process_message") as span:
            start_time = time.time()
            
            try:
                # Set span attributes
                span.set_attribute("request_id", correlation_ctx.request_id)
                span.set_attribute("user_id", user_id or "anonymous")
                span.set_attribute("message_length", len(message))
                span.set_attribute("service", "chatbot")
                
                span.add_event("Starting message processing", {
                    "message_preview": message[:50] + "..." if len(message) > 50 else message
                })
                
                # Step 1: Validate and preprocess message
                await self._validate_message(message, span, correlation_ctx)
                
                # Step 2: Analyze intent and entities
                analysis_result = await self._analyze_message(message, span, correlation_ctx)
                
                # Step 3: Fetch external data if needed
                external_data = await self._fetch_external_data(
                    analysis_result, span, correlation_ctx
                )
                
                # Step 4: Generate response
                response = await self._generate_response(
                    message, analysis_result, external_data, span, correlation_ctx
                )
                
                # Record metrics
                processing_time = time.time() - start_time
                self.processing_duration.record(processing_time, {
                    "intent": analysis_result.get("intent", "unknown"),
                    "user_type": "registered" if user_id else "anonymous"
                })
                
                self.message_processing_counter.add(1, {
                    "intent": analysis_result.get("intent", "unknown"),
                    "success": "true"
                })
                
                self.intent_recognition_counter.add(1, {
                    "intent": analysis_result.get("intent", "unknown"),
                    "confidence": analysis_result.get("confidence_level", "low")
                })
                
                span.set_attribute("processing_time_ms", processing_time * 1000)
                span.set_attribute("intent", analysis_result.get("intent", "unknown"))
                span.set_attribute("confidence", analysis_result.get("confidence", 0.0))
                span.add_event("Message processing completed successfully")
                
                return ChatbotResponse(
                    response=response,
                    intent=analysis_result.get("intent"),
                    confidence=analysis_result.get("confidence", 0.0),
                    request_id=correlation_ctx.request_id
                )
                
            except Exception as e:
                # Record failure metrics
                self.message_processing_counter.add(1, {
                    "intent": "unknown",
                    "success": "false"
                })
                
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                span.add_event("Message processing failed", {
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                })
                raise
    
    async def _validate_message(self, message: str, parent_span, correlation_ctx: CorrelationContext):
        """Validate incoming message"""
        with self.tracer.start_as_current_span("validate_message", parent=parent_span) as span:
            span.set_attribute("request_id", correlation_ctx.request_id)
            span.add_event("Validating message")
            
            if not message or len(message.strip()) == 0:
                error_msg = "Empty message provided"
                span.add_event("Validation failed", {"reason": error_msg})
                raise ValueError(error_msg)
            
            if len(message) > 5000:
                error_msg = "Message too long"
                span.add_event("Validation failed", {"reason": error_msg})
                raise ValueError(error_msg)
            
            # Simulate some processing time
            await asyncio.sleep(0.001)
            
            span.add_event("Message validation completed")
    
    async def _analyze_message(self, message: str, parent_span, correlation_ctx: CorrelationContext) -> dict:
        """Analyze message for intent and entities"""
        with self.tracer.start_as_current_span("analyze_message", parent=parent_span) as span:
            span.set_attribute("request_id", correlation_ctx.request_id)
            span.add_event("Starting message analysis")
            
            # Use NLP service for analysis
            analysis_result = await self.nlp_service.analyze_intent(message, correlation_ctx)
            
            span.set_attribute("detected_intent", analysis_result.get("intent", "unknown"))
            span.set_attribute("confidence_score", analysis_result.get("confidence", 0.0))
            span.set_attribute("entities_count", len(analysis_result.get("entities", [])))
            
            span.add_event("Message analysis completed", {
                "intent": analysis_result.get("intent"),
                "confidence": analysis_result.get("confidence"),
                "entities_found": len(analysis_result.get("entities", []))
            })
            
            return analysis_result
    
    async def _fetch_external_data(self, analysis_result: dict, parent_span, correlation_ctx: CorrelationContext) -> dict:
        """Fetch external data based on analysis"""
        with self.tracer.start_as_current_span("fetch_external_data", parent=parent_span) as span:
            span.set_attribute("request_id", correlation_ctx.request_id)
            span.set_attribute("intent", analysis_result.get("intent", "unknown"))
            
            intent = analysis_result.get("intent")
            external_data = {}
            
            if intent in ["weather", "news", "stock_price"]:
                span.add_event(f"Fetching external data for intent: {intent}")
                
                # Make external API calls based on intent
                if intent == "weather":
                    external_data = await self.external_service.get_weather_data(correlation_ctx)
                elif intent == "news":
                    external_data = await self.external_service.get_news_data(correlation_ctx)
                elif intent == "stock_price":
                    external_data = await self.external_service.get_stock_data(correlation_ctx)
                
                span.add_event("External data fetch completed", {
                    "data_size": len(str(external_data))
                })
            else:
                span.add_event("No external data needed for this intent")
            
            return external_data
    
    async def _generate_response(
        self, 
        message: str, 
        analysis_result: dict, 
        external_data: dict, 
        parent_span,
        correlation_ctx: CorrelationContext
    ) -> str:
        """Generate chatbot response"""
        with self.tracer.start_as_current_span("generate_response", parent=parent_span) as span:
            span.set_attribute("request_id", correlation_ctx.request_id)
            span.set_attribute("intent", analysis_result.get("intent", "unknown"))
            span.set_attribute("has_external_data", len(external_data) > 0)
            
            span.add_event("Starting response generation")
            
            # Simulate response generation logic
            intent = analysis_result.get("intent", "general")
            confidence = analysis_result.get("confidence", 0.0)
            
            # Simulate some processing time
            processing_time = random.uniform(0.1, 0.5)
            await asyncio.sleep(processing_time)
            
            # Generate response based on intent and external data
            if intent == "weather" and external_data:
                response = f"The weather is {external_data.get('condition', 'unknown')} with temperature {external_data.get('temperature', 'N/A')}°C"
            elif intent == "news" and external_data:
                response = f"Here's the latest news: {external_data.get('headline', 'No news available')}"
            elif intent == "stock_price" and external_data:
                response = f"The stock price is ${external_data.get('price', 'N/A')}"
            elif intent == "greeting":
                response = "Hello! How can I help you today?"
            elif intent == "goodbye":
                response = "Goodbye! Have a great day!"
            else:
                response = "I understand you're asking about something, but I need more information to help you properly."
            
            span.set_attribute("response_length", len(response))
            span.set_attribute("generation_time_ms", processing_time * 1000)
            
            span.add_event("Response generation completed", {
                "response_length": len(response),
                "processing_time_ms": processing_time * 1000
            })
            
            return response