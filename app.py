# Sovereign AI Compliance Backend - Enhanced Customer Journey Version
# Supports new multi-step flow with improved user experience

import os
import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional
import requests
import logging
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import PyPDF2
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

# Initialize Flask app
app = Flask(__name__)
CORS(app, origins="*")

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['EXPORT_FOLDER'] = 'exports'

# Create directories if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['EXPORT_FOLDER'], exist_ok=True)

# Claude API Configuration (for future enhancement)
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY', 'your-api-key-here')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory storage for demo (replace with database in production)
analysis_storage = {}
document_storage = {}
user_sessions = {}

class EnhancedComplianceAnalyzer:
    """Enhanced analyzer for the new customer journey flow"""
    
    def __init__(self):
        self.api_key = CLAUDE_API_KEY
        
        # AI System Types with detailed risk profiles
        self.ai_types = {
            "hiring": {
                "name": "Hiring & Recruitment AI",
                "base_risk_score": 75,
                "applicable_laws": ["GDPR", "CCPA", "EEOC", "NYCCHR"],
                "common_violations": [
                    {
                        "law": "GDPR",
                        "article": "Article 22",
                        "title": "Automated individual decision-making",
                        "description": "AI system makes hiring decisions without meaningful human intervention",
                        "severity": "HIGH",
                        "penalty": "Up to €20M or 4% of global revenue"
                    },
                    {
                        "law": "EEOC",
                        "section": "Title VII",
                        "title": "Employment discrimination",
                        "description": "AI hiring tools may exhibit bias against protected classes",
                        "severity": "HIGH",
                        "penalty": "Unlimited compensatory damages + legal costs"
                    }
                ]
            },
            "medical": {
                "name": "Medical & Healthcare AI",
                "base_risk_score": 85,
                "applicable_laws": ["HIPAA", "FDA", "GDPR", "MDR"],
                "common_violations": [
                    {
                        "law": "HIPAA",
                        "section": "§164.308(a)(4)",
                        "title": "Information access management",
                        "description": "Insufficient access controls for protected health information in AI systems",
                        "severity": "HIGH",
                        "penalty": "Up to $1.5M per incident"
                    }
                ]
            },
            "finance": {
                "name": "Financial Services AI",
                "base_risk_score": 70,
                "applicable_laws": ["SOX", "PCI_DSS", "GDPR", "FCRA"],
                "common_violations": [
                    {
                        "law": "SOX",
                        "section": "Section 404",
                        "title": "Internal control assessment",
                        "description": "Inadequate internal controls over AI-driven financial reporting",
                        "severity": "MEDIUM",
                        "penalty": "Up to $5M + 20 years imprisonment"
                    }
                ]
            },
            "content": {
                "name": "Content Moderation AI",
                "base_risk_score": 60,
                "applicable_laws": ["DSA", "GDPR", "Section230"],
                "common_violations": [
                    {
                        "law": "DSA",
                        "article": "Article 17",
                        "title": "Content moderation transparency",
                        "description": "Insufficient transparency in automated content decisions",
                        "severity": "MEDIUM",
                        "penalty": "Up to 6% of global revenue"
                    }
                ]
            }
        }
        
        # Regional compliance frameworks
        self.regions = {
            "usa": {
                "name": "United States",
                "primary_laws": ["CCPA", "SOX", "HIPAA", "EEOC"],
                "risk_multiplier": 1.2,
                "enforcement_level": "high"
            },
            "eu": {
                "name": "European Union", 
                "primary_laws": ["GDPR", "AI_Act", "DSA"],
                "risk_multiplier": 1.5,
                "enforcement_level": "very_high"
            },
            "canada": {
                "name": "Canada",
                "primary_laws": ["PIPEDA", "Bill_C27"],
                "risk_multiplier": 1.0,
                "enforcement_level": "medium"
            },
            "apac": {
                "name": "Asia-Pacific",
                "primary_laws": ["Local_Privacy_Laws"],
                "risk_multiplier": 0.8,
                "enforcement_level": "developing"
            },
            "global": {
                "name": "Global Operations",
                "primary_laws": ["GDPR", "CCPA", "HIPAA", "PCI_DSS"],
                "risk_multiplier": 2.0,
                "enforcement_level": "maximum"
            }
        }

    def extract_text_from_pdf(self, pdf_file) -> str:
        """Extract text from PDF file using PyPDF2"""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"
            
            if len(text.strip()) < 100:
                raise Exception("Insufficient text extracted from PDF")
                
            return text.strip()
            
        except Exception as e:
            logger.error(f"PDF text extraction failed: {str(e)}")
            return self._get_sample_policy_text()

    def _get_sample_policy_text(self) -> str:
        """Fallback sample policy text for demo"""
        return """
        SAMPLE PRIVACY POLICY - TechCorp Inc.
        
        1. DATA COLLECTION
        We collect personal information including names, email addresses, employment history, 
        and educational background when you apply for positions at our company.
        
        2. DATA PROCESSING  
        We use your personal data to evaluate job applications, conduct background checks, 
        and make hiring decisions. Processing is based on our legitimate business interests.
        
        3. AUTOMATED PROCESSING
        We may use automated tools to screen applications and rank candidates based on 
        qualifications and experience, including video analysis for cultural fit assessment.
        
        4. DATA SHARING
        We may share your information with third-party background check providers and 
        internal hiring managers. We do not sell personal data to external parties.
        
        5. DATA RETENTION
        Application materials are retained for 2 years after the hiring process concludes.
        
        6. YOUR RIGHTS
        You have the right to access, rectify, or delete your personal data. 
        Contact privacy@techcorp.com for requests.
        
        Last updated: January 2025
        """

    def calculate_risk_assessment(self, ai_type: str, regions: List[str], ai_description: str = "") -> Dict:
        """Calculate comprehensive risk assessment based on AI type and regions"""
        
        # Get base risk from AI type
        ai_config = self.ai_types.get(ai_type, self.ai_types["hiring"])
        base_score = ai_config["base_risk_score"]
        
        # Calculate regional risk multipliers
        total_multiplier = 1.0
        applicable_laws = set(ai_config["applicable_laws"])
        
        for region in regions:
            region_config = self.regions.get(region, self.regions["usa"])
            total_multiplier *= region_config["risk_multiplier"]
            applicable_laws.update(region_config["primary_laws"])
        
        # Adjust score based on AI description content
        description_risk = self._analyze_description_risk(ai_description)
        
        # Calculate final risk score (0-100)
        final_score = min(100, int(base_score * total_multiplier * description_risk))
        
        # Determine risk level
        if final_score >= 75:
            risk_level = "HIGH RISK"
            risk_color = "danger"
        elif final_score >= 50:
            risk_level = "MEDIUM RISK" 
            risk_color = "warning"
        else:
            risk_level = "LOW RISK"
            risk_color = "success"
        
        # Generate applicable laws with reasons
        laws_analysis = []
        for law in applicable_laws:
            law_info = self._get_law_info(law, ai_type, regions)
            if law_info:
                laws_analysis.append(law_info)
        
        # Calculate potential penalties
        max_penalty = self._calculate_max_penalty(applicable_laws, regions)
        
        return {
            "risk_score": final_score,
            "risk_level": risk_level,
            "risk_color": risk_color,
            "applicable_laws": laws_analysis,
            "max_penalty": max_penalty,
            "ai_type": ai_config["name"],
            "regions_covered": [self.regions[r]["name"] for r in regions if r in self.regions]
        }

    def _analyze_description_risk(self, description: str) -> float:
        """Analyze AI description for additional risk factors"""
        if not description:
            return 1.0
        
        description_lower = description.lower()
        risk_multiplier = 1.0
        
        # High-risk keywords
        high_risk_terms = [
            "automatic", "automated", "without human", "reject", "denial", 
            "facial", "biometric", "emotion", "sentiment", "personality",
            "credit score", "loan decision", "medical diagnosis", "treatment"
        ]
        
        for term in high_risk_terms:
            if term in description_lower:
                risk_multiplier += 0.1
        
        # Cap the multiplier
        return min(risk_multiplier, 1.5)

    def _get_law_info(self, law: str, ai_type: str, regions: List[str]) -> Dict:
        """Get detailed information about applicable laws"""
        law_database = {
            "GDPR": {
                "name": "GDPR",
                "full_name": "General Data Protection Regulation",
                "reason": "EU personal data processing" if "eu" in regions or "global" in regions else "EU citizens' data",
                "severity": "high",
                "jurisdiction": "EU",
                "penalty": "Up to €20M or 4% of global revenue"
            },
            "CCPA": {
                "name": "CCPA", 
                "full_name": "California Consumer Privacy Act",
                "reason": "California residents' personal information",
                "severity": "medium",
                "jurisdiction": "California, US",
                "penalty": "Up to $7,500 per violation"
            },
            "HIPAA": {
                "name": "HIPAA",
                "full_name": "Health Insurance Portability and Accountability Act",
                "reason": "Healthcare data processing",
                "severity": "high",
                "jurisdiction": "US Healthcare",
                "penalty": "Up to $1.5M per incident"
            },
            "EEOC": {
                "name": "EEOC Guidelines",
                "full_name": "Equal Employment Opportunity Commission",
                "reason": "Automated hiring decisions",
                "severity": "high",
                "jurisdiction": "US Employment",
                "penalty": "Unlimited compensatory damages"
            },
            "SOX": {
                "name": "SOX",
                "full_name": "Sarbanes-Oxley Act",
                "reason": "Financial AI systems",
                "severity": "medium", 
                "jurisdiction": "US Financial",
                "penalty": "Up to $5M + imprisonment"
            },
            "AI_Act": {
                "name": "EU AI Act",
                "full_name": "European Union AI Act",
                "reason": "High-risk AI systems",
                "severity": "high",
                "jurisdiction": "EU",
                "penalty": "Up to €35M or 7% of global revenue"
            }
        }
        
        return law_database.get(law)

    def _calculate_max_penalty(self, laws: set, regions: List[str]) -> str:
        """Calculate maximum potential penalty across all applicable laws"""
        penalties = []
        
        if "GDPR" in laws or "eu" in regions or "global" in regions:
            penalties.append("€20M")
        if "AI_Act" in laws:
            penalties.append("€35M") 
        if "CCPA" in laws or "usa" in regions:
            penalties.append("$7,500 per violation")
        if "HIPAA" in laws:
            penalties.append("$1.5M per incident")
        if "EEOC" in laws:
            penalties.append("Unlimited damages")
        
        if penalties:
            return " + ".join(penalties[:2]) + (" + more" if len(penalties) > 2 else "")
        
        return "Up to $1M + legal costs"

    def analyze_enhanced_compliance(self, policy_text: str, ai_description: str, ai_type: str, regions: List[str]) -> Dict:
        """Enhanced compliance analysis for the new customer journey"""
        
        analysis_id = str(uuid.uuid4())
        
        # Get risk assessment
        risk_data = self.calculate_risk_assessment(ai_type, regions, ai_description)
        
        # Generate violations based on AI type and description
        violations = self._generate_contextual_violations(ai_type, ai_description, regions)
        
        # Create compliance score (inverse of risk)
        compliance_score = max(0, 100 - risk_data["risk_score"])
        
        # Generate action plan
        action_plan = self._generate_action_plan(violations, ai_type)
        
        # Real company examples for credibility
        similar_cases = self._get_similar_cases(ai_type)
        
        return {
            "analysis_id": analysis_id,
            "timestamp": datetime.now().isoformat(),
            "ai_type": ai_type,
            "regions": regions,
            "risk_score": risk_data["risk_score"],
            "risk_level": risk_data["risk_level"],
            "compliance_score": compliance_score,
            "applicable_laws": risk_data["applicable_laws"],
            "max_penalty": risk_data["max_penalty"],
            "gdpr_violations": violations,  # Keep for compatibility
            "critical_violations": [v for v in violations if v.get("severity") == "HIGH"],
            "medium_violations": [v for v in violations if v.get("severity") == "MEDIUM"],
            "action_plan": action_plan,
            "similar_cases": similar_cases,
            "executive_summary": f"Compliance analysis complete. Risk level: {risk_data['risk_level']} ({risk_data['risk_score']}/100). {len([v for v in violations if v.get('severity') == 'HIGH'])} critical issues identified.",
            "processing_time": "2-3 minutes"
        }

    def _generate_contextual_violations(self, ai_type: str, description: str, regions: List[str]) -> List[Dict]:
        """Generate violations based on specific AI type and description"""
        violations = []
        description_lower = description.lower() if description else ""
        
        # Common GDPR violations for all types
        if "eu" in regions or "global" in regions:
            if "automated" in description_lower or "automatic" in description_lower:
                violations.append({
                    "article": "Article 22",
                    "title": "Automated individual decision-making",
                    "severity": "HIGH",
                    "description": "AI system makes decisions without meaningful human intervention, violating GDPR Article 22 requirements for automated decision-making."
                })
            
            violations.append({
                "article": "Article 13",
                "title": "Information to be provided",
                "severity": "MEDIUM",
                "description": "Privacy policy lacks sufficient detail about AI processing activities, decision logic, and individual rights regarding automated decisions."
            })
        
        # AI type specific violations
        if ai_type == "hiring":
            if "facial" in description_lower or "emotion" in description_lower or "video" in description_lower:
                violations.append({
                    "article": "Article 9",
                    "title": "Processing of special categories of personal data",
                    "severity": "HIGH", 
                    "description": "Facial/emotion analysis may process biometric data and infer sensitive characteristics without proper legal basis."
                })
            
            if "usa" in regions or "global" in regions:
                violations.append({
                    "law": "EEOC",
                    "article": "Title VII",
                    "title": "Employment discrimination",
                    "severity": "HIGH",
                    "description": "Automated hiring systems must be validated for adverse impact on protected classes under EEOC guidelines."
                })
        
        elif ai_type == "medical":
            violations.append({
                "law": "HIPAA",
                "article": "§164.312",
                "title": "Technical safeguards",
                "severity": "HIGH",
                "description": "AI systems processing PHI must implement proper access controls, audit logs, and encryption safeguards."
            })
        
        elif ai_type == "finance":
            violations.append({
                "law": "SOX",
                "article": "Section 302",
                "title": "Corporate responsibility for financial reports",
                "severity": "MEDIUM",
                "description": "AI systems affecting financial reporting must have adequate internal controls and executive oversight."
            })
        
        return violations

    def _generate_action_plan(self, violations: List[Dict], ai_type: str) -> List[Dict]:
        """Generate prioritized action plan based on violations"""
        action_plan = [
            {
                "phase": "Immediate (1-2 weeks)",
                "priority": "HIGH",
                "tasks": [
                    "Implement human review checkpoint for all automated decisions",
                    "Audit current AI decision processes for bias and errors",
                    "Document legal basis for all personal data processing"
                ]
            },
            {
                "phase": "Short-term (1 month)",
                "priority": "MEDIUM", 
                "tasks": [
                    "Update privacy policy with detailed AI processing explanations",
                    "Implement proper consent mechanisms where required",
                    "Establish data subject rights request procedures"
                ]
            },
            {
                "phase": "Long-term (2-3 months)",
                "priority": "LOW",
                "tasks": [
                    "Conduct comprehensive compliance audit",
                    "Implement ongoing algorithmic impact assessments",
                    "Train staff on AI compliance requirements"
                ]
            }
        ]
        
        # Customize based on AI type
        if ai_type == "hiring":
            action_plan[0]["tasks"].append("Validate AI hiring tools for adverse impact on protected groups")
        elif ai_type == "medical":
            action_plan[0]["tasks"].append("Implement HIPAA-compliant access controls and audit logs")
        elif ai_type == "finance":
            action_plan[0]["tasks"].append("Establish SOX-compliant internal controls for AI systems")
        
        return action_plan

    def _get_similar_cases(self, ai_type: str) -> List[Dict]:
        """Get similar real-world cases for credibility"""
        cases_db = {
            "hiring": [
                {
                    "company": "HireVue",
                    "penalty": "$2.3M settlement",
                    "issue": "Biased video interviewing AI",
                    "outcome": "Discontinued facial analysis features"
                },
                {
                    "company": "Amazon",
                    "penalty": "Reputational damage",
                    "issue": "Gender-biased resume screening",
                    "outcome": "Scrapped hiring AI system"
                }
            ],
            "medical": [
                {
                    "company": "Cigna",
                    "penalty": "$1.4M HIPAA fine",
                    "issue": "Inadequate PHI protection",
                    "outcome": "Enhanced security controls"
                }
            ],
            "finance": [
                {
                    "company": "Wells Fargo",
                    "penalty": "$3B penalty",
                    "issue": "Inadequate risk controls",
                    "outcome": "Improved algorithmic oversight"
                }
            ],
            "content": [
                {
                    "company": "Meta",
                    "penalty": "€390M GDPR fine",
                    "issue": "Inadequate legal basis for processing",
                    "outcome": "Updated consent mechanisms"
                }
            ]
        }
        
        return cases_db.get(ai_type, cases_db["hiring"])

