"""
UA Content Validator - Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Anthropic API
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# SAPterm API
SAPTERM_API_BASE = "https://lpiprod-term.ingress.prod.lp.shoot.live.k8s-hana.ondemand.com"
SAPTERM_COOKIE = os.getenv("SAPTERM_COOKIE", "")

# SAP MT Portal — official translation API (used by SAP Translation MCP)
# Requires SSO cookies at: C:/Users/I756724/.sap-mcp/cookies/mtportal/sap_cookies.json
SAP_TRANSLATION_BASE_URL = os.getenv("SAP_TRANSLATION_BASE_URL", "https://mtportal.int.sap")

# Help Portal
HELP_PORTAL_BASE = "https://help.sap.com"

# SAP Glossary
GLOSSARY_BASE = "https://help.sap.com/glossary"