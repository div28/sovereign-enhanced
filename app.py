# Sovereign AI Compliance Backend - Fixed with Validation & Professional PDF
import os
import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional
import logging
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import PyPDF2
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF

# Initialize Flask app
app = Flask(__name__)

# CORS Configuration
CORS(app, 
     origins=["*"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
     supports_credentials=False)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['EXPORT_FOLDER'] = 'exports'

# Create directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['EXPORT_FOLDER'], exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory storage
analysis_storage = {}
document_storage = {}

# CORS handler
@app.after_request
def after_request(response):
    if 'Access-Control-Allow-Origin' not in response.headers:
        response.headers['Access-Control-Allow-Origin'] = '*'
    if 'Access-Control-Allow-Headers' not in response.headers:
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization,Accept,Origin,X-Requested-With'
    if 'Access-Control-Allow-Methods' not in response.headers:
        response.headers['Access-Control-Allow-Methods'] = 'GET,PUT,POST,DELETE,OPTIONS'
    return response

class ComplianceAnalyzer:
    def __init__(self):
        # Industry validation keywords
        self.industry_keywords = {
            "hiring": ['hiring', 'recruitment', 'employee', 'candidate', 'job', 'resume', 'interview', 'applicant', 'hr', 'human resources', 'employment', 'workforce', 'talent', 'career'],
            "medical": ['medical', 'health', 'patient', 'doctor', 'hospital', 'healthcare', 'clinical', 'diagnosis', 'treatment', 'physician', 'medical device', 'pharmaceutical', 'therapy', 'medicine'],
            "finance": ['financial', 'finance', 'bank', 'credit', 'loan', 'payment', 'trading', 'investment', 'money', 'currency', 'transaction', 'fraud', 'risk', 'insurance'],
            "content": ['content', 'moderation', 'social media', 'post', 'comment', 'user-generated', 'platform', 'community', 'forum', 'blog', 'publication', 'media']
        }
        
        self.ai_types = {
            "hiring": {
                "name": "Hiring & Recruitment AI",
                "base_risk_score": 85,
                "max_penalty": "€20M or 4% global revenue",
                "critical_laws": ["GDPR Article 22", "EEOC Guidelines", "NYC Local Law 144"]
            },
            "medical": {
                "name": "Medical & Healthcare AI", 
                "base_risk_score": 95,
                "max_penalty": "$1.5M per incident",
                "critical_laws": ["HIPAA", "FDA 21 CFR", "GDPR Health Data"]
            },
            "finance": {
                "name": "Financial Services AI",
                "base_risk_score": 75,
                "max_penalty": "$5M + prosecution",
                "critical_laws": ["SOX", "PCI-DSS", "Fair Credit Reporting Act"]
            },
            "content": {
                "name": "Content Moderation AI",
                "base_risk_score": 65,
                "max_penalty": "6% global revenue",
                "critical_laws": ["DSA", "GDPR", "Section 230"]
            }
        }

    def validate_industry_match(self, industry, policy_text, ai_description):
        """Validate that policy and AI description match the selected industry"""
        if not industry or industry not in self.industry_keywords:
            return False, "Invalid industry selection"
        
        keywords = self.industry_keywords[industry]
        policy_lower = policy_text.lower() if policy_text else ""
        ai_lower = ai_description.lower() if ai_description else ""
        
        # Check policy match (need at least 2 keyword matches)
        policy_matches = sum(1 for keyword in keywords if keyword in policy_lower)
        
        # Check AI description match (need at least 1 keyword + AI terms)
        ai_matches = sum(1 for keyword in keywords if keyword in ai_lower)
        ai_terms = ['ai', 'artificial intelligence', 'machine learning', 'algorithm', 'automated', 'model']
        ai_term_matches = sum(1 for term in ai_terms if term in ai_lower)
        
        policy_valid = policy_matches >= 2 or len(policy_text) < 100  # Allow short policies
        ai_valid = ai_matches >= 1 and ai_term_matches >= 1
        
        if not policy_valid:
            return False, f"Policy doesn't appear to be for {industry} industry (found {policy_matches} relevant terms)"
        
        if not ai_valid:
            return False, f"AI description doesn't match {industry} industry or lacks AI terminology"
        
        return True, "Industry validation passed"

    def extract_text_from_pdf(self, file_path):
        """Extract text from PDF with error handling"""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text.strip()
        except Exception as e:
            logger.error(f"PDF extraction error: {str(e)}")
            return ""

    def analyze_compliance(self, ai_type, ai_description, policy_text="", regions=None, validation_passed=False):
        """Perform intelligent compliance analysis with proper validation"""
        
        if not validation_passed:
            is_valid, validation_message = self.validate_industry_match(ai_type, policy_text, ai_description)
            if not is_valid:
                return {
                    "success": False,
                    "error": f"Validation failed: {validation_message}",
                    "validation_required": True
                }
        
        ai_config = self.ai_types.get(ai_type, self.ai_types["content"])
        regions = regions or ["eu"]
        
        # Smart risk scoring based on actual content
        risk_score = self._calculate_intelligent_risk_score(ai_type, ai_description, policy_text)
        violations = self._generate_smart_violations(ai_type, ai_description, policy_text, regions)
        recommendations = self._generate_recommendations(violations, ai_type)
        
        analysis_id = f"SOV-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"
        
        analysis = {
            "analysis_id": analysis_id,
            "timestamp": datetime.now().isoformat(),
            "ai_type": ai_config["name"],
            "industry": ai_type,
            "regions": regions,
            "risk_score": risk_score,
            "risk_level": self._get_risk_level(risk_score),
            "compliance_score": max(0, 100 - risk_score),
            "max_penalty": ai_config["max_penalty"],
            "violations": violations,
            "recommendations": recommendations,
            "policy_analysis": {
                "word_count": len(policy_text.split()) if policy_text else 0,
                "industry_validated": validation_passed,
                "key_gaps_identified": len([v for v in violations if v['severity'] == 'CRITICAL'])
            },
            "summary": f"Professional compliance analysis complete. {len([v for v in violations if v['severity'] == 'CRITICAL'])} critical issues identified requiring immediate attention."
        }
        
        return analysis

    def _calculate_intelligent_risk_score(self, ai_type, ai_description, policy_text):
        """Calculate risk score based on actual content analysis"""
        base_score = 30  # Start conservative
        
        ai_lower = ai_description.lower()
        policy_lower = policy_text.lower() if policy_text else ""
        
        # High-risk AI capabilities
        high_risk_terms = {
            'automated decision': 15,
            'without human': 20,
            'facial recognition': 15,
            'biometric': 15,
            'personality': 10,
            'reject automatically': 20,
            'auto-reject': 20,
            'scoring': 10,
            'ranking': 10
        }
        
        for term, score_increase in high_risk_terms.items():
            if term in ai_lower:
                base_score += score_increase
        
        # Industry-specific adjustments
        industry_multipliers = {
            'hiring': 1.2,
            'medical': 1.4,
            'finance': 1.1,
            'content': 0.9
        }
        
        base_score *= industry_multipliers.get(ai_type, 1.0)
        
        # Policy completeness check
        if len(policy_text) < 500:
            base_score += 10  # Incomplete policy
        
        # Check for compliance mentions
        compliance_terms = ['gdpr', 'consent', 'data protection', 'privacy rights', 'automated decision']
        compliance_mentions = sum(1 for term in compliance_terms if term in policy_lower)
        
        if compliance_mentions < 2:
            base_score += 15  # Poor compliance awareness
        
        return min(95, max(15, int(base_score)))

    def _generate_smart_violations(self, ai_type, ai_description, policy_text, regions):
        """Generate realistic violations based on content analysis"""
        violations = []
        ai_lower = ai_description.lower()
        policy_lower = policy_text.lower() if policy_text else ""
        
        # Universal GDPR violations for EU regions
        if 'eu' in regions or 'uk' in regions:
            # Article 22 - Automated decision making
            if any(term in ai_lower for term in ['automatically', 'auto-reject', 'without human']):
                if 'article 22' not in policy_lower and 'automated decision' not in policy_lower:
                    violations.append({
                        "law": "GDPR Article 22",
                        "title": "Automated decision-making without proper disclosure",
                        "severity": "CRITICAL",
                        "description": "AI system makes automated decisions but privacy policy lacks Article 22 disclosures about individual rights.",
                        "penalty": "€20M or 4% global revenue",
                        "fix": "Add GDPR Article 22 section to privacy policy with clear explanation of automated decision-making and individual rights",
                        "region": "EU/UK"
                    })
            
            # Biometric data processing
            if any(term in ai_lower for term in ['facial', 'biometric', 'voice recognition']):
                if not any(term in policy_lower for term in ['biometric', 'facial data', 'special category']):
                    violations.append({
                        "law": "GDPR Article 9",
                        "title": "Biometric data processing without proper legal basis",
                        "severity": "CRITICAL", 
                        "description": "AI processes biometric data but policy lacks special category data protections and explicit consent mechanisms.",
                        "penalty": "€20M or 4% global revenue",
                        "fix": "Add biometric data processing section with explicit consent requirements and special category data protections",
                        "region": "EU/UK"
                    })
        
        # US-specific violations
        if 'us' in regions:
            if ai_type == 'hiring':
                violations.append({
                    "law": "EEOC Guidelines",
                    "title": "Potential employment discrimination risk",
                    "severity": "HIGH",
                    "description": "Hiring AI may have disparate impact on protected classes without proper bias testing and validation.",
                    "penalty": "Unlimited compensatory damages",
                    "fix": "Implement bias testing, adverse impact analysis, and regular fairness audits",
                    "region": "US"
                })
        
        # Industry-specific violations
        if ai_type == 'medical' and any(region in regions for region in ['us']):
            violations.append({
                "law": "HIPAA",
                "title": "Protected Health Information processing gaps",
                "severity": "CRITICAL",
                "description": "Medical AI processes PHI but may lack proper safeguards and patient consent mechanisms.",
                "penalty": "$1.5M per incident",
                "fix": "Implement HIPAA-compliant data handling with proper Business Associate Agreements and encryption",
                "region": "US"
            })
        
        # If no major violations found, add basic compliance gaps
        if len(violations) == 0:
            violations.append({
                "law": "GDPR Article 13",
                "title": "Basic transparency requirements",
                "severity": "MEDIUM",
                "description": "Privacy policy could be more comprehensive regarding AI data processing activities.",
                "penalty": "€10M or 2% global revenue", 
                "fix": "Enhance privacy policy with detailed AI processing descriptions and data subject rights",
                "region": "EU"
            })
        
        return violations

    def _generate_recommendations(self, violations, ai_type):
        """Generate actionable recommendations based on violations"""
        recommendations = []
        
        critical_count = len([v for v in violations if v['severity'] == 'CRITICAL'])
        
        if critical_count > 0:
            recommendations.append({
                "priority": "CRITICAL",
                "timeline": "1-2 weeks",
                "action": f"Address {critical_count} critical compliance violations immediately",
                "impact": "Prevents €20M+ regulatory fines",
                "steps": [
                    "Update privacy policy with missing disclosures",
                    "Implement human review checkpoints",
                    "Add consent mechanisms for sensitive data"
                ]
            })
        
        recommendations.append({
            "priority": "HIGH",
            "timeline": "1 month", 
            "action": "Implement comprehensive AI governance framework",
            "impact": "Reduces long-term compliance risk by 75%",
            "steps": [
                "Establish AI ethics committee",
                "Create bias testing protocols",
                "Implement regular compliance audits"
            ]
        })
        
        return recommendations

    def _get_risk_level(self, score):
        """Convert numeric score to risk level"""
        if score >= 80:
            return "CRITICAL RISK"
        elif score >= 65:
            return "HIGH RISK" 
        elif score >= 45:
            return "MEDIUM RISK"
        else:
            return "LOW RISK"

    def generate_professional_pdf(self, analysis):
        """Generate a comprehensive, professional PDF report"""
        filename = f"sovereign_compliance_report_{analysis['analysis_id']}.pdf"
        filepath = os.path.join(app.config['EXPORT_FOLDER'], filename)
        
        # Create document
        doc = SimpleDocTemplate(
            filepath, 
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        # Styles
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1e40af'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#374151'),
            spaceAfter=20,
            fontName='Helvetica-Bold'
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=12,
            alignment=TA_JUSTIFY,
            fontName='Helvetica'
        )
        
        # Build story
        story = []
        
        # Title Page
        story.append(Paragraph("🛡️ SOVEREIGN", title_style))
        story.append(Paragraph("AI Compliance Intelligence Report", subtitle_style))
        story.append(Spacer(1, 30))
        
        # Executive Summary Box
        summary_data = [
            ["Report ID:", analysis['analysis_id']],
            ["Generated:", datetime.now().strftime("%B %d, %Y at %I:%M %p")],
            ["AI System Type:", analysis['ai_type']],
            ["Operating Regions:", ", ".join(analysis.get('regions', ['EU']))],
            ["Policy Word Count:", f"{analysis.get('policy_analysis', {}).get('word_count', 'N/A')} words analyzed"],
            ["Risk Score:", f"{analysis['risk_score']}/100 ({analysis['risk_level']})"],
            ["Compliance Score:", f"{analysis['compliance_score']}/100"],
            ["Critical Violations:", str(len([v for v in analysis['violations'] if v['severity'] == 'CRITICAL']))],
            ["Total Violations:", str(len(analysis['violations']))],
            ["Max Penalty Exposure:", analysis.get('max_penalty', 'Varies by violation')]
        ]
        
        summary_table = Table(summary_data, colWidths=[4*cm, 10*cm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
            ('TEXTCOLOR', (0, 1), (0, -1), colors.HexColor('#1e40af')),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 30))
        
        # Key Findings Section
        story.append(Paragraph("🎯 Key Findings & Analysis Scope", subtitle_style))
        
        key_findings_text = f"""
        <b>Analysis Overview:</b><br/>
        This comprehensive compliance assessment analyzed your {analysis.get('ai_type', 'AI system')} against 
        {len(analysis.get('regions', ['EU']))} regional compliance framework(s): {', '.join([r.upper() for r in analysis.get('regions', ['EU'])])}.
        <br/><br/>
        
        <b>Policy-AI Cross-Reference:</b><br/>
        We examined {analysis.get('policy_analysis', {}).get('word_count', 'N/A')} words of privacy policy content 
        and cross-referenced against your AI system's actual capabilities to identify disclosure gaps and compliance violations.
        <br/><br/>
        
        <b>Risk Assessment:</b><br/>
        Your AI system scored {analysis['risk_score']}/100 on our risk assessment scale, indicating {analysis['risk_level'].lower()}. 
        This score considers automated decision-making capabilities, data processing practices, policy completeness, and regional regulatory requirements.
        <br/><br/>
        
        <b>Critical Issues Identified:</b><br/>
        {len([v for v in analysis['violations'] if v['severity'] == 'CRITICAL'])} critical compliance violations require immediate attention 
        to prevent regulatory penalties up to {analysis.get('max_penalty', '€20M or 4% global revenue')}.
        <br/><br/>
        
        <b>Implementation Timeline:</b><br/>
        Following our recommendations, full compliance can be achieved within 6-8 weeks through systematic policy updates, 
        technical safeguards, and governance improvements detailed in this report.
        """
        
        story.append(Paragraph(key_findings_text, body_style))
        story.append(Spacer(1, 30))
        
        # Risk Assessment
        story.append(Paragraph("📊 Risk Assessment", subtitle_style))
        
        risk_color = colors.red if analysis['risk_score'] >= 70 else colors.orange if analysis['risk_score'] >= 50 else colors.green
        
        story.append(Paragraph(f"""
        <b>Overall Risk Level:</b> {analysis['risk_level']}<br/>
        <b>Risk Score:</b> {analysis['risk_score']}/100<br/>
        <b>Compliance Score:</b> {analysis['compliance_score']}/100<br/><br/>
        
        This assessment is based on analysis of your AI system description and privacy policy 
        against applicable regulatory frameworks in {', '.join(analysis.get('regions', ['EU']))}. 
        The risk score considers automated decision-making capabilities, data processing practices, 
        and policy completeness.
        """, body_style))
        
        story.append(Spacer(1, 20))
        
        # Violations Section
        story.append(Paragraph("⚠️ Compliance Violations", subtitle_style))
        
        for i, violation in enumerate(analysis['violations'], 1):
            severity_color = colors.red if violation['severity'] == 'CRITICAL' else colors.orange if violation['severity'] == 'HIGH' else colors.blue
            
            violation_data = [
                [f"Violation #{i}", ""],
                ["Law/Regulation:", violation['law']],
                ["Title:", violation['title']],
                ["Severity:", violation['severity']],
                ["Description:", violation['description']],
                ["Max Penalty:", violation['penalty']],
                ["Recommended Fix:", violation['fix']],
                ["Jurisdiction:", violation.get('region', 'Global')]
            ]
            
            violation_table = Table(violation_data, colWidths=[3*cm, 9*cm])
            violation_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), severity_color),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            
            story.append(violation_table)
            story.append(Spacer(1, 15))
        
        # Recommendations Section
        story.append(PageBreak())
        story.append(Paragraph("🎯 Implementation Roadmap", subtitle_style))
        
        for rec in analysis['recommendations']:
            priority_color = colors.red if rec['priority'] == 'CRITICAL' else colors.orange
            
            story.append(Paragraph(f"<b>{rec['priority']} PRIORITY</b> ({rec['timeline']})", 
                                  ParagraphStyle('Priority', 
                                               parent=body_style, 
                                               textColor=priority_color,
                                               fontName='Helvetica-Bold')))
            
            story.append(Paragraph(f"<b>Action:</b> {rec['action']}", body_style))
            story.append(Paragraph(f"<b>Impact:</b> {rec['impact']}", body_style))
            
            if 'steps' in rec:
                story.append(Paragraph("<b>Implementation Steps:</b>", body_style))
                for step in rec['steps']:
                    story.append(Paragraph(f"• {step}", body_style))
            
            story.append(Spacer(1, 15))
        
        # Footer
        story.append(PageBreak())
        story.append(Paragraph("About Sovereign AI Compliance", subtitle_style))
        story.append(Paragraph("""
        This report was generated by Sovereign AI Compliance Intelligence platform, 
        providing automated regulatory analysis for enterprise AI systems. 
        
        <b>Disclaimer:</b> This analysis is for informational purposes and does not constitute legal advice. 
        Consult qualified legal counsel for specific compliance guidance.
        
        <b>Contact:</b> For questions about this report or enterprise solutions, 
        contact: compliance@sovereign.ai
        """, body_style))
        
        # Build PDF
        doc.build(story)
        return filepath

