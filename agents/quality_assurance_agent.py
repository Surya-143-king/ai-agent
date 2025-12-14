"""
Quality Assurance Agent
Compares data across sources and identifies discrepancies
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from config import Config
from utils.helpers import compare_strings, calculate_confidence_score


class QualityAssuranceAgent:
    def __init__(self):
        self.name = "QualityAssuranceAgent"
        self.min_confidence = Config.MIN_CONFIDENCE_SCORE
        self.high_priority_threshold = Config.HIGH_PRIORITY_THRESHOLD
    
    def assess_data_quality(self, provider: Dict, validation_results: Dict, 
                           enrichment_results: Dict) -> Dict:
        """
        Main quality assessment method
        """
        print(f"[{self.name}] Assessing quality for provider: {provider.get('name')}")
        
        assessment = {
            'overall_score': 0.0,
            'data_completeness': 0.0,
            'data_accuracy': 0.0,
            'cross_validation_score': 0.0,
            'priority_level': 'low',
            'requires_manual_review': False,
            'discrepancies': [],
            'missing_fields': [],
            'quality_issues': [],
            'recommendations': []
        }
        
        # Assess data completeness
        assessment['data_completeness'] = self._assess_completeness(provider)
        
        # Assess data accuracy based on validation
        assessment['data_accuracy'] = validation_results.get('confidence_score', 0.0)
        
        # Cross-validate data from multiple sources
        assessment['cross_validation_score'] = self._cross_validate_data(
            provider, validation_results, enrichment_results
        )
        
        # Identify discrepancies
        assessment['discrepancies'] = self._identify_discrepancies(
            provider, validation_results
        )
        
        # Check for missing critical fields
        assessment['missing_fields'] = self._check_missing_fields(provider)
        
        # Detect quality issues
        assessment['quality_issues'] = self._detect_quality_issues(
            provider, validation_results
        )
        
        # Calculate overall quality score
        assessment['overall_score'] = self._calculate_overall_score(assessment)
        
        # Determine priority level
        assessment['priority_level'] = self._determine_priority(assessment['overall_score'])
        
        # Check if manual review is needed
        assessment['requires_manual_review'] = self._requires_manual_review(assessment)
        
        # Generate recommendations
        assessment['recommendations'] = self._generate_recommendations(assessment)
        
        return assessment
    
    def _assess_completeness(self, provider: Dict) -> float:
        """
        Assess how complete the provider data is
        """
        required_fields = [
            'npi', 'name', 'first_name', 'last_name', 'specialty',
            'phone', 'email', 'address_line1', 'city', 'state', 'zip_code'
        ]
        
        filled = sum(1 for field in required_fields if provider.get(field))
        return filled / len(required_fields)
    
    def _cross_validate_data(self, provider: Dict, validation_results: Dict, 
                            enrichment_results: Dict) -> float:
        """
        Cross-validate data from multiple sources
        """
        scores = []
        
        # Check NPI validation
        if validation_results.get('npi_validated'):
            scores.append(1.0)
        
        # Check contact validation
        if validation_results.get('contact_validated'):
            scores.append(0.8)
        
        # Check address validation
        if validation_results.get('address_validated'):
            scores.append(0.7)
        
        # Check enrichment confidence
        enrichment_confidence = enrichment_results.get('confidence_score', 0)
        if enrichment_confidence > 0:
            scores.append(enrichment_confidence)
        
        return sum(scores) / len(scores) if scores else 0.0
    
    def _identify_discrepancies(self, provider: Dict, validation_results: Dict) -> List[Dict]:
        """
        Identify discrepancies between provider data and validation results
        """
        discrepancies = []
        
        findings = validation_results.get('findings', {})
        
        # Check NPI discrepancies
        npi_data = findings.get('npi', {})
        if npi_data and provider.get('name'):
            npi_name = npi_data.get('name', '')
            similarity = compare_strings(provider.get('name', ''), npi_name)
            if similarity < 0.8:
                discrepancies.append({
                    'field': 'name',
                    'current_value': provider.get('name'),
                    'validated_value': npi_name,
                    'similarity': similarity,
                    'severity': 'high'
                })
        
        # Check contact information discrepancies
        contact_data = findings.get('contact', {})
        if contact_data:
            validated_phone = contact_data.get('phone')
            if validated_phone and provider.get('phone') != validated_phone:
                discrepancies.append({
                    'field': 'phone',
                    'current_value': provider.get('phone'),
                    'validated_value': validated_phone,
                    'severity': 'medium'
                })
        
        return discrepancies
    
    def _check_missing_fields(self, provider: Dict) -> List[str]:
        """
        Check for missing critical fields
        """
        critical_fields = {
            'npi': 'NPI Number',
            'name': 'Provider Name',
            'phone': 'Phone Number',
            'specialty': 'Specialty',
            'address_line1': 'Street Address',
            'city': 'City',
            'state': 'State'
        }
        
        missing = []
        for field, label in critical_fields.items():
            if not provider.get(field):
                missing.append(label)
        
        return missing
    
    def _detect_quality_issues(self, provider: Dict, validation_results: Dict) -> List[Dict]:
        """
        Detect potential data quality issues
        """
        issues = []
        
        # Check for low confidence score
        confidence = validation_results.get('confidence_score', 0)
        if confidence < self.min_confidence:
            issues.append({
                'type': 'low_confidence',
                'severity': 'high',
                'description': f'Validation confidence score ({confidence:.2f}) below threshold',
                'value': confidence
            })
        
        # Check for validation failures
        if not validation_results.get('npi_validated'):
            issues.append({
                'type': 'npi_validation_failed',
                'severity': 'critical',
                'description': 'NPI validation failed',
                'value': provider.get('npi')
            })
        
        # Check for suspicious patterns
        phone = provider.get('phone', '')
        if phone and (phone == '000-000-0000' or phone == '111-111-1111'):
            issues.append({
                'type': 'suspicious_phone',
                'severity': 'high',
                'description': 'Phone number appears to be placeholder',
                'value': phone
            })
        
        return issues
    
    def _calculate_overall_score(self, assessment: Dict) -> float:
        """
        Calculate overall quality score
        """
        weights = {
            'data_completeness': 0.3,
            'data_accuracy': 0.4,
            'cross_validation_score': 0.3
        }
        
        score = (
            assessment['data_completeness'] * weights['data_completeness'] +
            assessment['data_accuracy'] * weights['data_accuracy'] +
            assessment['cross_validation_score'] * weights['cross_validation_score']
        )
        
        # Penalize for quality issues
        critical_issues = sum(1 for i in assessment.get('quality_issues', []) 
                            if i.get('severity') == 'critical')
        score -= (critical_issues * 0.2)
        
        return max(0.0, min(1.0, score))
    
    def _determine_priority(self, overall_score: float) -> str:
        """
        Determine priority level based on overall score
        """
        if overall_score >= 0.8:
            return 'low'
        elif overall_score >= 0.5:
            return 'medium'
        else:
            return 'high'
    
    def _requires_manual_review(self, assessment: Dict) -> bool:
        """
        Determine if provider requires manual review
        """
        # Require manual review if:
        # - Overall score is below threshold
        # - Has critical quality issues
        # - Has high-severity discrepancies
        
        if assessment['overall_score'] < self.high_priority_threshold:
            return True
        
        critical_issues = [i for i in assessment['quality_issues'] 
                          if i.get('severity') == 'critical']
        if critical_issues:
            return True
        
        high_severity_discrepancies = [d for d in assessment['discrepancies'] 
                                      if d.get('severity') == 'high']
        if high_severity_discrepancies:
            return True
        
        return False
    
    def _generate_recommendations(self, assessment: Dict) -> List[str]:
        """
        Generate actionable recommendations
        """
        recommendations = []
        
        # Recommendations for missing fields
        if assessment['missing_fields']:
            recommendations.append(
                f"Complete missing fields: {', '.join(assessment['missing_fields'])}"
            )
        
        # Recommendations for discrepancies
        for discrepancy in assessment['discrepancies']:
            recommendations.append(
                f"Verify {discrepancy['field']}: Current value may be outdated"
            )
        
        # Recommendations for quality issues
        for issue in assessment['quality_issues']:
            if issue['type'] == 'low_confidence':
                recommendations.append("Re-validate provider information from primary sources")
            elif issue['type'] == 'npi_validation_failed':
                recommendations.append("Verify NPI number with provider")
        
        # Priority-based recommendations
        if assessment['priority_level'] == 'high':
            recommendations.insert(0, "⚠️ URGENT: Requires immediate manual review")
        
        return recommendations
