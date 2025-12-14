"""
Configuration settings for Provider Directory AI Agent System
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Keys
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./provider_directory.db')
    
    # NPI Registry
    NPI_REGISTRY_URL = os.getenv('NPI_REGISTRY_URL', 'https://npiregistry.cms.hhs.gov/api/')
    
    # Processing Configuration
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', 50))
    CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', 0.75))
    MAX_WORKERS = int(os.getenv('MAX_WORKERS', 5))
    
    # Validation Settings
    MIN_CONFIDENCE_SCORE = 0.6
    HIGH_PRIORITY_THRESHOLD = 0.4
    
    # Timeouts
    WEB_SCRAPING_TIMEOUT = 10
    API_REQUEST_TIMEOUT = 5
    
    # File Paths
    DATA_DIR = 'data'
    REPORTS_DIR = 'reports'
    TEMP_DIR = 'temp'
    
    # Agent Settings
    AGENT_RETRY_COUNT = 3
    AGENT_RETRY_DELAY = 2
