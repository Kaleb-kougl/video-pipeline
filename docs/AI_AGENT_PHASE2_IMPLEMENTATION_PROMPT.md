# AI Agent Implementation Prompt: Phase 2 Quality Enhancement

## 🎯 Mission

You are tasked with implementing Phase 2 Quality Enhancement features for an anime video generation system. Your goal is to enhance video quality through character analysis integration, visual coherence, adaptive quality settings, and intelligent platform adaptation.

## 📋 Implementation Requirements

### Core Directive
Implement the features outlined in `/Users/kkougl/Desktop/Personal/htmlParser/docs/PHASE2_QUALITY_ENHANCEMENT_PLAN.md` using **Test-Driven Development (TDD)** methodology with strict PEP8 compliance.

### Quality Standards
- **Test Coverage**: Minimum 90% for all new code
- **Code Style**: Strict PEP8 compliance using `black` and `flake8`
- **Performance**: Meet targets specified in VIDEO_CREATION_IMPROVEMENTS.md
- **Memory Usage**: Peak usage <4GB during processing
- **Documentation**: Comprehensive docstrings for all public methods

## 🔄 TDD Methodology (MANDATORY)

For each feature, follow this exact cycle:

### 1. RED Phase (Write Failing Tests)
```bash
# Example workflow for character integration
pytest tests/unit/test_character_integration.py::TestEpisodeCharacterEnhancer::test_character_weight_calculation_accuracy -v
# Should FAIL initially
```

### 2. GREEN Phase (Implement Minimal Code)
```python
# Implement just enough code to make the test pass
# Focus on functionality, not optimization
```

### 3. REFACTOR Phase (Improve Code Quality)
```python
# Optimize performance, improve readability
# Ensure PEP8 compliance
# Add proper error handling
```

### 4. VALIDATE Phase (Integration Testing)
```bash
# Run integration tests
pytest tests/integration/ -v
# Validate with existing system components
```

## 🏗️ Implementation Order (CRITICAL)

### Week 1: Character Analysis Integration

#### Day 1-2: Test Infrastructure
1. **Setup test environment**:
   ```bash
   pip install pytest pytest-asyncio pytest-mock pytest-benchmark coverage black flake8
   mkdir -p tests/{unit,integration,performance,e2e}
   mkdir -p tests/fixtures/{images,videos,character_data}
   ```

2. **Create test fixtures**:
   - Sample episode content
   - Mock character analysis data
   - Test images for consistency validation

#### Day 3-4: Character Integration Tests (RED Phase)
**File**: `tests/unit/test_character_integration.py`

**Required Test Methods**:
- `test_character_weight_calculation_accuracy()`
- `test_timing_adjustment_with_character_weights()`
- `test_prompt_enhancement_with_character_context()`
- `test_full_episode_enhancement_workflow()`

**Acceptance Criteria**:
- All tests must FAIL initially
- Test coverage plan for edge cases
- Mock dependencies properly

#### Day 5-7: Character Integration Implementation (GREEN + REFACTOR)
**File**: `core/character_episode_enhancer.py`

**Required Classes/Methods**:
- `CharacterWeight` dataclass
- `EpisodeCharacterEnhancer` class
- `enhance_episode_with_character_data()` method
- `_calculate_character_weights()` method
- `_adjust_timing_for_characters()` method
- `_enhance_prompt_with_character_context()` method

**Integration Points**:
- Connect with existing `agents/character_analysis_agent.py`
- Hook into `media/media_utils.py` image generation
- Validate with `agents/video_agent.py`

### Week 2: Visual Coherence System

#### Day 8-9: Visual Coherence Tests (RED Phase)
**File**: `tests/unit/test_visual_coherence.py`

**Required Test Methods**:
- `test_style_consistency_validation()`
- `test_character_appearance_consistency()`
- `test_color_palette_coherence()`
- `test_consistency_retry_mechanism()`

#### Day 10-12: Visual Coherence Implementation (GREEN + REFACTOR)
**File**: `core/visual_coherence_manager.py`

**Required Classes/Methods**:
- `VisualConsistencyMetrics` dataclass
- `VisualCoherenceManager` class
- `generate_consistent_image()` method
- `_evaluate_visual_consistency()` method
- `_calculate_color_coherence()` using OpenCV k-means
- `_calculate_style_consistency()` using feature comparison

### Week 3: Adaptive Quality & Platform Adaptation

#### Day 13-14: Quality Settings Tests & Implementation
**Files**: 
- `tests/unit/test_adaptive_quality.py`
- `core/adaptive_quality_manager.py`

#### Day 15-19: Platform Adaptation
**Files**:
- `tests/unit/test_platform_adaptation.py` 
- `core/intelligent_format_adapter.py`

## 📊 Validation Commands (Run After Each Implementation)

