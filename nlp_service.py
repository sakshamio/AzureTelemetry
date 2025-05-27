"""
NLP Service for intent recognition and entity extraction with telemetry
"""

import asyncio
import random
import re
from typing import Dict, List, Any
from opentelemetry import trace, metrics
from utils.correlation_context import CorrelationContext

class NLPService:
    """Natural Language Processing service with comprehensive telemetry"""
    
    def __init__(self):
        self.tracer = trace.get_tracer(__name__)
        self.meter = metrics.get_meter(__name__)
        
        # Intent patterns for simple rule-based classification
        self.intent_patterns = {
            "greeting": [r"\b(hi|hello|hey|good morning|good afternoon)\b", r"\bgreetings\b"],
            "goodbye": [r"\b(bye|goodbye|see you|farewell)\b", r"\bsee you later\b"],
            "weather": [r"\bweather\b", r"\btemperature\b", r"\b(rain|snow|sunny|cloudy)\b"],
            "news": [r"\bnews\b", r"\bheadlines\b", r"\bcurrent events\b"],
            "stock_price": [r"\bstock\b", r"\bshare price\b", r"\bmarket\b", r"\baapl\b"],
            "help": [r"\bhelp\b", r"\bassist\b", r"\bsupport\b"],
            "general": []  # fallback
        }
        
        # Create metrics
        self.intent_analysis_counter = self.meter.create_counter(
            name="nlp_intent_analysis_total",
            description="Total number of intent analysis operations",
            unit="1"
        )
        
        self.intent_analysis_duration = self.meter.create_histogram(
            name="nlp_intent_analysis_duration_seconds",
            description="Duration of intent analysis operations",
            unit="s"
        )
        
        self.confidence_score_histogram = self.meter.create_histogram(
            name="nlp_confidence_scores",
            description="Distribution of NLP confidence scores",
            unit="1"
        )
    
    async def analyze_intent(self, message: str, correlation_ctx: CorrelationContext) -> Dict[str, Any]:
        """Analyze message intent and extract entities"""
        with self.tracer.start_as_current_span("analyze_intent") as span:
            import time
            start_time = time.time()
            
            span.set_attribute("request_id", correlation_ctx.request_id)
            span.set_attribute("message_length", len(message))
            span.set_attribute("service", "nlp")
            
            span.add_event("Starting intent analysis", {
                "message_preview": message[:100] + "..." if len(message) > 100 else message
            })
            
            try:
                # Step 1: Preprocess message
                preprocessed = await self._preprocess_message(message, span, correlation_ctx)
                
                # Step 2: Classify intent
                intent_result = await self._classify_intent(preprocessed, span, correlation_ctx)
                
                # Step 3: Extract entities
                entities = await self._extract_entities(preprocessed, span, correlation_ctx)
                
                # Step 4: Calculate confidence
                confidence = await self._calculate_confidence(intent_result, entities, span, correlation_ctx)
                
                # Prepare final result
                analysis_result = {
                    "intent": intent_result["intent"],
                    "confidence": confidence,
                    "confidence_level": self._get_confidence_level(confidence),
                    "entities": entities,
                    "preprocessed_message": preprocessed
                }
                
                # Record metrics
                duration = time.time() - start_time
                self.intent_analysis_duration.record(duration, {
                    "intent": intent_result["intent"],
                    "confidence_level": analysis_result["confidence_level"]
                })
                
                self.intent_analysis_counter.add(1, {
                    "intent": intent_result["intent"],
                    "success": "true"
                })
                
                self.confidence_score_histogram.record(confidence, {
                    "intent": intent_result["intent"]
                })
                
                # Set span attributes
                span.set_attribute("detected_intent", intent_result["intent"])
                span.set_attribute("confidence_score", confidence)
                span.set_attribute("entities_count", len(entities))
                span.set_attribute("processing_time_ms", duration * 1000)
                
                span.add_event("Intent analysis completed", {
                    "intent": intent_result["intent"],
                    "confidence": confidence,
                    "entities_found": len(entities),
                    "processing_time_ms": duration * 1000
                })
                
                return analysis_result
                
            except Exception as e:
                duration = time.time() - start_time
                
                self.intent_analysis_counter.add(1, {
                    "intent": "error",
                    "success": "false"
                })
                
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                span.add_event("Intent analysis failed", {
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                })
                raise
    
    async def _preprocess_message(self, message: str, parent_span, correlation_ctx: CorrelationContext) -> str:
        """Preprocess the input message"""
        with self.tracer.start_as_current_span("preprocess_message", parent=parent_span) as span:
            span.set_attribute("request_id", correlation_ctx.request_id)
            span.add_event("Starting message preprocessing")
            
            # Simulate preprocessing time
            await asyncio.sleep(random.uniform(0.001, 0.005))
            
            # Basic preprocessing: lowercase, strip whitespace
            preprocessed = message.lower().strip()
            
            # Remove extra whitespaces
            preprocessed = re.sub(r'\s+', ' ', preprocessed)
            
            span.set_attribute("original_length", len(message))
            span.set_attribute("preprocessed_length", len(preprocessed))
            span.add_event("Message preprocessing completed")
            
            return preprocessed
    
    async def _classify_intent(self, message: str, parent_span, correlation_ctx: CorrelationContext) -> Dict[str, Any]:
        """Classify the intent of the message"""
        with self.tracer.start_as_current_span("classify_intent", parent=parent_span) as span:
            span.set_attribute("request_id", correlation_ctx.request_id)
            span.add_event("Starting intent classification")
            
            # Simulate ML model inference time
            await asyncio.sleep(random.uniform(0.05, 0.15))
            
            # Simple rule-based classification
            detected_intent = "general"
            pattern_matches = []
            
            for intent, patterns in self.intent_patterns.items():
                if intent == "general":
                    continue
                    
                for pattern in patterns:
                    if re.search(pattern, message, re.IGNORECASE):
                        detected_intent = intent
                        pattern_matches.append(pattern)
                        break
                
                if detected_intent != "general":
                    break
            
            result = {
                "intent": detected_intent,
                "matched_patterns": pattern_matches
            }
            
            span.set_attribute("detected_intent", detected_intent)
            span.set_attribute("patterns_matched", len(pattern_matches))
            span.add_event("Intent classification completed", {
                "intent": detected_intent,
                "patterns_matched": len(pattern_matches)
            })
            
            return result
    
    async def _extract_entities(self, message: str, parent_span, correlation_ctx: CorrelationContext) -> List[Dict[str, Any]]:
        """Extract entities from the message"""
        with self.tracer.start_as_current_span("extract_entities", parent=parent_span) as span:
            span.set_attribute("request_id", correlation_ctx.request_id)
            span.add_event("Starting entity extraction")
            
            # Simulate entity extraction processing time
            await asyncio.sleep(random.uniform(0.02, 0.08))
            
            entities = []
            
            # Simple entity extraction patterns
            entity_patterns = {
                "location": r'\b(london|new york|paris|tokyo|sydney)\b',
                "stock_symbol": r'\b([A-Z]{3,4})\b',
                "number": r'\b(\d+\.?\d*)\b',
                "date": r'\b(today|tomorrow|yesterday)\b'
            }
            
            for entity_type, pattern in entity_patterns.items():
                matches = re.finditer(pattern, message, re.IGNORECASE)
                for match in matches:
                    entities.append({
                        "type": entity_type,
                        "value": match.group(1),
                        "start": match.start(),
                        "end": match.end(),
                        "confidence": random.uniform(0.7, 1.0)
                    })
            
            span.set_attribute("entities_found", len(entities))
            span.add_event("Entity extraction completed", {
                "entities_count": len(entities),
                "entity_types": list(set(e["type"] for e in entities))
            })
            
            return entities
    
    async def _calculate_confidence(
        self, 
        intent_result: Dict[str, Any], 
        entities: List[Dict[str, Any]], 
        parent_span,
        correlation_ctx: CorrelationContext
    ) -> float:
        """Calculate overall confidence score"""
        with self.tracer.start_as_current_span("calculate_confidence", parent=parent_span) as span:
            span.set_attribute("request_id", correlation_ctx.request_id)
            span.add_event("Calculating confidence score")
            
            # Simple confidence calculation
            base_confidence = 0.5
            
            # Boost confidence if patterns matched
            if intent_result.get("matched_patterns"):
                base_confidence += 0.3
            
            # Boost confidence based on entities found
            if entities:
                entity_boost = min(0.2, len(entities) * 0.05)
                base_confidence += entity_boost
            
            # Add some randomness to simulate ML model uncertainty
            final_confidence = min(1.0, base_confidence + random.uniform(-0.1, 0.1))
            
            span.set_attribute("calculated_confidence", final_confidence)
            span.add_event("Confidence calculation completed", {
                "confidence_score": final_confidence
            })
            
            return round(final_confidence, 3)
    
    def _get_confidence_level(self, confidence: float) -> str:
        """Convert confidence score to level"""
        if confidence >= 0.8:
            return "high"
        elif confidence >= 0.6:
            return "medium"
        else:
            return "low"