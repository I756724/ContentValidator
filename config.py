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

# Help Portal
HELP_PORTAL_BASE = "https://help.sap.com"

# SAP Glossary
GLOSSARY_BASE = "https://help.sap.com/glossary"