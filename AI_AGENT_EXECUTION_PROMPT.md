# AI Agent Execution Prompt: Parallel Image Generation Implementation

## 🤖 Agent Mission

You are tasked with implementing **parallel image generation** for the anime video generation system to achieve a **60-70% performance improvement** in video creation time. Follow the comprehensive TDD plan provided and execute it autonomously with full PEP 8 compliance.

## 📋 Core Instructions

### **Primary Objective**
Transform the existing sequential image generation to parallel processing using AnyIO structured concurrency, while maintaining system reliability and adding comprehensive documentation.

### **Execution Framework**
- **Methodology**: Test-Driven Development (RED-GREEN-REFACTOR cycle)
- **Standards**: Full PEP 8 compliance for all code
- **Documentation**: Update README.md with comprehensive parallel image generation section
- **Workspace**: `/Users/kkougl/Desktop/Personal/htmlParser/`

### **Implementation Plan Location**
Follow the detailed plan in: `docs/PARALLEL_IMAGE_GENERATION_TDD_PLAN.md`

## 🎯 Key Requirements

### **Technical Requirements**
1. **Performance**: Achieve 60-70% reduction in image generation time
2. **Concurrency**: Use AnyIO with CapacityLimiter for rate limiting
3. **Error Handling**: Comprehensive retry mechanisms with exponential backoff
4. **Memory Efficiency**: Keep additional memory usage under 100MB
5. **Integration**: Seamlessly integrate with existing video generation pipeline

### **Code Quality Requirements**
1. **PEP 8 Compliance**: All code must pass `flake8 --max-line-length=88`
2. **Type Hints**: Complete type annotations for all functions and classes
3. **Docstrings**: Google-style docstrings with Args, Returns, and comprehensive descriptions
4. **Test Coverage**: Achieve 90%+ test coverage using pytest
5. **Import Organization**: Use isort for proper import sorting

### **Documentation Requirements**
1. **README Update**: Add comprehensive parallel image generation section
2. **Usage Examples**: Include working code examples
3. **Performance Metrics**: Document speed improvements and benchmarks  
4. **CLI Documentation**: Update command reference with new capabilities
5. **Development Guide**: Add testing and development workflow instructions

## 🔄 Execution Phases

Execute the following phases **in order**, verifying each phase before proceeding:

### **Phase 1: Foundation & Infrastructure**
- Install dependencies: `anyio pytest pytest-asyncio pytest-cov psutil`
- Create test directory structure
- Implement basic ParallelImageGenerator class
- Establish rate limiting with AnyIO CapacityLimiter

### **Phase 2: Core Generation Logic** 
- Implement concurrent image generation
- Add comprehensive error handling
- Create retry mechanisms with exponential backoff
- Integrate with existing AI client

### **Phase 3: Integration Testing**
- Test system integration with existing workflow
- Perform performance benchmarking
- Validate memory usage requirements
- Test failure scenarios and recovery

### **Phase 4: Error Handling & Edge Cases**
- Implement comprehensive error scenarios
- Add network timeout handling
- Create partial failure recovery mechanisms
- Test API rate limiting scenarios

### **Phase 5: Monitoring & Observability**
- Add performance metrics collection
- Implement real-time monitoring
- Create alerting system for high error rates
- Add resource usage tracking

### **Phase 6: Production Integration**
- Update configuration management
- Integrate with workflow orchestrator
- **UPDATE README.md** with comprehensive documentation
- Prepare deployment configurations

## ✅ Execution Guidelines

### **For Each Task:**
1. **RED Phase**: Write failing tests first
2. **GREEN Phase**: Implement minimal code to pass tests
3. **REFACTOR Phase**: Improve code quality while maintaining tests
4. **VERIFY**: Run validation commands and check success criteria
5. **DOCUMENT**: Update docstrings and comments as needed

### **Validation Commands to Run:**
```bash
# Test execution
pytest tests/test_parallel_image_generation.py -v

# PEP 8 compliance
flake8 agents/parallel_image_generator.py --max-line-length=88
black --check agents/parallel_image_generator.py
isort --check-only agents/parallel_image_generator.py
mypy agents/parallel_image_generator.py

# Documentation validation
pytest tests/test_documentation.py -v
pydocstyle agents/parallel_image_generator.py
```

### **Critical Success Factors:**
- ✅ **Always follow TDD cycle**: RED → GREEN → REFACTOR
- ✅ **PEP 8 compliance**: All code must pass style checks
- ✅ **Comprehensive testing**: 90%+ coverage required
- ✅ **Performance validation**: Measure actual 60-70% improvement
- ✅ **README updates**: Must include parallel image generation section
- ✅ **Integration compatibility**: Must work with existing system

## 🎯 Final Validation Checklist

Before completing the task, verify **ALL** items below:

### **Core Functionality ✅**
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Performance improvement achieved: 60-70% faster image generation
- [ ] Error rate under 30% in failure scenarios
- [ ] Memory usage increase under 100MB
- [ ] Integration with existing workflow successful

### **Code Quality & Standards ✅**
- [ ] PEP 8 compliance: `flake8 agents/parallel_image_generator.py --max-line-length=88`
- [ ] Code formatting: `black --check agents/parallel_image_generator.py`
- [ ] Import sorting: `isort --check-only agents/parallel_image_generator.py`
- [ ] Type checking: `mypy agents/parallel_image_generator.py`
- [ ] Docstring standards: `pydocstyle agents/parallel_image_generator.py`

### **Documentation & Usability ✅**
- [ ] README.md updated with parallel image generation section
- [ ] Usage examples tested and functional
- [ ] CLI commands documented
- [ ] Performance metrics documented
- [ ] Documentation tests pass: `pytest tests/test_documentation.py -v`

### **Production Readiness ✅**
- [ ] Configuration management implemented
- [ ] Monitoring and alerting functional
- [ ] Error handling comprehensive
- [ ] Resource cleanup proper
- [ ] Deployment documentation complete

## 🚨 Important Notes

### **Failure Handling**
If any phase fails:
1. Check the specific failure handling section in the TDD plan
2. Verify all prerequisites are met
3. Run diagnostic commands provided in the plan
4. Do not proceed to next phase until current phase passes

### **Performance Requirements**
- Target: 60-70% reduction in image generation time
- Measure before and after performance
- Document actual improvements achieved
- Test with realistic workloads (5-10 images per batch)

### **README Update Requirements**
The README.md MUST include:
- Performance improvements section
- Usage examples with working code
- Configuration options
- CLI commands documentation
- Development workflow guide
- Technology stack updates

## 🎬 Success Criteria

**Task is complete when:**
1. All validation checklist items are ✅ checked
2. Performance benchmarks meet 60-70% improvement target  
3. All tests pass with 90%+ coverage
4. README.md contains comprehensive parallel image generation documentation
5. Code passes all PEP 8 compliance checks
6. System integrates seamlessly with existing video generation workflow

---

**Agent Authorization**: You are authorized to create, modify, and test files in the specified workspace. Follow the TDD plan exactly and maintain high code quality standards throughout the implementation.

**Status**: Ready for autonomous AI agent execution ✅
