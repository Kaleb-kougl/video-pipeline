# Project Structure & Organization

This document outlines the complete organization of the Anime Video Generator project.

## 🏗️ Directory Structure

```
htmlParser/                           # Root project directory
├── 📁 agents/                        # Core processing agents (9 agents)
│   ├── 📁 quality_agents/            # Quality validation subsystem (6 agents)
│   │   ├── __init__.py
│   │   ├── quality_coordinator.py    # Orchestrates all quality validation
│   │   ├── transcript_quality_agent.py
│   │   ├── content_quality_agent.py
│   │   ├── video_quality_agent.py
│   │   ├── discovery_quality_agent.py
│   │   └── workflow_quality_agent.py
│   ├── __init__.py
│   ├── transcript_agent.py           # Multi-source transcript discovery
│   ├── transcript_source_agent.py    # Source discovery & evaluation
│   ├── content_agent.py              # AI content processing
│   ├── video_agent.py                # Video generation
│   ├── quality_agent.py              # Main quality interface
│   ├── discovery_agent.py            # Episode URL discovery
│   ├── config_manager.py             # Episode configuration
│   └── workflow_orchestrator.py      # Pipeline coordination
│
├── 📁 core/                          # Core infrastructure
│   ├── __init__.py
│   ├── database.py                   # SQLite operations
│   └── schemas.py                    # Data models & validation
│
├── 📁 config/                        # Configuration management
│   ├── __init__.py
│   └── settings.py                   # Application settings
│
├── 📁 utils/                         # Shared utilities
│   ├── __init__.py
│   └── web_utils.py                  # Web scraping utilities
│
├── 📁 media/                         # Media processing
│   ├── __init__.py
│   └── media_utils.py                # Video/audio generation
│
├── 📁 tests/                         # Comprehensive test suite
│   ├── __init__.py                   # Test package configuration
│   ├── test_all_agents.py            # Comprehensive validation
│   ├── test_agents_fixed.py          # Targeted fixes validation
│   ├── test_transcript_agent.py      # Transcript discovery tests
│   ├── test_transcript_source_agent.py # Source discovery tests
│   ├── test_complete_discovery.py    # Discovery integration tests
│   ├── test_complex_shows.py         # Complex show handling tests
│   └── test_fandom_search.py         # Fandom search tests
│
├── 📁 docs/                          # Documentation
│   ├── README_MODULAR.md             # Detailed architecture guide
│   ├── AGENT_VALIDATION_REPORT.md    # Comprehensive validation report
│   ├── RESTRUCTURING_SUMMARY.md      # Migration documentation
│   ├── TRANSCRIPT_AGENT_GUIDE.md     # Transcript agent guide
│   └── project_structure_plan.md     # Original structure plan
│
├── 📁 notebooks/                     # Jupyter notebooks
│   ├── MovieTest.ipynb               # Movie processing experiments
│   ├── Untitled.ipynb                # General experimentation
│   └── Untitled1.ipynb               # Additional experiments
│
├── 📁 scripts/                       # Utility scripts
│   ├── migrate_structure.py          # Structure migration utility
│   └── main copy.py                  # Legacy script backup
│
├── 📁 logs/                          # Application logs
│   └── anime_generator.log           # System operation logs
│
├── 📁 data/                          # Data storage
│   └── episode_data/                 # Episode-specific data
│
├── 📁 My Hero Academia/              # Example generated content
│   ├── tldr_mha_intro.mp4           # Generated video content
│   └── Season1/Episode4/             # Episode-specific outputs
│       ├── My Hero Academia_1_4_model.json
│       ├── My Hero Academia_1_4.mp4
│       ├── My Hero Academia_4_*.png  # Generated images
│       └── My Hero Academia_4.wav    # Generated audio
│
├── 📄 main.py                        # Original monolithic implementation (2,249 lines)
├── 📄 main_refactored.py             # Modern modular CLI interface
├── 📄 run_tests.py                   # Test suite runner
├── 📄 README.md                      # Main project README
├── 📄 requirements.txt               # Python dependencies
├── 📄 .gitignore                     # Git ignore rules
├── 📄 video_generator.db             # SQLite database
└── 📄 My Hero Academia_My Hero Academia_4_model.json # Episode model
```