### Test Execution
```bash
# Unit tests with coverage
pytest tests/unit/ -v --cov=core --cov-report=html --cov-fail-under=90

# Integration tests  
pytest tests/integration/ -v

# Performance benchmarks
pytest tests/performance/ --benchmark-only

# End-to-end validation
pytest tests/e2e/ -v
```

### Code Quality
```bash
# PEP8 formatting
black core/ tests/ --line-length=88

# Linting
flake8 core/ tests/ --max-line-length=88

# Type checking (if using type hints)
mypy core/ --ignore-missing-imports
```

### System Integration
```bash
# Test with existing components
python -m pytest tests/integration/test_quality_enhancement_integration.py -v

# Validate memory usage
python -c "
from core.adaptive_quality_manager import AdaptiveQualityManager
import psutil
print(f'Memory before: {psutil.Process().memory_info().rss / 1024**2:.1f}MB')
# Run quality enhancement
print(f'Memory after: {psutil.Process().memory_info().rss / 1024**2:.1f}MB')
"
```

## 🎯 Success Criteria Checklist

### Character Analysis Integration ✅
- [ ] Character weights calculated accurately from analysis data
- [ ] Scene timing adjusted based on character importance (±30% adjustment range)
- [ ] Visual prompts enhanced with character appearance consistency
- [ ] Integration with existing `agents/character_analysis_agent.py` works seamlessly
- [ ] Test coverage ≥90%

### Visual Coherence System ✅
- [ ] Visual consistency score >0.8 for generated images
- [ ] Character appearance consistency maintained across scenes
- [ ] Episode color palette coherence preserved
- [ ] Retry mechanism works (max 3 attempts) with progressive prompt enhancement
- [ ] OpenCV-based color analysis functional
- [ ] Test coverage ≥90%

### Adaptive Quality Settings ✅
- [ ] Quality profiles selected correctly based on context
- [ ] System resources monitored accurately using psutil
- [ ] Memory constraints respected (<4GB peak usage)
- [ ] Processing speed adapts to deadline pressure
- [ ] Profile adjustment works for low-resource environments
- [ ] Test coverage ≥90%

### Platform Format Adaptation ✅
- [ ] Content condensation works for TikTok (60s max)
- [ ] YouTube Shorts optimization (informative hooks)
- [ ] Instagram Reels adaptation (aesthetic focus)
- [ ] Engagement prediction provides meaningful scores
- [ ] Multi-platform batch export efficiency validated
- [ ] Test coverage ≥90%

## 🚨 Critical Implementation Notes

### Integration Points
1. **Character Analysis**: Leverage existing `agents/character_analysis_agent.py` with ChromaDB
2. **Image Generation**: Hook into `media/media_utils.py` `create_images()` for consistent generation
3. **Video Assembly**: Enhance `media/media_utils.py` with quality-aware processing
4. **Export Pipeline**: Upgrade `media/format_exporters/` with intelligent adaptation

### Error Handling Requirements
- Graceful degradation when character analysis unavailable
- Fallback quality profiles for resource-constrained environments  
- Retry mechanisms with exponential backoff
- Comprehensive logging for debugging

### Performance Constraints
- Character integration: <500ms per episode
- Visual coherence: <2s per image generation
- Quality adaptation: <100ms for profile selection
- Platform adaptation: <30s for multi-platform export

## 🔍 Validation Workflow

### After Each Feature Implementation:
1. **Run feature-specific tests**: `pytest tests/unit/test_[feature].py -v`
2. **Check integration**: `pytest tests/integration/ -k [feature] -v`
3. **Validate performance**: `pytest tests/performance/ -k [feature] --benchmark-only`
4. **Code quality check**: `black . && flake8 . && mypy core/`

### Final System Validation:
1. **Complete test suite**: `pytest tests/ -v --cov=core --cov-report=html`
2. **Memory profiling**: Use `pytest-memray` for memory usage analysis
3. **Performance benchmarking**: Compare before/after metrics
4. **Integration with existing pipeline**: Test with `main_refactored.py`

## 🎬 Expected Outcomes

Upon successful implementation, the system will deliver:

- **60% improvement** in visual consistency across generated images
- **Character-aware timing** with 25-40% better narrative flow
- **Resource-adaptive quality** reducing memory usage by 50%
- **Platform-optimized content** with predicted 25%+ engagement improvement
- **Comprehensive test coverage** ensuring system reliability and maintainability

## 🚀 Getting Started

1. **Read the implementation plan**: `/Users/kkougl/Desktop/Personal/htmlParser/docs/PHASE2_QUALITY_ENHANCEMENT_PLAN.md`
2. **Examine existing codebase**: Focus on `agents/`, `core/`, `media/` directories
3. **Start with character integration tests**: Begin TDD cycle with failing tests
4. **Follow the 4-week roadmap**: Implement features in specified order
5. **Validate continuously**: Run tests after each significant change

**Remember: Test-first development is mandatory. No implementation without corresponding tests.**