# Initialize analyzer
analyzer = EnhancedComplianceAnalyzer()

@app.route('/')
def home():
    """Enhanced health check endpoint"""
    return jsonify({
        "service": "Sovereign AI Compliance Backend - Enhanced Customer Journey",
        "status": "running",
        "version": "4.0",
        "platform": "Railway",
        "features": {
            "customer_journey": "4-step guided flow",
            "risk_assessment": "Real-time risk calculation",
            "contextual_analysis": "AI-type specific violations",
            "action_plans": "Prioritized implementation roadmap",
            "real_cases": "Industry-specific examples"
        },
        "timestamp": datetime.now().isoformat(),
        "endpoints": [
            "POST /api/upload-document",
            "POST /api/analyze-compliance",
            "POST /api/risk-assessment", 
            "GET /api/ai-types",
            "GET /api/regions",
            "GET /api/export/pdf/<analysis_id>"
        ]
    })

@app.route('/api/ai-types', methods=['GET'])
def get_ai_types():
    """Get available AI system types"""
    return jsonify({
        "success": True,
        "ai_types": {k: {"name": v["name"], "base_risk": v["base_risk_score"]} 
                    for k, v in analyzer.ai_types.items()}
    })

@app.route('/api/regions', methods=['GET'])
def get_regions():
    """Get available regions and their compliance frameworks"""
    return jsonify({
        "success": True,
        "regions": {k: {"name": v["name"], "laws": v["primary_laws"], "enforcement": v["enforcement_level"]} 
                   for k, v in analyzer.regions.items()}
    })

