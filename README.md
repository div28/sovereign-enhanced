**🛡️ Sovereign: AI Compliance Violation Predictor
**
AI-powered platform that helps organizations assess GDPR compliance risks in their AI systems through intelligent document analysis.

**Overview**
Sovereign analyzes privacy policies and AI system descriptions to identify compliance gaps and generate actionable implementation roadmaps. Built as a capstone project for the Next Gen Product Manager bootcamp.

**Key Features**:
Document upload with OCR processing
5-step compliance analysis (GDPR → Cross-reference → Bias → Ethics → Planning)
Professional PDF/CSV report generation
<10 second analysis time

**Usage**
Upload privacy policy (PDF/text)
Describe your AI system
Run compliance analysis
Download professional report

**Project Structure
**├── app.py              # Flask backend
├── index.html          # Main application
├── static/
│   ├── styles.css      # Styling
│   └── script.js       # Frontend logic
├── requirements.txt    # Dependencies
└── docs/
    ├── PRD.docx        # Product Requirements
    └── kickoff.docx    # Project planning

**Technology Stack
**Frontend: HTML5, CSS3, Vanilla JavaScript
Backend: Python Flask
Document Processing: PyPDF2, Google Vision OCR
Reporting: ReportLab (PDF), CSV export
AI Analysis: Claude API integration

**Demo Scenarios
**Three pre-built scenarios for demonstration:

DPO Use Case: Privacy policy gap analysis
AI PM Use Case: Comprehensive hiring AI assessment
Consultant Use Case: Financial AI compliance audit