## 📦 Package Organization

### Core Packages (Production Code)
- **`agents/`** - Main processing logic (15 total agents)
- **`core/`** - Database and schema management
- **`config/`** - Configuration and settings
- **`utils/`** - Shared utility functions
- **`media/`** - Media processing utilities

### Development & Documentation
- **`tests/`** - Comprehensive test suite (8 test files)
- **`docs/`** - Complete documentation set (5 documents)
- **`notebooks/`** - Jupyter experiments and analysis
- **`scripts/`** - Development and migration utilities
- **`logs/`** - Runtime logs and debugging

### Data & Output
- **`data/`** - Structured data storage
- **`My Hero Academia/`** - Example generated content
- **Database files** - SQLite storage

## 🔧 Key Files

### Entry Points
- **`main_refactored.py`** - Primary CLI interface (15+ commands)
- **`main.py`** - Original implementation (preserved, fully commented)
- **`run_tests.py`** - Test suite runner

### Configuration
- **`requirements.txt`** - Python dependencies
- **`config/settings.py`** - Application configuration
- **`.gitignore`** - Version control exclusions

### Documentation
- **`README.md`** - Main project overview
- **`docs/README_MODULAR.md`** - Detailed architecture guide
- **`docs/AGENT_VALIDATION_REPORT.md`** - Validation results

## 🧪 Testing Organization

### Test Categories
1. **Individual Agent Tests** - Test each agent independently
2. **Integration Tests** - Test agent interactions
3. **Discovery Tests** - Test transcript discovery functionality
4. **Validation Tests** - Comprehensive system validation

### Test Files
- `test_all_agents.py` - Complete system validation
- `test_agents_fixed.py` - Targeted testing with fixes
- `test_transcript_*.py` - Transcript-specific tests
- `test_complete_discovery.py` - Discovery integration
- `test_complex_shows.py` - Complex show handling
- `test_fandom_search.py` - Fandom search functionality

## 📊 Metrics

### Codebase Size
- **Total Agents:** 15 (9 core + 6 quality)
- **Lines of Code:** ~3,500+ (modular) + 2,249 (original)
- **Test Coverage:** 8 comprehensive test files
- **Documentation:** 5 detailed documents

### File Organization
- **Python Packages:** 6 organized packages
- **Support Directories:** 5 (tests, docs, notebooks, scripts, logs)
- **Generated Content:** Organized by show/season/episode
- **Total Files:** 50+ organized files

## 🚀 Usage Patterns

### Development Workflow
1. Edit agents in `agents/`
2. Test with files in `tests/`
3. Run via `main_refactored.py`
4. Check logs in `logs/`
5. Update docs in `docs/`

### Production Deployment
1. Use `main_refactored.py` as entry point
2. Configure via `config/settings.py`
3. Monitor via `logs/` directory
4. Store data in `data/` directory

### Testing & Validation
1. Run `python run_tests.py` for full suite
2. Individual tests: `python tests/test_*.py`
3. Validation report: `docs/AGENT_VALIDATION_REPORT.md`

## 🔄 Migration Benefits

### Before (Monolithic)
- Single 2,249-line file
- Mixed responsibilities
- Difficult to test
- Hard to maintain

### After (Modular)
- 15 specialized agents
- Clean separation of concerns
- Comprehensive test suite
- Easy to extend and maintain
- Quality assurance at every stage

## 📈 Future Organization

### Planned Additions
- `api/` - REST API interface
- `web/` - Web frontend
- `docker/` - Containerization
- `deploy/` - Deployment scripts
- `monitoring/` - System monitoring

### Scalability
- Each agent can be independently scaled
- Quality system provides monitoring foundation
- Modular structure supports microservices
- Clean interfaces enable API wrapping

---

This organization provides a solid foundation for both development and production use, with clear separation of concerns and comprehensive testing coverage.
