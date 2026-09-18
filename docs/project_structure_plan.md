# Recommended Project Structure for HTML Parser/Anime Video Generator

## Current Issues
- Single 1800+ line file
- Multiple responsibilities mixed together
- Hard to maintain and test
- No clear separation of concerns

## Proposed Structure

```
htmlParser/
├── main.py                     # Main entry point and CLI
├── requirements.txt
├── README.md
├── config/
│   ├── __init__.py
│   ├── settings.py            # Configuration settings
│   └── episode_configs.py     # Episode configurations
├── agents/
│   ├── __init__.py
│   ├── content_agent.py       # Content extraction and analysis
│   ├── transcript_agent.py    # Transcript discovery
│   ├── video_agent.py         # Video generation
│   └── quality_agent.py       # Quality assurance
├── core/
│   ├── __init__.py
│   ├── database.py            # Database operations
│   ├── orchestrator.py        # Workflow orchestration
│   └── schemas.py             # Pydantic models
├── media/
│   ├── __init__.py
│   ├── image_generator.py     # Image creation
│   ├── audio_generator.py     # Audio/TTS generation
│   └── video_composer.py      # Video composition
├── utils/
│   ├── __init__.py
│   ├── web_scraper.py         # HTML parsing utilities
│   ├── file_utils.py          # File operations
│   └── text_processing.py     # Text processing helpers
├── tests/
│   ├── __init__.py
│   ├── test_transcript_agent.py
│   ├── test_content_agent.py
│   └── test_integration.py
└── data/
    └── episode_data/          # Generated content storage
```

## Benefits of This Structure

### 1. **Separation of Concerns**
- Each module has a single responsibility
- Easier to test individual components
- Better code reusability

### 2. **Agent-Based Architecture**
- Each agent handles specific tasks
- Clear interfaces between components
- Easy to extend with new agents

### 3. **Configuration Management**
- Centralized configuration
- Environment-specific settings
- Easy to modify show configurations

### 4. **Media Pipeline**
- Dedicated modules for each media type
- Reusable media generation components
- Better error handling and logging

### 5. **Testing & Maintenance**
- Unit tests for each component
- Integration tests for workflows
- Easier debugging and profiling

## Migration Strategy

### Phase 1: Extract Core Components
1. Create basic directory structure
2. Extract database operations → `core/database.py`
3. Extract Pydantic schemas → `core/schemas.py`
4. Update imports in main.py

### Phase 2: Extract Agents
1. Move TranscriptDiscoveryAgent → `agents/transcript_agent.py`
2. Move other agents to respective files
3. Create agent factory/registry

### Phase 3: Extract Media Generation
1. Move image generation → `media/image_generator.py`
2. Move audio generation → `media/audio_generator.py`
3. Move video composition → `media/video_composer.py`

### Phase 4: Extract Utilities
1. Move web scraping → `utils/web_scraper.py`
2. Move file operations → `utils/file_utils.py`
3. Create shared utilities

### Phase 5: Configuration & Testing
1. Create configuration system
2. Add comprehensive tests
3. Update documentation

## Implementation Notes

### Dependency Injection
```python
# Instead of hardcoded dependencies
class WorkflowOrchestrator:
    def __init__(self):
        self.db = DatabaseManager()
        self.transcript_agent = TranscriptDiscoveryAgent()
        # ...

# Use dependency injection
class WorkflowOrchestrator:
    def __init__(self, db_manager, transcript_agent, video_agent, ...):
        self.db = db_manager
        self.transcript_agent = transcript_agent
        # ...
```

### Configuration System
```python
# config/settings.py
from pydantic import BaseSettings

class Settings(BaseSettings):
    # Database settings
    database_path: str = "episodes.db"
    
    # Media settings
    output_directory: str = "data/episode_data"
    image_quality: str = "high"
    
    # API settings
    gemini_api_key: str
    
    class Config:
        env_file = ".env"
```

### Agent Registry
```python
# agents/__init__.py
from .transcript_agent import TranscriptDiscoveryAgent
from .content_agent import ContentAgent
from .video_agent import VideoGenerationAgent
from .quality_agent import QualityAssuranceAgent

class AgentRegistry:
    def __init__(self, config):
        self.transcript_agent = TranscriptDiscoveryAgent(config)
        self.content_agent = ContentAgent(config)
        self.video_agent = VideoGenerationAgent(config)
        self.quality_agent = QualityAssuranceAgent(config)
```

## Next Steps

Would you like me to:
1. Start with Phase 1 (extract core components)?
2. Create the directory structure and begin migration?
3. Focus on a specific component first?
4. Create a more detailed implementation plan?

The modular approach will make the codebase much more maintainable and allow for easier testing and future enhancements.
