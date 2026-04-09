"""
Configuration Management Module
Centralized configuration handling for the application
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    path: str = "taskmanager.db"
    echo: bool = False
    pool_pre_ping: bool = True
    
@dataclass 
class ServerConfig:
    """Server configuration settings"""
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    debug: bool = False
    
@dataclass
class UIConfig:
    """UI-specific configuration"""
    items_per_page: int = 50
    date_format: str = "%d.%m.%Y %H:%M"
    timezone: str = "Europe/Berlin"
    
@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None

@dataclass
class FeaturesConfig:
    """Feature flags configuration"""
    enable_ice_scoring: bool = True
    enable_recurrence: bool = True
    enable_export: bool = True
    enable_dashboard: bool = True

@dataclass
class SecurityConfig:
    """Security configuration"""
    allowed_origins: list = None
    max_file_size: int = 10485760  # 10MB
    session_timeout: int = 3600  # 1 hour
    
class ConfigManager:
    """Central configuration manager"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or os.getenv("CONFIG_FILE", "config.json")
        self.workspace_root = Path(__file__).parent.parent.parent
        
        # Initialize configurations with defaults
        self.database = DatabaseConfig()
        self.server = ServerConfig()
        self.ui = UIConfig()
        self.logging = LoggingConfig()
        self.features = FeaturesConfig()
        self.security = SecurityConfig(allowed_origins=["*"])
        
        # Load configuration from file and environment
        self.load_configuration()
        
    def load_configuration(self):
        """Load configuration from JSON file and environment variables"""
        # First load from JSON file if it exists
        config_path = Path(self.config_file)
        if not config_path.is_absolute():
            config_path = self.workspace_root / config_path
            
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    self._apply_json_config(config_data)
                    logger.info(f"Configuration loaded from {config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config file {config_path}: {e}")
        
        # Override with environment variables
        self._apply_env_config()
        
    def _apply_json_config(self, config_data: Dict[str, Any]):
        """Apply configuration from JSON data"""
        # Database configuration
        if 'database' in config_data:
            db_config = config_data['database']
            self.database.path = db_config.get('path', self.database.path)
            self.database.echo = db_config.get('echo', self.database.echo)
            self.database.pool_pre_ping = db_config.get('pool_pre_ping', self.database.pool_pre_ping)
            
        # Server configuration  
        if 'server' in config_data:
            srv_config = config_data['server']
            self.server.host = srv_config.get('host', self.server.host)
            self.server.port = srv_config.get('port', self.server.port)
            self.server.reload = srv_config.get('reload', self.server.reload)
            self.server.debug = srv_config.get('debug', self.server.debug)
            
        # UI configuration
        if 'ui' in config_data:
            ui_config = config_data['ui']
            self.ui.items_per_page = ui_config.get('items_per_page', self.ui.items_per_page)
            self.ui.date_format = ui_config.get('date_format', self.ui.date_format)
            self.ui.timezone = ui_config.get('timezone', self.ui.timezone)
            
        # Logging configuration
        if 'logging' in config_data:
            log_config = config_data['logging']
            self.logging.level = log_config.get('level', self.logging.level)
            self.logging.format = log_config.get('format', self.logging.format)
            self.logging.file_path = log_config.get('file_path', self.logging.file_path)
            
        # Features configuration
        if 'features' in config_data:
            feat_config = config_data['features']
            self.features.enable_ice_scoring = feat_config.get('enable_ice_scoring', self.features.enable_ice_scoring)
            self.features.enable_recurrence = feat_config.get('enable_recurrence', self.features.enable_recurrence)
            self.features.enable_export = feat_config.get('enable_export', self.features.enable_export)
            self.features.enable_dashboard = feat_config.get('enable_dashboard', self.features.enable_dashboard)
            
        # Security configuration
        if 'security' in config_data:
            sec_config = config_data['security']
            self.security.allowed_origins = sec_config.get('allowed_origins', self.security.allowed_origins)
            self.security.max_file_size = sec_config.get('max_file_size', self.security.max_file_size)
            self.security.session_timeout = sec_config.get('session_timeout', self.security.session_timeout)
        
    def _apply_env_config(self):
        """Apply configuration from environment variables"""
        # Database configuration
        self.database.path = os.getenv("DB_PATH", self.database.path)
        self.database.echo = os.getenv("DB_ECHO", str(self.database.echo)).lower() == "true"
        
        # Server configuration  
        self.server.host = os.getenv("SERVER_HOST", self.server.host)
        self.server.port = int(os.getenv("SERVER_PORT", self.server.port))
        self.server.reload = os.getenv("SERVER_RELOAD", str(self.server.reload)).lower() == "true"
        self.server.debug = os.getenv("DEBUG", str(self.server.debug)).lower() == "true"
        
        # UI configuration
        self.ui.items_per_page = int(os.getenv("ITEMS_PER_PAGE", self.ui.items_per_page))
        self.ui.date_format = os.getenv("DATE_FORMAT", self.ui.date_format)
        self.ui.timezone = os.getenv("TIMEZONE", self.ui.timezone)
        
        # Logging configuration
        self.logging.level = os.getenv("LOG_LEVEL", self.logging.level)
        self.logging.file_path = os.getenv("LOG_FILE", self.logging.file_path)
        
    def get_database_url(self) -> str:
        """Get database connection URL"""
        db_path = Path(self.database.path)
        if not db_path.is_absolute():
            db_path = self.workspace_root / db_path
        return f"sqlite:///{db_path}"
    
    def get_templates_path(self) -> str:
        """Get templates directory path"""
        return str(self.workspace_root / "web" / "templates")
    
    def get_static_path(self) -> str:
        """Get static files directory path"""
        return str(self.workspace_root / "web" / "static")
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_level = getattr(logging, self.logging.level.upper(), logging.INFO)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Clear existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Create formatter
        formatter = logging.Formatter(self.logging.format)
        
        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # Add file handler if specified
        if self.logging.file_path:
            log_file_path = Path(self.logging.file_path)
            if not log_file_path.is_absolute():
                log_file_path = self.workspace_root / log_file_path
                
            file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
            
        logger.info("Logging setup completed")
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary for debugging"""
        return {
            "database": {
                "path": self.database.path,
                "echo": self.database.echo,
                "pool_pre_ping": self.database.pool_pre_ping,
                "url": self.get_database_url()
            },
            "server": {
                "host": self.server.host,
                "port": self.server.port,
                "reload": self.server.reload,
                "debug": self.server.debug
            },
            "ui": {
                "items_per_page": self.ui.items_per_page,
                "date_format": self.ui.date_format,
                "timezone": self.ui.timezone
            },
            "logging": {
                "level": self.logging.level,
                "format": self.logging.format,
                "file_path": self.logging.file_path
            },
            "features": {
                "enable_ice_scoring": self.features.enable_ice_scoring,
                "enable_recurrence": self.features.enable_recurrence,
                "enable_export": self.features.enable_export,
                "enable_dashboard": self.features.enable_dashboard
            },
            "security": {
                "allowed_origins": self.security.allowed_origins,
                "max_file_size": self.security.max_file_size,
                "session_timeout": self.security.session_timeout
            },
            "paths": {
                "workspace_root": str(self.workspace_root),
                "templates": self.get_templates_path(),
                "static": self.get_static_path()
            }
        }

# Global configuration instance
config = ConfigManager()