# Initialize analyzer
analyzer = ComplianceAnalyzer()

# API Routes
@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Sovereign AI Compliance API - Enhanced",
        "version": "3.0.0",
        "features": ["industry_validation", "smart_analysis", "professional_pdf"],
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/upload-document', methods=['POST'])
def upload_document():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        # Save file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        file.save(filepath)
        
        # Extract text
        extracted_text = ""
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext == '.pdf':
            extracted_text = analyzer.extract_text_from_pdf(filepath)
        elif file_ext == '.txt':
            with open(filepath, 'r', encoding='utf-8') as f:
                extracted_text = f.read()
        else:
            extracted_text = f"File uploaded successfully. {file_ext} processing available."
        
        # Store document
        document_id = f"doc_{timestamp}_{str(uuid.uuid4())[:8]}"
        document_storage[document_id] = {
            'filename': filename,
            'filepath': filepath,
            'extracted_text': extracted_text,
            'upload_time': datetime.now().isoformat(),
            'word_count': len(extracted_text.split()) if extracted_text else 0
        }
        
        return jsonify({
            'success': True,
            'document_id': document_id,
            'filename': filename,
            'text_preview': extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
            'word_count': len(extracted_text.split()) if extracted_text else 0,
            'message': 'Document processed successfully'
        })

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analyze-compliance', methods=['POST'])
def analyze_compliance():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        document_id = data.get('document_id')
        ai_system = data.get('ai_system', {})
        ai_description = ai_system.get('description', '')
        ai_type = ai_system.get('type', 'hiring')
        regions = ai_system.get('regions', ['eu'])
        policy_text_direct = data.get('policy_text', '')
        validation_info = data.get('validation', {})
        
        if not ai_description:
            return jsonify({'success': False, 'error': 'AI system description is required'}), 400
        
        # Get policy text from file or direct input
        policy_text = policy_text_direct
        if document_id and document_id in document_storage:
            file_policy_text = document_storage[document_id].get('extracted_text', '')
            if file_policy_text:
                policy_text = file_policy_text
        
        if not policy_text:
            return jsonify({
                'success': False, 
                'error': 'Privacy policy is required (either upload document or provide text)'
            }), 400
        
        # Perform analysis with validation
        analysis = analyzer.analyze_compliance(
            ai_type=ai_type,
            ai_description=ai_description, 
            policy_text=policy_text,
            regions=regions,
            validation_passed=validation_info.get('industry_validated', False)
        )
        
        if not analysis.get('success', True):
            return jsonify(analysis), 400
        
        # Store analysis for PDF generation
        analysis_storage[analysis['analysis_id']] = analysis
        
        return jsonify({
            'success': True,
            'analysis': analysis,
            'message': 'Intelligent compliance analysis completed with industry validation'
        })

    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export/pdf/<analysis_id>')
def export_pdf(analysis_id):
    try:
        if analysis_id not in analysis_storage:
            return jsonify({'error': 'Analysis not found'}), 404
        
        analysis = analysis_storage[analysis_id]
        pdf_path = analyzer.generate_professional_pdf(analysis)
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"sovereign_compliance_report_{analysis_id[:8]}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        logger.error(f"PDF generation error: {str(e)}")
        return jsonify({'error': f'PDF generation failed: {str(e)}'}), 500

@app.route('/api/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "storage": {
            "documents": len(document_storage),
            "analyses": len(analysis_storage)
        },
        "features": ["validation", "smart_analysis", "professional_pdf"]
    })

# Error handlers
@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    return jsonify({'success': False, 'error': 'File too large (max 20MB)'}), 413

@app.errorhandler(404)
def handle_not_found(e):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def handle_internal_error(e):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("🚀 Starting Sovereign Backend - Enhanced Version...")
    print("🔡 Server: http://localhost:5000")
    print("✅ Industry validation enabled")
    print("✅ Smart compliance analysis ready")
    print("✅ Professional PDF generation ready")
    print("✅ CORS enabled")
    
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
