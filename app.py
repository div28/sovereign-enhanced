# Sovereign AI Compliance Backend - Production Ready
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
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

# Initialize Flask app
app = Flask(__name__)

# CORS Configuration - Fixed for production
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
        self.ai_types = {
            "hiring": {
                "name": "Hiring & Recruitment AI",
                "base_risk_score": 85,
                "max_penalty": "€20M or 4% global revenue",
                "laws": [
                    {"law": "GDPR Article 22", "severity": "CRITICAL"},
                    {"law": "EEOC Guidelines", "severity": "HIGH"},
                    {"law": "NYC Local Law 144", "severity": "HIGH"}
                ]
            },
            "medical": {
                "name": "Medical & Healthcare AI", 
                "base_risk_score": 95,
                "max_penalty": "$1.5M per incident",
                "laws": [
                    {"law": "HIPAA", "severity": "CRITICAL"},
                    {"law": "FDA 21 CFR", "severity": "CRITICAL"}
                ]
            },
            "finance": {
                "name": "Financial Services AI",
                "base_risk_score": 70,
                "max_penalty": "$5M + prosecution",
                "laws": [
                    {"law": "SOX", "severity": "CRITICAL"},
                    {"law": "PCI-DSS", "severity": "HIGH"}
                ]
            },
            "content": {
                "name": "Content Moderation AI",
                "base_risk_score": 60,
                "max_penalty": "6% global revenue",
                "laws": [
                    {"law": "DSA", "severity": "HIGH"},
                    {"law": "GDPR", "severity": "HIGH"}
                ]
            },
            "other": {
                "name": "Custom AI System",
                "base_risk_score": 65,
                "max_penalty": "Varies by jurisdiction",
                "laws": [
                    {"law": "GDPR", "severity": "HIGH"}
                ]
            }
        }

    def extract_text_from_pdf(self, file_path):
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

    def analyze_compliance(self, ai_type, ai_description, policy_text=""):
        """Perform REAL compliance analysis based on actual content"""
        ai_config = self.ai_types.get(ai_type, self.ai_types["other"])
        
        # Start with base score but make it content-dependent
        base_score = 30  # Start lower, build up based on actual issues
        
        policy_lower = policy_text.lower()
        description_lower = ai_description.lower()
        
        # REAL POLICY ANALYSIS - Check if policy mentions AI at all
        ai_mentioned = any(term in policy_lower for term in [
            'artificial intelligence', 'ai', 'machine learning', 'automated decision', 
            'algorithm', 'predictive', 'neural network', 'deep learning'
        ])
        
        if not ai_mentioned and len(policy_text) > 100:
            base_score += 25  # Major gap - policy doesn't mention AI at all
        
        # Check for automated decision-making mentions
        auto_decision_terms = ['automated decision', 'automatic decision', 'algorithmic decision']
        auto_mentioned = any(term in policy_lower for term in auto_decision_terms)
        
        # Check if AI actually makes automated decisions
        ai_makes_decisions = any(term in description_lower for term in [
            'automatically', 'automated', 'without human', 'auto reject', 'auto approve'
        ])
        
        if ai_makes_decisions and not auto_mentioned:
            base_score += 20  # Policy-AI mismatch on automated decisions
        
        # Industry-specific risk analysis
        if ai_type == "hiring":
            # High-risk indicators for hiring AI
            hiring_risks = [
                'facial', 'video interview', 'personality', 'cultural fit', 
                'scoring', 'ranking', 'reject', 'screening'
            ]
            risk_count = sum(1 for risk in hiring_risks if risk in description_lower)
            base_score += risk_count * 8
            
            # Check for GDPR Article 22 mention in policy
            if 'article 22' not in policy_lower and ai_makes_decisions:
                base_score += 15
                
        elif ai_type == "medical":
            # Medical AI is inherently high risk
            base_score += 30
            medical_terms = ['diagnosis', 'treatment', 'patient', 'medical', 'health']
            if any(term in description_lower for term in medical_terms):
                base_score += 20
                
        elif ai_type == "finance":
            # Financial decisions
            finance_terms = ['credit', 'loan', 'fraud', 'financial', 'payment']
            if any(term in description_lower for term in finance_terms):
                base_score += 15
        
        # For content/research AI (like The Information example)
        research_terms = ['research', 'information', 'content', 'article', 'reporting']
        if any(term in description_lower for term in research_terms) and not ai_makes_decisions:
            base_score -= 15  # Lower risk for research/content tools
            
        # Check for consent mechanisms
        consent_terms = ['consent', 'opt-in', 'permission', 'agree']
        if any(term in policy_lower for term in consent_terms):
            base_score -= 5
            
        # Check for human oversight mentions
        human_terms = ['human review', 'human oversight', 'manual review', 'human intervention']
        if any(term in policy_lower or term in description_lower for term in human_terms):
            base_score -= 10
            
        final_risk_score = max(10, min(100, base_score))
        violations = self._generate_smart_violations(ai_type, ai_description, policy_text, policy_lower, description_lower)
        
        analysis_id = f"SOV-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"
        
        return {
            "analysis_id": analysis_id,
            "timestamp": datetime.now().isoformat(),
            "ai_type": ai_config["name"],
            "risk_score": final_risk_score,
            "risk_level": self._get_risk_level(final_risk_score),
            "compliance_score": max(0, 100 - final_risk_score),
            "max_penalty": ai_config["max_penalty"],
            "violations": violations,
            "recommendations": self._generate_recommendations(violations),
            "policy_analysis": {
                "ai_mentioned": ai_mentioned,
                "automated_decisions_mentioned": auto_mentioned,
                "policy_ai_gap_detected": ai_makes_decisions and not auto_mentioned,
                "word_count": len(policy_text.split()) if policy_text else 0
            },
            "summary": f"Analysis complete. {len([v for v in violations if v['severity'] == 'CRITICAL'])} critical issues found based on actual policy-AI analysis."
        }

    def _generate_smart_violations(self, ai_type, description, policy_text, policy_lower, description_lower):
        """Generate violations based on ACTUAL policy-AI analysis"""
        violations = []
        
        # Check if AI makes automated decisions but policy doesn't mention it
        ai_makes_decisions = any(term in description_lower for term in [
            'automatically', 'automated', 'without human', 'auto reject', 'auto approve'
        ])
        
        auto_mentioned = any(term in policy_lower for term in [
            'automated decision', 'automatic decision', 'algorithmic decision'
        ])
        
        if ai_makes_decisions and not auto_mentioned and len(policy_text) > 50:
            violations.append({
                "law": "GDPR Article 22",
                "title": "Automated decision-making not disclosed",
                "severity": "CRITICAL",
                "description": f"Your AI system makes automated decisions but your privacy policy doesn't mention automated decision-making rights. AI description mentions: {self._extract_decision_phrases(description_lower)}",
                "penalty_risk": "€20M or 4% global revenue",
                "fix": "Update privacy policy to include GDPR Article 22 automated decision-making disclosures"
            })
        
        # Check for biometric data processing
        if any(term in description_lower for term in ['facial', 'biometric', 'voice', 'fingerprint']):
            biometric_mentioned = any(term in policy_lower for term in ['biometric', 'facial', 'voice'])
            if not biometric_mentioned:
                violations.append({
                    "law": "GDPR Article 9",
                    "title": "Biometric data processing not disclosed",
                    "severity": "HIGH",
                    "description": "AI system processes biometric data but privacy policy lacks proper biometric data disclosures.",
                    "penalty_risk": "€20M or 4% global revenue",
                    "fix": "Add explicit biometric data processing section to privacy policy with consent mechanisms"
                })
        
        # Industry-specific violations
        if ai_type == "hiring":
            if 'personality' in description_lower and 'personality' not in policy_lower:
                violations.append({
                    "law": "GDPR Article 9",
                    "title": "Personality assessment data processing",
                    "severity": "MEDIUM",
                    "description": "AI processes personality data which may constitute special category data requiring explicit consent.",
                    "penalty_risk": "€20M or 4% global revenue",
                    "fix": "Add personality data processing disclosure and obtain explicit consent"
                })
        
        # If no violations found and it's actually low-risk
        if not violations and any(term in description_lower for term in ['research', 'information', 'content']):
            violations.append({
                "law": "GDPR Article 13",
                "title": "Basic transparency requirements",
                "severity": "LOW",
                "description": "While your AI system appears low-risk, ensure your privacy policy includes basic data processing information.",
                "penalty_risk": "€10M or 2% global revenue",
                "fix": "Review privacy policy for completeness of data processing disclosures"
            })
        
        return violations
    
    def _extract_decision_phrases(self, description_lower):
        """Extract phrases that indicate automated decision-making"""
        decision_phrases = []
        if 'automatically' in description_lower:
            decision_phrases.append('automatically processes/decides')
        if 'without human' in description_lower:
            decision_phrases.append('without human review')
        if 'reject' in description_lower:
            decision_phrases.append('automatic rejection')
        return ', '.join(decision_phrases) if decision_phrases else 'automated processing'

    def _generate_recommendations(self, violations):
        recommendations = []
        
        critical_count = len([v for v in violations if v['severity'] == 'CRITICAL'])
        if critical_count > 0:
            recommendations.append({
                "priority": "CRITICAL",
                "timeline": "1-2 weeks",
                "action": "Address critical compliance violations immediately",
                "impact": "Prevents €20M+ fines"
            })
        
        recommendations.append({
            "priority": "HIGH", 
            "timeline": "1 month",
            "action": "Implement bias testing and fairness controls",
            "impact": "Reduces discrimination liability"
        })
        
        return recommendations

    def _get_risk_level(self, score):
        if score >= 80:
            return "CRITICAL RISK"
        elif score >= 65:
            return "HIGH RISK"
        elif score >= 45:
            return "MEDIUM RISK"
        else:
            return "LOW RISK"

    def generate_pdf_report(self, analysis):
        filename = f"sovereign_report_{analysis['analysis_id']}.pdf"
        filepath = os.path.join(app.config['EXPORT_FOLDER'], filename)
        
        doc = SimpleDocTemplate(filepath, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#1e40af'))
        story.append(Paragraph("🛡️ Sovereign AI Compliance Report", title_style))
        story.append(Spacer(1, 20))
        
        # Summary table
        summary_data = [
            ["Analysis ID:", analysis['analysis_id']],
            ["AI System:", analysis['ai_type']], 
            ["Risk Score:", f"{analysis['risk_score']}/100"],
            ["Risk Level:", analysis['risk_level']],
            ["Critical Issues:", str(len([v for v in analysis['violations'] if v['severity'] == 'CRITICAL']))]
        ]
        
        summary_table = Table(summary_data, colWidths=[2*inch, 4*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0'))
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 30))
        
        # Violations
        story.append(Paragraph("Compliance Violations", styles['Heading2']))
        for i, violation in enumerate(analysis['violations'], 1):
            story.append(Paragraph(f"{i}. {violation['title']}", styles['Heading3']))
            story.append(Paragraph(f"Law: {violation['law']}", styles['Normal']))
            story.append(Paragraph(f"Severity: {violation['severity']}", styles['Normal']))
            story.append(Paragraph(f"Fix: {violation['fix']}", styles['Normal']))
            story.append(Spacer(1, 15))
        
        doc.build(story)
        return filepath

# Initialize analyzer
analyzer = ComplianceAnalyzer()

# API Routes
@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "service": "Sovereign AI Compliance API",
        "version": "2.0.0",
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
            extracted_text = f"File uploaded. {file_ext} processing available."
        
        # Store document
        document_id = f"doc_{timestamp}_{str(uuid.uuid4())[:8]}"
        document_storage[document_id] = {
            'filename': filename,
            'filepath': filepath,
            'extracted_text': extracted_text,
            'upload_time': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'document_id': document_id,
            'filename': filename,
            'text_preview': extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
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
        ai_type = ai_system.get('type', 'other')
        policy_text_direct = data.get('policy_text', '')  # Text pasted directly
        
        if not ai_description:
            return jsonify({'success': False, 'error': 'AI description required'}), 400
        
        # Get policy text from file or direct input
        policy_text = policy_text_direct
        if document_id and document_id in document_storage:
            file_policy_text = document_storage[document_id].get('extracted_text', '')
            # Use file text if available, otherwise use direct text
            if file_policy_text:
                policy_text = file_policy_text
        
        # Require either policy text or uploaded document
        if not policy_text and not document_id:
            return jsonify({
                'success': False, 
                'error': 'Either upload a privacy policy document or provide policy text'
            }), 400
        
        # Analyze with actual policy content
        analysis = analyzer.analyze_compliance(ai_type, ai_description, policy_text)
        analysis_storage[analysis['analysis_id']] = analysis
        
        return jsonify({
            'success': True,
            'analysis': analysis,
            'message': 'Real compliance analysis completed based on policy-AI cross-reference'
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
        pdf_path = analyzer.generate_pdf_report(analysis)
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"sovereign_report_{analysis_id[:8]}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        logger.error(f"PDF error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "storage": {
            "documents": len(document_storage),
            "analyses": len(analysis_storage)
        }
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
    print("🚀 Starting Sovereign Backend...")
    print("📡 Server: http://localhost:5000")
    print("✅ CORS enabled")
    print("✅ File upload ready")
    print("✅ Analysis engine ready")
    
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
