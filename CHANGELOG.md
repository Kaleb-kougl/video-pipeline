# Changelog

All notable changes to the Anime Video Generator project will be documented in this file.

## [2.1.0] - 2025-08-18

### 🔧 Critical Bug Fixes

#### ChromaDB Array Boolean Evaluation Fixes
- **Fixed**: "The truth value of an array with more than one element is ambiguous" errors
- **Affected Files**: 
  - `agents/character_analysis_agent.py`
  - `scripts/migrate_metadata.py` 
  - `utils/vector_search.py`
  - `agents/quality_agents/metadata_quality_agent.py`
- **Impact**: Character analysis now works correctly without crashing
- **Details**: Replaced direct numpy array boolean evaluation with explicit length and None checks

#### Google AI Client API Updates
- **Fixed**: Updated from deprecated `google-generativeai` to `google-genai` SDK
- **Affected Files**:
  - `media/media_utils.py`
  - `requirements.txt`
  - `README.md`
  - `docs/README_MODULAR.md`
- **Changes**:
  - `genai.Client()` → `genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))`
  - `generate_content()` → `generate_images()` for image generation
  - Updated model names: `imagen-3.0-generate-002`
  - Added proper configuration classes: `GenerateImagesConfig`
- **Impact**: Image and audio generation now work with current Google AI SDK

#### File Path Consistency
- **Fixed**: Consistent path construction between image generation and video creation
- **Impact**: Videos now properly find generated images, preventing missing file errors

#### Season Analysis Retrieval
- **Fixed**: Season episode data retrieval works without array errors
- **Impact**: Season summary creation now completes successfully

### 📦 Dependencies Updated

#### New Dependencies Added
- `opencv-python>=4.8.0` - Required for Phase 2 visual coherence features
- `psutil>=5.8.0` - Required for Phase 2 adaptive quality management
- `google-genai>=0.8.0` - New unified Google AI SDK

#### Dependencies Removed
- `google-generativeai==0.8.5` - Deprecated, replaced by google-genai

### 🧪 Testing Infrastructure

#### New Regression Test Suite
- **Added**: Comprehensive regression test suite (`tests/test_regression_suite.py`)
- **Coverage**:
  - ChromaDB array boolean evaluation fixes (`tests/test_chromadb_array_fixes.py`)
  - Google AI client initialization fixes (`tests/test_google_ai_client_fixes.py`)
  - File path consistency validation (`tests/test_file_path_consistency.py`)
  - Character season analysis validation (`tests/test_character_season_analysis.py`)
- **Documentation**: Complete test documentation (`REGRESSION_TESTS.md`)

### 🎯 Phase 2 Validation
- **Confirmed**: All Phase 2 features working correctly with fixes
- **Components Validated**:
  - Visual Coherence Manager
  - Adaptive Quality Manager  
  - Intelligent Format Adapter
  - Episode Character Enhancer
- **Integration**: Full workflow orchestrator integration confirmed

### 📝 Documentation Updates
- **Updated**: README.md with correct Google AI SDK usage
- **Updated**: requirements.txt with new dependencies
- **Updated**: docs/README_MODULAR.md with current dependency information
- **Added**: REGRESSION_TESTS.md comprehensive testing guide

### ✅ Validation Results
- **End-to-End Testing**: ✅ PASSED
- **Phase 2 Integration**: ✅ PASSED  
- **Character Analysis**: ✅ WORKING (previously broken)
- **Season Summary Creation**: ✅ FUNCTIONAL
- **Regression Test Suite**: ✅ 100% SUCCESS RATE

---

## Previous Versions

### [2.0.0] - Phase 2 Quality Enhancement
- Added advanced AI-powered quality improvements
- Character analysis integration
- Visual coherence management
- Adaptive quality settings
- Intelligent platform adaptation

### [1.0.0] - Initial Release  
- Basic anime video generation pipeline
- Transcript discovery and processing
- AI content generation
- Video compilation and export
