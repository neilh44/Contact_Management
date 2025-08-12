import openai
from typing import Dict, Any, List
import json
import re

class GPTVisionExtractor:
    """Extracts contact information from visiting cards using GPT Vision"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        openai.api_key = api_key
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
    
    def create_extraction_prompt(self) -> str:
        """Create prompt for contact information extraction with business intelligence"""
        return """
        Extract all contact information from this visiting card image and provide comprehensive business intelligence.
        Return the information in JSON format with these fields:
        
        {
            "name": "Full name of the person",
            "company": "Company/Organization name",
            "position": "Job title/position",
            "email": "Email address",
            "phone": "Phone number(s)",
            "address": "Physical address",
            "website": "Website URL",
            "social_media": "Social media handles",
            "business_category": "Primary business category (Healthcare, Real Estate, Manufacturing, Engineering, Technology, Finance, Education, Hospitality, Retail, Construction, Legal, Consulting, etc.)",
            "business_subcategory": "Specific subcategory (e.g., 'Pediatric Hospital', 'Residential Real Estate', 'Glass Manufacturing', 'Software Development', etc.)",
            "industry_keywords": ["List of 5-10 relevant industry keywords that describe this business"],
            "services_offered": "Brief description of main services or products offered",
            "target_market": "Who are their likely customers/clients",
            "business_type": "Type of business (B2B, B2C, B2G, etc.)",
            "company_size": "Estimated company size (Startup, Small, Medium, Large, Enterprise)",
            "geographic_scope": "Geographic reach (Local, Regional, National, International)",
            "specializations": ["List of specific specializations or expertise areas"],
            "additional_info": "Any other relevant information"
        }
        
        IMPORTANT: 
        - Be very specific with business_category - use standard industry classifications
        - Industry_keywords should be comprehensive and include synonyms, related terms, and industry jargon
        - Analyze the company name, position, and any visible text to infer business intelligence
        - If any field is not found or cannot be inferred, use null
        - Be precise and insightful in your business analysis
        """
    
    def _create_business_intelligence_text(self, contact_data: Dict[str, Any]) -> str:
        """Create rich text for semantic search with business intelligence"""
        search_elements = []
        
        # Basic contact info
        for field in ['name', 'company', 'position', 'email', 'address']:
            value = contact_data.get(field)
            if value and str(value).strip() and value != 'null':
                search_elements.append(f"{field}: {value}")
        
        # Business intelligence fields
        business_fields = {
            'business_category': 'Primary Business',
            'business_subcategory': 'Business Type', 
            'services_offered': 'Services',
            'target_market': 'Target Market',
            'business_type': 'Business Model',
            'company_size': 'Company Size',
            'geographic_scope': 'Geographic Reach'
        }
        
        for field, label in business_fields.items():
            value = contact_data.get(field)
            if value and str(value).strip() and value != 'null':
                search_elements.append(f"{label}: {value}")
        
        # Industry keywords
        keywords = contact_data.get('industry_keywords', [])
        if keywords and isinstance(keywords, list):
            search_elements.append(f"Industry Keywords: {', '.join(keywords)}")
        
        # Specializations
        specializations = contact_data.get('specializations', [])
        if specializations and isinstance(specializations, list):
            search_elements.append(f"Specializations: {', '.join(specializations)}")
        
        return " | ".join(search_elements)
    
    def extract_contact_info(self, base64_image: str) -> Dict[str, Any]:
        """Extract contact information with business intelligence from base64 encoded image"""
        try:
            print("🔗 Making request to OpenAI GPT Vision API with business intelligence...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": self.create_extraction_prompt()
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1500  # Increased for business intelligence
            )
            
            content = response.choices[0].message.content
            print(f"📝 Raw GPT response: {content[:300]}...")
            
            # Parse JSON response
            try:
                # First, try to parse the content directly
                contact_info = json.loads(content)
                print("✅ Successfully parsed JSON directly from GPT response")
                
            except json.JSONDecodeError:
                try:
                    # Try to find JSON in markdown code blocks
                    import re
                    # Look for ```json ... ``` blocks
                    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                        contact_info = json.loads(json_str)
                        print("✅ Successfully parsed JSON from markdown code block")
                    else:
                        # Try to find any JSON object
                        json_match = re.search(r'\{.*\}', content, re.DOTALL)
                        if json_match:
                            json_str = json_match.group()
                            contact_info = json.loads(json_str)
                            print("✅ Successfully parsed JSON from text")
                        else:
                            raise json.JSONDecodeError("No JSON found", content, 0)
                            
                except json.JSONDecodeError as je:
                    print(f"❌ JSON parsing failed: {str(je)}")
                    # Try to extract key information manually
                    contact_info = self._parse_text_response(content)
                    print("⚠️ Used fallback text parsing")
            
            # Validate and enhance business intelligence
            contact_info = self._enhance_business_intelligence(contact_info)
            
            # Create rich searchable text for vector database
            searchable_text = self._create_business_intelligence_text(contact_info)
            
            return {
                'success': True,
                'data': contact_info,
                'searchable_text': searchable_text,
                'tokens_used': response.usage.total_tokens,
                'raw_response': content
            }
                
        except Exception as e:
            print(f"💥 OpenAI API error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def _enhance_business_intelligence(self, contact_info: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance and validate business intelligence data"""
        
        # Ensure industry_keywords is a list
        if not isinstance(contact_info.get('industry_keywords'), list):
            keywords_str = str(contact_info.get('industry_keywords', ''))
            if keywords_str and keywords_str != 'null':
                # Try to parse as comma-separated values
                contact_info['industry_keywords'] = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
            else:
                contact_info['industry_keywords'] = []
        
        # Ensure specializations is a list
        if not isinstance(contact_info.get('specializations'), list):
            spec_str = str(contact_info.get('specializations', ''))
            if spec_str and spec_str != 'null':
                contact_info['specializations'] = [sp.strip() for sp in spec_str.split(',') if sp.strip()]
            else:
                contact_info['specializations'] = []
        
        # Auto-generate industry keywords if missing
        if not contact_info.get('industry_keywords'):
            contact_info['industry_keywords'] = self._generate_industry_keywords(contact_info)
        
        # Set default business category if missing
        if not contact_info.get('business_category') or contact_info.get('business_category') == 'null':
            contact_info['business_category'] = self._infer_business_category(contact_info)
        
        print(f"🏢 Business Intelligence:")
        print(f"   📂 Category: {contact_info.get('business_category', 'Unknown')}")
        print(f"   🏷️ Keywords: {contact_info.get('industry_keywords', [])[:3]}...")
        print(f"   🎯 Services: {str(contact_info.get('services_offered', 'N/A'))[:50]}...")
        
        return contact_info
    
    def _generate_industry_keywords(self, contact_info: Dict[str, Any]) -> List[str]:
        """Generate industry keywords based on company and position info"""
        keywords = []
        
        company = str(contact_info.get('company', '')).lower()
        position = str(contact_info.get('position', '')).lower()
        category = str(contact_info.get('business_category', '')).lower()
        
        # Healthcare keywords
        if any(word in company + position + category for word in ['hospital', 'clinic', 'medical', 'doctor', 'health']):
            keywords.extend(['healthcare', 'medical', 'hospital', 'clinic', 'doctor', 'physician', 'treatment', 'patient care'])
        
        # Real estate keywords
        if any(word in company + position + category for word in ['real estate', 'property', 'realty', 'homes', 'land']):
            keywords.extend(['real estate', 'property', 'realty', 'housing', 'commercial property', 'residential', 'investment', 'broker'])
        
        # Manufacturing keywords
        if any(word in company + position + category for word in ['glass', 'manufacturing', 'fabricat', 'industrial']):
            keywords.extend(['manufacturing', 'industrial', 'production', 'fabrication', 'materials', 'supply chain'])
        
        # Engineering keywords
        if any(word in company + position + category for word in ['engineer', 'technical', 'construction']):
            keywords.extend(['engineering', 'technical', 'construction', 'infrastructure', 'design', 'project management'])
        
        return list(set(keywords))  # Remove duplicates
    
    def _infer_business_category(self, contact_info: Dict[str, Any]) -> str:
        """Infer business category from available information"""
        company = str(contact_info.get('company', '')).lower()
        position = str(contact_info.get('position', '')).lower()
        
        if any(word in company + position for word in ['hospital', 'clinic', 'medical', 'doctor', 'health']):
            return 'Healthcare'
        elif any(word in company + position for word in ['real estate', 'property', 'realty', 'homes']):
            return 'Real Estate'
        elif any(word in company + position for word in ['glass', 'manufacturing', 'fabricat']):
            return 'Manufacturing'
        elif any(word in company + position for word in ['engineer', 'technical', 'construction']):
            return 'Engineering'
        elif any(word in company + position for word in ['software', 'tech', 'digital', 'IT']):
            return 'Technology'
        else:
            return 'Business Services'
    
    def _parse_text_response(self, content: str) -> Dict[str, Any]:
        """Manually parse contact information from text response"""
        contact_info = {
            "name": None,
            "company": None,
            "position": None,
            "email": None,
            "phone": None,
            "address": None,
            "website": None,
            "social_media": None,
            "additional_info": None
        }
        
        # Simple text parsing - look for common patterns
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Look for email pattern
            if '@' in line and not contact_info['email']:
                import re
                email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', line)
                if email_match:
                    contact_info['email'] = email_match.group()
            
            # Look for phone pattern
            if any(char.isdigit() for char in line) and len([c for c in line if c.isdigit()]) >= 7:
                if not contact_info['phone']:
                    contact_info['phone'] = line
            
            # Look for website pattern
            if 'www.' in line.lower() or 'http' in line.lower():
                if not contact_info['website']:
                    contact_info['website'] = line
        
        # If we couldn't extract much, put the full content as additional_info
        if not any(contact_info.values()):
            contact_info['additional_info'] = content[:500]  # Truncate long content
            
        return contact_info