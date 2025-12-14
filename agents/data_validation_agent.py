"""
Data Validation Agent
Performs automated web scraping and validation of provider contact information
"""
import requests
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import phonenumbers
from config import Config
from utils.helpers import (
    validate_npi, format_phone_number, fetch_webpage,
    extract_email_from_text, extract_phone_from_text, calculate_confidence_score
)


class DataValidationAgent:
    def __init__(self):
        self.name = "DataValidationAgent"
        self.confidence_threshold = Config.MIN_CONFIDENCE_SCORE
    
    def validate_provider(self, provider: Dict) -> Dict:
        """
        Main validation method - orchestrates all validation steps
        """
        print(f"[{self.name}] Validating provider: {provider.get('name')}")
        
        validation_results = {
            'npi_validated': False,
            'contact_validated': False,
            'address_validated': False,
            'confidence_score': 0.0,
            'data_sources': [],
            'findings': {},
            'errors': []
        }
        
        # Step 1: Validate NPI
        npi_result = self.validate_npi_registry(provider.get('npi'))
        if npi_result:
            validation_results['npi_validated'] = True
            validation_results['data_sources'].append('npi_registry')
            validation_results['findings']['npi'] = npi_result
        
        # Step 2: Validate contact information
        contact_result = self.validate_contact_info(provider)
        if contact_result:
            validation_results['contact_validated'] = contact_result.get('validated', False)
            validation_results['findings']['contact'] = contact_result
        
        # Step 3: Validate address
        address_result = self.validate_address(provider)
        if address_result:
            validation_results['address_validated'] = address_result.get('validated', False)
            validation_results['findings']['address'] = address_result
        
        # Calculate overall confidence score
        data_points = []
        if npi_result:
            data_points.append({'source': 'npi_registry', 'confidence': 1.0})
        if contact_result:
            data_points.append({'source': contact_result.get('source', 'web_scraping'), 
                              'confidence': contact_result.get('confidence', 0.5)})
        if address_result:
            data_points.append({'source': 'google_maps', 
                              'confidence': address_result.get('confidence', 0.6)})
        
        validation_results['confidence_score'] = calculate_confidence_score(data_points)
        
        return validation_results
    
    def validate_npi_registry(self, npi: str) -> Optional[Dict]:
        """
        Validate provider against NPI Registry
        """
        if not validate_npi(npi):
            return None
        
        try:
            url = f"{Config.NPI_REGISTRY_URL}?number={npi}&version=2.1"
            response = requests.get(url, timeout=Config.API_REQUEST_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                
                if results:
                    result = results[0]
                    return {
                        'validated': True,
                        'npi': result.get('number'),
                        'name': result.get('basic', {}).get('name'),
                        'credential': result.get('basic', {}).get('credential'),
                        'taxonomy': result.get('taxonomies', [{}])[0].get('desc') if result.get('taxonomies') else None,
                        'source': 'npi_registry',
                        'confidence': 1.0
                    }
        except Exception as e:
            print(f"Error validating NPI {npi}: {str(e)}")
        
        return None
    
    def validate_contact_info(self, provider: Dict) -> Optional[Dict]:
        """
        Validate provider contact information through web scraping
        """
        result = {
            'validated': False,
            'phone': None,
            'email': None,
            'website': None,
            'source': 'web_scraping',
            'confidence': 0.0
        }
        
        # Try to find provider website
        website = provider.get('website')
        if website:
            soup = fetch_webpage(website)
            if soup:
                # Extract contact information
                page_text = soup.get_text()
                
                phone = extract_phone_from_text(page_text)
                email = extract_email_from_text(page_text)
                
                if phone or email:
                    result['validated'] = True
                    result['phone'] = phone
                    result['email'] = email
                    result['website'] = website
                    result['confidence'] = 0.7
        
        # Fallback: Try Google search (simulated)
        if not result['validated']:
            result['confidence'] = 0.3
            result['source'] = 'simulated_search'
        
        return result
    
    def validate_address(self, provider: Dict) -> Optional[Dict]:
        """
        Validate provider address
        """
        address = provider.get('address', {})
        
        result = {
            'validated': False,
            'normalized_address': None,
            'latitude': None,
            'longitude': None,
            'confidence': 0.0
        }
        
        # Simple validation - check if address components exist
        if address.get('line1') and address.get('city') and address.get('state'):
            result['validated'] = True
            result['normalized_address'] = address
            result['confidence'] = 0.6
        
        return result
    
    def cross_validate(self, provider_data: Dict, external_data: Dict) -> float:
        """
        Cross-validate provider data against external sources
        """
        matches = 0
        total = 0
        
        fields_to_check = ['phone', 'email', 'address', 'specialty']
        
        for field in fields_to_check:
            if field in provider_data and field in external_data:
                total += 1
                if provider_data[field] == external_data[field]:
                    matches += 1
        
        return matches / total if total > 0 else 0.0
