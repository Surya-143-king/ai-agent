"""
Information Enrichment Agent
Searches and enriches provider information from multiple public sources
"""
import requests
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from config import Config
from utils.helpers import fetch_webpage, sanitize_text


class InformationEnrichmentAgent:
    def __init__(self):
        self.name = "InformationEnrichmentAgent"
    
    def enrich_provider_data(self, provider: Dict) -> Dict:
        """
        Main enrichment method - adds additional provider information
        """
        print(f"[{self.name}] Enriching data for provider: {provider.get('name')}")
        
        enrichment_results = {
            'additional_specialties': [],
            'board_certifications': [],
            'education': [],
            'hospital_affiliations': [],
            'languages': [],
            'office_hours': None,
            'accepting_new_patients': None,
            'data_sources': [],
            'confidence_score': 0.0
        }
        
        # Enrich from various sources
        npi = provider.get('npi')
        if npi:
            # Search professional databases
            professional_data = self.search_professional_databases(npi)
            if professional_data:
                enrichment_results.update(professional_data)
                enrichment_results['data_sources'].append('professional_database')
        
        # Search provider website
        website = provider.get('website')
        if website:
            website_data = self.extract_from_website(website)
            if website_data:
                self._merge_enrichment_data(enrichment_results, website_data)
                enrichment_results['data_sources'].append('provider_website')
        
        # Calculate confidence score
        enrichment_results['confidence_score'] = self._calculate_enrichment_confidence(enrichment_results)
        
        return enrichment_results
    
    def search_professional_databases(self, npi: str) -> Optional[Dict]:
        """
        Search professional databases for additional provider information
        """
        # Simulated search - in real implementation, would query actual databases
        return {
            'board_certifications': [
                {'board': 'American Board of Internal Medicine', 'year': 2015}
            ],
            'education': [
                {'institution': 'Johns Hopkins University', 'degree': 'MD', 'year': 2010}
            ]
        }
    
    def extract_from_website(self, website: str) -> Optional[Dict]:
        """
        Extract provider information from practice website
        """
        soup = fetch_webpage(website)
        if not soup:
            return None
        
        result = {}
        page_text = soup.get_text()
        
        # Extract specialties
        specialty_keywords = ['cardiology', 'dermatology', 'orthopedics', 'pediatrics', 
                            'internal medicine', 'family medicine', 'surgery']
        found_specialties = [s for s in specialty_keywords if s.lower() in page_text.lower()]
        if found_specialties:
            result['additional_specialties'] = found_specialties
        
        # Extract languages
        language_keywords = ['spanish', 'mandarin', 'french', 'german', 'hindi']
        found_languages = [l for l in language_keywords if l.lower() in page_text.lower()]
        if found_languages:
            result['languages'] = found_languages
        
        # Check for new patient acceptance
        if 'accepting new patients' in page_text.lower():
            result['accepting_new_patients'] = True
        elif 'not accepting' in page_text.lower():
            result['accepting_new_patients'] = False
        
        return result
    
    def search_hospital_affiliations(self, provider_name: str, city: str) -> List[str]:
        """
        Search for hospital affiliations
        """
        # Simulated search - would use actual hospital databases
        return ['General Hospital', 'Medical Center']
    
    def extract_education_history(self, npi: str) -> List[Dict]:
        """
        Extract provider education history
        """
        # Simulated - would query medical school databases
        return [
            {
                'institution': 'Medical University',
                'degree': 'MD',
                'year': 2010,
                'residency': 'Internal Medicine'
            }
        ]
    
    def find_additional_locations(self, provider: Dict) -> List[Dict]:
        """
        Find additional practice locations
        """
        # Simulated - would search multiple sources
        return []
    
    def _merge_enrichment_data(self, target: Dict, source: Dict):
        """
        Merge enrichment data from multiple sources
        """
        for key, value in source.items():
            if isinstance(value, list):
                if key in target:
                    target[key].extend(value)
                else:
                    target[key] = value
            else:
                if key not in target or target[key] is None:
                    target[key] = value
    
    def _calculate_enrichment_confidence(self, enrichment_data: Dict) -> float:
        """
        Calculate confidence score for enriched data
        """
        data_points = 0
        filled_points = 0
        
        for key, value in enrichment_data.items():
            if key not in ['data_sources', 'confidence_score']:
                data_points += 1
                if value and (not isinstance(value, list) or len(value) > 0):
                    filled_points += 1
        
        return filled_points / data_points if data_points > 0 else 0.0
