# Directory Structure

This document outlines the organized directory structure of the Anime Video Generator project.

## 📁 Root Directory Structure

```
htmlParser/
├── 📁 agents/                          # Core processing agents
│   ├── 📁 quality_agents/             # Specialized quality validation agents
│   ├── character_analysis_agent.py    # ChromaDB character analysis
│   ├── content_agent.py               # AI content processing
│   ├── transcript_agent.py            # Multi-source transcript discovery
│   ├── transcript_source_agent.py     # Source discovery and evaluation
│   ├── video_agent.py                # Video generation and compilation
│   ├── quality_agent.py              # Main quality assurance interface
│   └── workflow_orchestrator.py      # Workflow coordination
├── 📁 config/                         # Configuration files
│   ├── settings.py                   # Application settings
│   └── episode_configs/              # Episode-specific configurations
├── 📁 core/                          # Core system modules
│   ├── database.py                   # Database management
│   ├── schemas.py                    # Data schemas and validation
│   ├── show_registry.py              # Show naming and metadata validation
│   └── metadata_schemas.py           # ChromaDB metadata schemas
├── 📁 data/                          # Data storage
│   ├── 📁 databases/                 # All database files
│   │   ├── video_generator.db        # Main SQLite database
│   │   ├── character_db/             # ChromaDB character data
│   │   └── vector_db/               # Vector database storage
│   ├── 📁 models/                    # AI models and training data
│   └── 📁 exports/                   # Exported data and backups
├── 📁 demos/                         # Demo scripts and examples
│   ├── character_analysis_demo.py    # Character analysis demonstration
│   └── demo_season_processing.py     # Season processing example
├── 📁 docs/                          # Documentation
│   ├── 📁 implementation-plans/       # Feature implementation plans
│   │   ├── CROSS_SEASON_CONTEXT_IMPLEMENTATION_PLAN.md
│   │   ├── METADATA_VALIDATION_PLAN.md
│   │   ├── NEW_FEATURES_IMPLEMENTATION_PLAN.md
│   │   └── VIDEO_LENGTH_CONFIGURATION_PLAN.md
│   ├── 📁 guides/                    # User guides
│   │   └── SEASON_PROCESSING_GUIDE.md
│   ├── 📁 summaries/                 # Implementation summaries
│   │   ├── README_INTEGRATION_SUMMARY.md
│   │   └── SEASON_PROCESSING_IMPLEMENTATION_SUMMARY.md
│   └── DIRECTORY_STRUCTURE.md        # This file
├── 📁 logs/                          # Application logs
│   └── anime_generator.log           # Main application log
├── 📁 media/                         # Generated media files
│   ├── images/                       # AI-generated images
│   ├── audio/                        # Generated audio files
│   └── videos/                       # Final video outputs
├── 📁 notebooks/                     # Jupyter notebooks for analysis
├── 📁 scripts/                       # Utility scripts
│   ├── migrate_metadata.py           # Database migration scripts
│   └── maintenance/                  # System maintenance scripts
├── 📁 tests/                         # Test files
│   ├── test_*.py                     # Unit tests
│   ├── run_tests.py                  # Test runner
│   └── test_season_processing.py     # Season processing tests
├── 📁 utils/                         # Utility modules
│   ├── web_utils.py                  # Web scraping utilities
│   ├── file_utils.py                 # File handling utilities
│   └── format_utils.py               # Data formatting utilities
├── 📁 validation/                    # Validation modules
├── main_refactored.py                # Main CLI application
├── main.py                          # Legacy main file
├── README.md                        # Project documentation
├── requirements.txt                 # Python dependencies
├── requirements-vector.txt          # Vector database dependencies
├── pyproject.toml                   # Project configuration
└── runtime.txt                      # Runtime specifications
```

## 📂 Key Directory Purposes

### **Core Application**
- `agents/` - Modular processing agents for different system components
- `core/` - Essential system modules and data structures
- `config/` - Application configuration and settings

### **Data Management**
- `data/databases/` - All database files (SQLite, ChromaDB, Vector DB)
- `data/models/` - AI models and training data
- `data/exports/` - Data exports and backups

### **Development & Testing**
- `tests/` - All test files and test runners
- `demos/` - Example scripts and demonstrations
- `scripts/` - Utility and maintenance scripts

### **Documentation**
- `docs/implementation-plans/` - Feature development plans
- `docs/guides/` - User guides and tutorials
- `docs/summaries/` - Implementation summaries and reports

### **Output & Logging**
- `media/` - Generated videos, images, and audio
- `logs/` - Application logs and debug information

## 🧹 Cleanup Benefits

1. **Organized Documentation** - All planning and implementation docs in `docs/`
2. **Centralized Data** - All databases and models in `data/`
3. **Proper Test Organization** - All test files in `tests/`
4. **Clean Root Directory** - Only essential files in project root
5. **Improved .gitignore** - Prevents future clutter and protects sensitive data

This structure follows industry best practices for Python projects and makes the codebase much more maintainable and navigable.
