"""
Directory Management Agent
Generates reports, manages workflows, and creates communication
"""
from typing import Dict, List
from datetime import datetime
import json


class DirectoryManagementAgent:
    def __init__(self):
        self.name = "DirectoryManagementAgent"
    
    def generate_validation_report(self, providers: List[Dict]) -> Dict:
        """
        Generate comprehensive validation report
        """
        print(f"[{self.name}] Generating validation report for {len(providers)} providers")
        
        report = {
            'summary': self._generate_summary(providers),
            'statistics': self._calculate_statistics(providers),
            'high_priority_providers': self._identify_high_priority(providers),
            'validation_trends': self._analyze_trends(providers),
            'actionable_items': self._generate_action_items(providers),
            'generated_at': datetime.utcnow().isoformat()
        }
        
        return report
    
    def create_manual_review_queue(self, providers: List[Dict]) -> List[Dict]:
        """
        Create prioritized queue for manual review
        """
        review_queue = []
        
        for provider in providers:
            qa_assessment = provider.get('qa_assessment', {})
            
            if qa_assessment.get('requires_manual_review'):
                review_item = {
                    'provider_id': provider.get('id'),
                    'provider_name': provider.get('name'),
                    'npi': provider.get('npi'),
                    'priority': qa_assessment.get('priority_level', 'medium'),
                    'overall_score': qa_assessment.get('overall_score', 0),
                    'issues': qa_assessment.get('quality_issues', []),
                    'discrepancies': qa_assessment.get('discrepancies', []),
                    'recommendations': qa_assessment.get('recommendations', []),
                    'validation_confidence': provider.get('validation_results', {}).get('confidence_score', 0)
                }
                review_queue.append(review_item)
        
        # Sort by priority (high -> medium -> low) and then by confidence score (low -> high)
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        review_queue.sort(key=lambda x: (
            priority_order.get(x['priority'], 2),
            x['overall_score']
        ))
        
        return review_queue
    
    def generate_communication_email(self, provider: Dict, purpose: str = 'verification') -> str:
        """
        Generate email communication for provider
        """
        templates = {
            'verification': self._verification_email_template,
            'update_request': self._update_request_email_template,
            'welcome': self._welcome_email_template
        }
        
        template_func = templates.get(purpose, self._verification_email_template)
        return template_func(provider)
    
    def export_directory(self, providers: List[Dict], format: str = 'json') -> str:
        """
        Export provider directory in specified format
        """
        if format == 'json':
            return json.dumps(providers, indent=2, default=str)
        elif format == 'csv':
            return self._export_as_csv(providers)
        else:
            return json.dumps(providers, indent=2, default=str)
    
    def _generate_summary(self, providers: List[Dict]) -> Dict:
        """
        Generate summary statistics
        """
        total = len(providers)
        validated = sum(1 for p in providers 
                       if p.get('validation_results', {}).get('npi_validated'))
        needs_review = sum(1 for p in providers 
                          if p.get('qa_assessment', {}).get('requires_manual_review'))
        
        high_confidence = sum(1 for p in providers 
                             if p.get('validation_results', {}).get('confidence_score', 0) >= 0.8)
        
        return {
            'total_providers': total,
            'validated_providers': validated,
            'high_confidence_providers': high_confidence,
            'needs_manual_review': needs_review,
            'validation_rate': round((validated / total * 100), 2) if total > 0 else 0,
            'auto_validation_rate': round(((total - needs_review) / total * 100), 2) if total > 0 else 0
        }
    
    def _calculate_statistics(self, providers: List[Dict]) -> Dict:
        """
        Calculate detailed statistics
        """
        total = len(providers)
        if total == 0:
            return {}
        
        # Calculate average scores
        avg_confidence = sum(p.get('validation_results', {}).get('confidence_score', 0) 
                           for p in providers) / total
        avg_quality_score = sum(p.get('qa_assessment', {}).get('overall_score', 0) 
                              for p in providers) / total
        avg_completeness = sum(p.get('qa_assessment', {}).get('data_completeness', 0) 
                             for p in providers) / total
        
        # Count by priority
        priority_counts = {'high': 0, 'medium': 0, 'low': 0}
        for provider in providers:
            priority = provider.get('qa_assessment', {}).get('priority_level', 'low')
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        # Count validation status
        status_counts = {}
        for provider in providers:
            status = provider.get('validation_status', 'pending')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            'average_confidence_score': round(avg_confidence, 3),
            'average_quality_score': round(avg_quality_score, 3),
            'average_completeness': round(avg_completeness, 3),
            'priority_distribution': priority_counts,
            'status_distribution': status_counts
        }
    
    def _identify_high_priority(self, providers: List[Dict]) -> List[Dict]:
        """
        Identify high-priority providers
        """
        high_priority = []
        
        for provider in providers:
            qa_assessment = provider.get('qa_assessment', {})
            if qa_assessment.get('priority_level') == 'high':
                high_priority.append({
                    'npi': provider.get('npi'),
                    'name': provider.get('name'),
                    'issues': qa_assessment.get('quality_issues', []),
                    'score': qa_assessment.get('overall_score', 0),
                    'recommendations': qa_assessment.get('recommendations', [])
                })
        
        return high_priority[:20]  # Top 20 high-priority providers
    
    def _analyze_trends(self, providers: List[Dict]) -> Dict:
        """
        Analyze validation trends
        """
        # Common issues analysis
        all_issues = []
        for provider in providers:
            issues = provider.get('qa_assessment', {}).get('quality_issues', [])
            all_issues.extend([i['type'] for i in issues])
        
        issue_counts = {}
        for issue in all_issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        
        # Common missing fields
        all_missing = []
        for provider in providers:
            missing = provider.get('qa_assessment', {}).get('missing_fields', [])
            all_missing.extend(missing)
        
        missing_counts = {}
        for field in all_missing:
            missing_counts[field] = missing_counts.get(field, 0) + 1
        
        return {
            'common_issues': dict(sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:5]),
            'common_missing_fields': dict(sorted(missing_counts.items(), key=lambda x: x[1], reverse=True)[:5])
        }
    
    def _generate_action_items(self, providers: List[Dict]) -> List[Dict]:
        """
        Generate actionable items for staff
        """
        action_items = []
        
        # Critical items
        for provider in providers:
            qa_assessment = provider.get('qa_assessment', {})
            critical_issues = [i for i in qa_assessment.get('quality_issues', []) 
                             if i.get('severity') == 'critical']
            
            if critical_issues:
                action_items.append({
                    'priority': 'critical',
                    'provider_npi': provider.get('npi'),
                    'provider_name': provider.get('name'),
                    'action': 'Immediate verification required',
                    'details': [i['description'] for i in critical_issues]
                })
        
        return action_items[:50]  # Top 50 action items
    
    def _verification_email_template(self, provider: Dict) -> str:
        """
        Template for verification email
        """
        return f"""
Subject: Provider Directory Information Verification Request

Dear {provider.get('name', 'Provider')},

We are updating our provider directory to ensure our members have accurate information. 
Could you please verify the following details?

Provider Information:
- Name: {provider.get('name')}
- NPI: {provider.get('npi')}
- Specialty: {provider.get('specialty', 'Not specified')}
- Phone: {provider.get('phone', 'Not specified')}
- Email: {provider.get('email', 'Not specified')}
- Address: {provider.get('address_line1', '')}, {provider.get('city', '')}, {provider.get('state', '')} {provider.get('zip_code', '')}

Please reply to this email with any corrections or confirm if all information is accurate.

Thank you for your cooperation.

Best regards,
Provider Network Services
"""
    
    def _update_request_email_template(self, provider: Dict) -> str:
        """
        Template for update request email
        """
        issues = provider.get('qa_assessment', {}).get('quality_issues', [])
        issue_list = '\n'.join([f"- {i.get('description', '')}" for i in issues[:3]])
        
        return f"""
Subject: Action Required: Provider Directory Update

Dear {provider.get('name', 'Provider')},

Our quality assurance process has identified potential issues with your directory listing:

{issue_list}

Please review and update your information at your earliest convenience to ensure our members 
can reach you without difficulty.

To update your information, please reply to this email or contact our Provider Services team.

Thank you,
Provider Network Services
"""
    
    def _welcome_email_template(self, provider: Dict) -> str:
        """
        Template for welcome email to new providers
        """
        return f"""
Subject: Welcome to Our Provider Network

Dear Dr. {provider.get('last_name', provider.get('name', 'Provider'))},

Welcome to our provider network! We're pleased to have you join us.

Your profile has been successfully added to our directory:
- NPI: {provider.get('npi')}
- Specialty: {provider.get('specialty', 'Not specified')}
- Practice Location: {provider.get('city', '')}, {provider.get('state', '')}

Members will now be able to find and contact you through our directory.

If you need to update any information, please don't hesitate to contact us.

Best regards,
Provider Network Services
"""
    
    def _export_as_csv(self, providers: List[Dict]) -> str:
        """
        Export providers as CSV
        """
        import io
        import csv
        
        output = io.StringIO()
        fieldnames = ['npi', 'name', 'specialty', 'phone', 'email', 'city', 'state', 
                     'validation_status', 'confidence_score', 'priority']
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for provider in providers:
            writer.writerow({
                'npi': provider.get('npi', ''),
                'name': provider.get('name', ''),
                'specialty': provider.get('specialty', ''),
                'phone': provider.get('phone', ''),
                'email': provider.get('email', ''),
                'city': provider.get('city', ''),
                'state': provider.get('state', ''),
                'validation_status': provider.get('validation_status', ''),
                'confidence_score': provider.get('validation_results', {}).get('confidence_score', 0),
                'priority': provider.get('qa_assessment', {}).get('priority_level', '')
            })
        
        return output.getvalue()