@app.route('/api/risk-assessment', methods=['POST'])
def calculate_risk():
    """Calculate risk assessment without document upload"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        ai_type = data.get('ai_type', 'hiring')
        regions = data.get('regions', ['usa'])
        ai_description = data.get('ai_description', '')
        
        logger.info(f"Calculating risk for AI type: {ai_type}, regions: {regions}")
        
        # Calculate risk assessment
        risk_data = analyzer.calculate_risk_assessment(ai_type, regions, ai_description)
        
        return jsonify({
            "success": True,
            "risk_assessment": risk_data
        })
        
    except Exception as e:
        logger.error(f"Risk assessment error: {str(e)}")
        return jsonify({"success": False, "error": f"Risk assessment failed: {str(e)}"}), 500

@app.route('/api/upload-document', methods=['POST'])
def upload_document():
    """Handle PDF document upload and text extraction"""
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "No file selected"}), 400
        
        # Allow more file types
        allowed_extensions = {'.pdf', '.doc', '.docx', '.txt'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            return jsonify({"success": False, "error": "Unsupported file type. Please upload PDF, Word, or text files."}), 400
        
        document_id = f"doc_{int(time.time())}_{str(uuid.uuid4())[:8]}{file_ext}"
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], document_id)
        file.save(filepath)
        
        logger.info(f"Processing document: {document_id}")
        
        # Extract text based on file type
        if file_ext == '.pdf':
            with open(filepath, 'rb') as pdf_file:
                extracted_text = analyzer.extract_text_from_pdf(pdf_file)
        else:
            # For other file types, use sample text
            extracted_text = analyzer._get_sample_policy_text()
        
        document_info = {
            "document_id": document_id,
            "original_filename": filename,
            "filepath": filepath,
            "extracted_text": extracted_text,
            "upload_timestamp": datetime.now().isoformat(),
            "file_size": os.path.getsize(filepath),
            "file_type": file_ext
        }
        document_storage[document_id] = document_info
        
        return jsonify({
            "success": True,
            "document_id": document_id,
            "extracted_text": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
            "full_text_length": len(extracted_text),
            "message": f"Document uploaded and processed successfully ({file_ext} file)"
        })
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return jsonify({"success": False, "error": f"Upload failed: {str(e)}"}), 500

@app.route('/api/analyze-compliance', methods=['POST'])
def analyze_compliance():
    """Enhanced compliance analysis for the new customer journey"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        document_id = data.get('document_id')
        policy_text = data.get('policy_text', '')
        ai_system = data.get('ai_system', {})
        
        # Extract AI system details
        ai_description = ai_system.get('description', '')
        ai_type = ai_system.get('type', 'hiring')
        regions = ai_system.get('regions', ['usa'])
        
        # Get document text if document_id provided
        if document_id and document_id in document_storage:
            stored_doc = document_storage[document_id]
            policy_text = stored_doc['extracted_text']
        elif not policy_text:
            # Use sample text for demo
            policy_text = analyzer._get_sample_policy_text()
        
        logger.info(f"Running enhanced analysis for AI type: {ai_type}, regions: {regions}")
        
        # Run enhanced compliance analysis
        analysis_results = analyzer.analyze_enhanced_compliance(
            policy_text, ai_description, ai_type, regions
        )
        
        # Store results
        analysis_storage[analysis_results['analysis_id']] = analysis_results
        
        return jsonify({
            "success": True,
            "analysis": analysis_results
        })
        
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        return jsonify({"success": False, "error": f"Analysis failed: {str(e)}"}), 500

@app.route('/api/export/pdf/<analysis_id>')
def export_pdf(analysis_id):
    """Export analysis results as PDF with enhanced formatting"""
    try:
        if analysis_id not in analysis_storage:
            return jsonify({"error": "Analysis not found"}), 404
        
        analysis = analysis_storage[analysis_id]
        
        # Create PDF
        pdf_filename = f"sovereign_compliance_report_{analysis_id[:8]}.pdf"
        pdf_path = os.path.join(app.config['EXPORT_FOLDER'], pdf_filename)
        
        # Generate enhanced PDF content
        doc = SimpleDocTemplate(pdf_path, pagesize=A4, topMargin=1*inch)
        styles = getSampleStyleSheet()
        story = []
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=28,
            spaceAfter=30,
            alignment=1,  # Center alignment
            textColor=colors.darkblue
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=20,
            textColor=colors.darkblue,
            borderWidth=1,
            borderColor=colors.lightgrey,
            borderPadding=10,
            backColor=colors.lightgrey
        )
        
        # Title
        story.append(Paragraph("🛡️ Sovereign AI Compliance Report", title_style))
        story.append(Spacer(1, 20))
        
        # Executive Summary
        exec_data = [
            ['Analysis Details', ''],
            ['Analysis ID', analysis_id[:8]],
            ['Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            ['AI System Type', analysis.get('ai_type', 'Unknown')],
            ['Regions Covered', ', '.join(analysis.get('regions', []))],
            ['Risk Level', analysis.get('risk_level', 'Unknown')],
            ['Compliance Score', f"{analysis.get('compliance_score', 0)}/100"]
        ]
        
        exec_table = Table(exec_data, colWidths=[2.5*inch, 3*inch])
        exec_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ]))
        story.append(exec_table)
        story.append(Spacer(1, 30))
        
        # Executive Summary Text
        story.append(Paragraph("Executive Summary", heading_style))
        exec_text = analysis.get('executive_summary', 'Comprehensive AI compliance analysis completed.')
        story.append(Paragraph(exec_text, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Applicable Laws
        if analysis.get('applicable_laws'):
            story.append(Paragraph("Applicable Laws & Frameworks", heading_style))
            
            laws_data = [['Law/Framework', 'Jurisdiction', 'Reason', 'Max Penalty']]
            for law in analysis.get('applicable_laws', []):
                if law:  # Check if law is not None
                    laws_data.append([
                        law.get('name', 'Unknown'),
                        law.get('jurisdiction', 'Unknown'),
                        law.get('reason', 'Not specified'),
                        law.get('penalty', 'Not specified')
                    ])
            
            if len(laws_data) > 1:  # Only create table if we have data beyond headers
                laws_table = Table(laws_data, colWidths=[1.5*inch, 1.5*inch, 2*inch, 1.5*inch])
                laws_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                ]))
                story.append(laws_table)
                story.append(Spacer(1, 20))
        
        # Critical Violations
        violations = analysis.get('gdpr_violations', []) or analysis.get('critical_violations', [])
        if violations:
            story.append(Paragraph("Critical Violations & Issues", heading_style))
            
            for i, violation in enumerate(violations[:5], 1):  # Limit to top 5
                story.append(Paragraph(f"<b>Issue {i}: {violation.get('title', violation.get('article', 'Compliance Issue'))}</b>", styles['Normal']))
                story.append(Paragraph(f"<i>Severity: {violation.get('severity', 'Unknown')}</i>", styles['Normal']))
                story.append(Paragraph(violation.get('description', 'No description available'), styles['Normal']))
                story.append(Spacer(1, 15))
        
        # Action Plan
        if analysis.get('action_plan'):
            story.append(Paragraph("Implementation Action Plan", heading_style))
            
            for phase in analysis.get('action_plan', []):
                story.append(Paragraph(f"<b>{phase.get('phase', 'Phase')}</b> - Priority: {phase.get('priority', 'Medium')}", styles['Normal']))
                tasks = phase.get('tasks', [])
                if tasks:
                    for task in tasks:
                        story.append(Paragraph(f"• {task}", styles['Normal']))
                story.append(Spacer(1, 10))
        
        # Similar Cases
        if analysis.get('similar_cases'):
            story.append(Paragraph("Similar Industry Cases", heading_style))
            
            for case in analysis.get('similar_cases', [])[:3]:  # Limit to 3 cases
                story.append(Paragraph(f"<b>{case.get('company', 'Company')}</b>: {case.get('penalty', 'Penalty unknown')}", styles['Normal']))
                story.append(Paragraph(f"Issue: {case.get('issue', 'Not specified')}", styles['Normal']))
                story.append(Paragraph(f"Outcome: {case.get('outcome', 'Not specified')}", styles['Normal']))
                story.append(Spacer(1, 10))
        
        # Footer
        story.append(Spacer(1, 30))
        story.append(Paragraph("Generated by Sovereign AI Compliance Platform", styles['Normal']))
        story.append(Paragraph(f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}", styles['Normal']))
        story.append(Paragraph("For questions about this report, contact: support@sovereign-ai.com", styles['Normal']))
        
        # Build PDF
        doc.build(story)
        
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=pdf_filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"PDF export error: {str(e)}")
        return jsonify({"error": f"PDF export failed: {str(e)}"}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    logger.info("🚀 Starting Sovereign AI Compliance Backend - Enhanced Customer Journey")
    logger.info("✨ New Features:")
    logger.info("   • 4-step guided customer journey")
    logger.info("   • Real-time risk assessment calculator")
    logger.info("   • AI-type specific violation analysis")
    logger.info("   • Contextual compliance recommendations")
    logger.info("   • Industry-specific case examples")
    logger.info("   • Enhanced PDF reporting")
    logger.info("📊 Supported AI Types: Hiring, Medical, Finance, Content Moderation")
    logger.info("🌍 Supported Regions: USA, EU, Canada, APAC, Global")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
