# AI Agent Implementation Guide: Parallel Image Generation (TDD)

**Document Version:** 2.0 - AI Agent Ready  
**Date:** January 2025  
**Status:** AI Agent Executable Plan  
**Approach:** Test-Driven Development (TDD)  
**Execution Mode:** Autonomous AI Agent Implementation  

## 🤖 AI Agent Instructions

This document provides step-by-step instructions for an AI agent to implement parallel image generation using Test-Driven Development. Each task includes:
- **Prerequisites**: What must exist before starting
- **Action Steps**: Exact commands and code to execute  
- **Verification**: How to confirm success
- **Failure Handling**: What to do if tasks fail

### Agent Execution Rules
1. **Always run tests first** (Red phase) before implementation
2. **Implement minimal code** to pass tests (Green phase)
3. **Refactor only after tests pass** (Refactor phase)
4. **Follow PEP 8 standards** for all code documentation and formatting
5. **Verify each step** before proceeding to the next
6. **Create files in the exact paths** specified
7. **Run validation commands** after each phase
8. **Update documentation** including README when adding new features

## 📋 Implementation Overview

Transform the anime video generation system to use parallel image generation, reducing processing time by 60-70% while maintaining reliability and quality through comprehensive testing.

## ⚡ Quick Start for AI Agent

```bash
# 1. Setup environment
cd /Users/kkougl/Desktop/Personal/htmlParser
pip install anyio pytest pytest-asyncio pytest-cov psutil

# 2. Create directory structure  
mkdir -p tests/unit tests/integration agents

# 3. Execute each phase sequentially
# Follow RED-GREEN-REFACTOR cycle for each task
# Verify each step before proceeding
```

## 🎯 Objectives

- **Performance**: Reduce image generation time by 60-70% through concurrent processing
- **Reliability**: Implement robust error handling and retry mechanisms
- **Rate Limiting**: Respect API rate limits while maximizing throughput
- **Resource Management**: Efficiently manage memory and API connections
- **Maintainability**: Create clean, testable, and extensible code

## 📚 Technology Stack Analysis

Based on Context7 library research, we'll use:

### **Primary Libraries**
- **AnyIO** (`/agronholm/anyio`) - High-level async framework with structured concurrency
- **pytest** (`/pytest-dev/pytest`) - Testing framework with extensive fixture support  
- **pytest-asyncio** (`/pytest-dev/pytest-asyncio`) - Async testing capabilities

### **Key Patterns from Research**
- **Structured Concurrency**: Using `create_task_group()` for managing concurrent tasks
- **Capacity Limiting**: Using `CapacityLimiter` for rate limiting API calls
- **Resource Guards**: Using `ResourceGuard` for exclusive resource access
- **Async Fixtures**: Proper async test setup and teardown

## 🔄 AI Agent Execution Phases

### 🚀 PHASE 1: Foundation Tests & Infrastructure

**Duration**: Complete in sequence  
**Goal**: Establish basic test infrastructure and parallel image generation framework

#### TASK 1.1: Setup Test Infrastructure

**Prerequisites**:
- Workspace exists at `/Users/kkougl/Desktop/Personal/htmlParser/`
- Python environment is activated
- Required packages can be installed

**🔴 RED PHASE - Create Failing Tests**

**Action 1.1.1**: Install required dependencies
```bash
pip install anyio pytest pytest-asyncio pytest-cov psutil
```

**Action 1.1.2**: Create test file structure
```bash
mkdir -p tests/unit
mkdir -p tests/integration  
mkdir -p agents
```

**Action 1.1.3**: Create failing test file
```python
# tests/test_parallel_image_generation.py
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from parallel_image_generator import ParallelImageGenerator, ImageGenerationResult

class TestParallelImageGeneratorInfrastructure:
    """Test basic infrastructure and configuration"""
    
    @pytest.fixture
    async def mock_ai_client(self):
        """Mock AI client for testing"""
        client = AsyncMock()
        client.generate_image.return_value = Mock(
            candidates=[Mock(content=Mock(parts=[Mock(inline_data=Mock(data=b"fake_image"))]))]
        )
        return client
    
    @pytest.fixture
    def image_generator(self, mock_ai_client):
        """Fixture providing ParallelImageGenerator instance"""
        return ParallelImageGenerator(
            ai_client=mock_ai_client,
            max_concurrent=3,
            rate_limit_delay=0.1
        )
    
    def test_parallel_generator_initialization(self, image_generator):
        """Test that ParallelImageGenerator initializes correctly"""
        assert image_generator.max_concurrent == 3
        assert image_generator.rate_limit_delay == 0.1
        assert image_generator.ai_client is not None
    
    @pytest.mark.asyncio
    async def test_single_image_generation_fails_initially(self, image_generator):
        """Test single image generation (should fail initially)"""
        with pytest.raises(AttributeError):
            await image_generator.generate_single_image(
                "test prompt", "test_show", "1", "1", 0
            )
```

**Verification 1.1.3**: Run tests to confirm they fail
```bash
cd /Users/kkougl/Desktop/Personal/htmlParser
pytest tests/test_parallel_image_generation.py -v
```

**Expected Result**: Tests should FAIL with import errors or AttributeError

**🟢 GREEN PHASE - Implement Minimal Code**

**Action 1.1.4**: Create minimal ParallelImageGenerator
```python
# agents/parallel_image_generator.py
import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class ImageGenerationResult:
    """Result of an image generation operation.
    
    Attributes:
        success: Whether the image generation succeeded.
        image_path: Path to the generated image file, if successful.
        prompt: The original prompt used for generation.
        index: Index of this image in the batch.
        error: Error message if generation failed.
        generation_time: Time taken to generate the image in seconds.
    """
    success: bool
    image_path: Optional[str] = None
    prompt: Optional[str] = None
    index: Optional[int] = None
    error: Optional[str] = None
    generation_time: Optional[float] = None


class ParallelImageGenerator:
    """Parallel image generation with rate limiting and error handling.
    
    This class provides concurrent image generation capabilities using AnyIO
    for structured concurrency. It includes rate limiting to respect API
    limits and comprehensive error handling with retry mechanisms.
    
    Attributes:
        ai_client: The AI client for image generation API calls.
        max_concurrent: Maximum number of concurrent image generation tasks.
        rate_limit_delay: Delay between API calls in seconds.
    """
    
    def __init__(self, ai_client, max_concurrent: int = 3, 
                 rate_limit_delay: float = 0.5) -> None:
        """Initialize the parallel image generator.
        
        Args:
            ai_client: Client for AI image generation API.
            max_concurrent: Maximum concurrent tasks (default: 3).
            rate_limit_delay: Delay between API calls in seconds (default: 0.5).
        """
        self.ai_client = ai_client
        self.max_concurrent = max_concurrent
        self.rate_limit_delay = rate_limit_delay
        
    async def generate_single_image(self, prompt: str, show: str, season: str, 
                                  episode: str, index: int) -> ImageGenerationResult:
        """Generate a single image with comprehensive error handling.
        
        Args:
            prompt: Text prompt for image generation.
            show: Name of the show for file organization.
            season: Season number for file organization.
            episode: Episode number for file organization.
            index: Index of this image in the batch.
            
        Returns:
            ImageGenerationResult containing success status and metadata.
        """
        # Basic implementation to pass initial test
        raise NotImplementedError("Implementation pending")
```

**Verification 1.1.4**: Run tests to confirm basic structure passes
```bash
pytest tests/test_parallel_image_generation.py::TestParallelImageGeneratorInfrastructure::test_parallel_generator_initialization -v
```

**Expected Result**: Initialization test should PASS

**🔵 REFACTOR PHASE - Improve Code Quality**

**Action 1.1.5**: Add proper error handling and logging

**Verification 1.1.5**: Run all infrastructure tests
```bash
pytest tests/test_parallel_image_generation.py::TestParallelImageGeneratorInfrastructure -v
```

**Success Criteria for Task 1.1**:
- [ ] All dependencies installed without errors
- [ ] Test directory structure created
- [ ] Basic test infrastructure passes
- [ ] Tests follow TDD Red-Green-Refactor cycle

**Failure Handling**: If any verification step fails:
1. Check Python environment is activated
2. Verify all file paths are correct
3. Check for import conflicts
4. Run `pip list` to confirm dependencies

---

#### TASK 1.2: Implement Rate Limiting

**Prerequisites**:
- Task 1.1 completed successfully
- AnyIO installed and importable

**🔴 RED PHASE - Create Rate Limiting Tests**

**Action 1.2.1**: Add rate limiting test class

#### 1.2 Rate Limiting Tests

**Red Phase**: Write failing tests for rate limiting
```python
class TestRateLimiting:
    """Test rate limiting functionality"""
    
    @pytest.mark.asyncio
    async def test_rate_limiting_with_capacity_limiter(self, image_generator):
        """Test that rate limiting works correctly"""
        start_time = asyncio.get_event_loop().time()
        
        # Generate 5 images with max_concurrent=3
        prompts = [f"test prompt {i}" for i in range(5)]
        results = await image_generator.generate_images_parallel(
            prompts, "test_show", "1", "1"
        )
        
        end_time = asyncio.get_event_loop().time()
        
        # Should take at least rate_limit_delay * ceil(5/3) time
        min_expected_time = image_generator.rate_limit_delay * 2  # 2 batches
        assert (end_time - start_time) >= min_expected_time
        assert len(results) == 5
    
    @pytest.mark.asyncio
    async def test_concurrent_limit_enforcement(self, image_generator):
        """Test that concurrent limit is enforced"""
        # Track concurrent executions
        concurrent_count = 0
        max_concurrent_seen = 0
        
        async def mock_generate_with_tracking(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent_seen
            concurrent_count += 1
            max_concurrent_seen = max(max_concurrent_seen, concurrent_count)
            await asyncio.sleep(0.1)  # Simulate work
            concurrent_count -= 1
            return Mock(candidates=[Mock(content=Mock(parts=[Mock(inline_data=Mock(data=b"fake"))]))])
        
        image_generator.ai_client.generate_content = mock_generate_with_tracking
        
        prompts = [f"prompt {i}" for i in range(6)]
        await image_generator.generate_images_parallel(prompts, "show", "1", "1")
        
        assert max_concurrent_seen <= image_generator.max_concurrent
```

**Green Phase**: Implement rate limiting using AnyIO
```python
# agents/parallel_image_generator.py (updated)
from anyio import create_task_group, CapacityLimiter, sleep
import time

class ParallelImageGenerator:
    def __init__(self, ai_client, max_concurrent: int = 3, rate_limit_delay: float = 0.5):
        self.ai_client = ai_client
        self.max_concurrent = max_concurrent
        self.rate_limit_delay = rate_limit_delay
        self.capacity_limiter = CapacityLimiter(max_concurrent)
        
    async def generate_images_parallel(self, prompts: List[str], show: str, 
                                     season: str, episode: str) -> List[ImageGenerationResult]:
        """Generate multiple images in parallel with rate limiting"""
        results = []
        
        async with create_task_group() as tg:
            for index, prompt in enumerate(prompts):
                tg.start_soon(
                    self._generate_single_with_limiter,
                    prompt, show, season, episode, index, results
                )
        
        return results
    
    async def _generate_single_with_limiter(self, prompt: str, show: str, season: str,
                                          episode: str, index: int, results: List):
        """Generate single image with capacity limiting"""
        async with self.capacity_limiter:
            await sleep(self.rate_limit_delay)  # Rate limiting
            result = await self.generate_single_image(prompt, show, season, episode, index)
            results.append(result)
```

### Phase 2: Core Image Generation Logic (Week 1-2)

#### 2.1 Image Generation Implementation Tests

**Red Phase**: Write comprehensive image generation tests
```python
class TestImageGeneration:
    """Test core image generation functionality"""
    
    @pytest.mark.asyncio
    async def test_successful_image_generation(self, image_generator, tmp_path, monkeypatch):
        """Test successful image generation flow"""
        # Mock file system operations
        monkeypatch.setattr("os.makedirs", Mock())
        mock_image = Mock()
        mock_image.save = Mock()
        monkeypatch.setattr("PIL.Image.open", Mock(return_value=mock_image))
        
        result = await image_generator.generate_single_image(
            "test prompt", "test_show", "1", "1", 0
        )
        
        assert result.success is True
        assert result.image_path is not None
        assert result.prompt == "test prompt"
        assert result.index == 0
        assert result.error is None
        assert result.generation_time > 0
    
    @pytest.mark.asyncio
    async def test_image_generation_api_failure(self, image_generator):
        """Test handling of API failures"""
        # Mock API failure
        image_generator.ai_client.models.generate_content.side_effect = Exception("API Error")
        
        result = await image_generator.generate_single_image(
            "test prompt", "test_show", "1", "1", 0
        )
        
        assert result.success is False
        assert result.error is not None
        assert "API Error" in result.error
        assert result.image_path is None
    
    @pytest.mark.asyncio
    async def test_image_generation_with_retry(self, image_generator):
        """Test retry mechanism on failures"""
        call_count = 0
        
        def failing_then_success(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return Mock(candidates=[Mock(content=Mock(parts=[Mock(inline_data=Mock(data=b"success"))]))])
        
        image_generator.ai_client.models.generate_content = failing_then_success
        image_generator.max_retries = 3
        
        result = await image_generator.generate_single_image(
            "test prompt", "test_show", "1", "1", 0
        )
        
        assert result.success is True
        assert call_count == 3  # Failed twice, succeeded on third try
```

**Green Phase**: Implement core image generation with error handling
```python
# agents/parallel_image_generator.py (updated)
import google.generativeai as genai
from google.generativeai import types
from PIL import Image
from io import BytesIO
import os

class ParallelImageGenerator:
    def __init__(self, ai_client, max_concurrent: int = 3, rate_limit_delay: float = 0.5, 
                 max_retries: int = 3):
        self.ai_client = ai_client
        self.max_concurrent = max_concurrent
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.capacity_limiter = CapacityLimiter(max_concurrent)
    
    async def generate_single_image(self, prompt: str, show: str, season: str,
                                  episode: str, index: int) -> ImageGenerationResult:
        """Generate a single image with retry logic"""
        start_time = time.time()
        
        for attempt in range(self.max_retries):
            try:
                # Enhance prompt with style consistency
                enhanced_prompt = self._enhance_prompt_for_consistency(prompt, show)
                
                # Generate image using Gemini
                response = self.ai_client.models.generate_content(
                    model="gemini-2.0-flash-preview-image-generation",
                    contents=enhanced_prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=['TEXT', 'IMAGE']
                    )
                )
                
                # Process and save image
                image_path = await self._process_and_save_image(
                    response, show, season, episode, index
                )
                
                generation_time = time.time() - start_time
                return ImageGenerationResult(
                    success=True,
                    image_path=image_path,
                    prompt=prompt,
                    index=index,
                    generation_time=generation_time
                )
                
            except Exception as e:
                logger.warning(f"Image generation attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    return ImageGenerationResult(
                        success=False,
                        prompt=prompt,
                        index=index,
                        error=str(e),
                        generation_time=time.time() - start_time
                    )
                await sleep(0.5 * (attempt + 1))  # Exponential backoff
    
    def _enhance_prompt_for_consistency(self, prompt: str, show: str) -> str:
        """Enhance prompt for visual consistency"""
        style_prompt = f"""
        Create images in a consistent anime art style for {show}.
        Maintain character designs and color palette consistency.
        
        Scene: {prompt}
        
        Style requirements:
        - Consistent anime art style throughout
        - Cohesive color palette
        - Professional animation quality
        """
        return style_prompt.strip()
    
    async def _process_and_save_image(self, response, show: str, season: str,
                                    episode: str, index: int) -> str:
        """Process API response and save image"""
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image = Image.open(BytesIO(part.inline_data.data))
                
                # Create directory structure
                dir_path = f"{show}/Season{season}/Episode{episode}"
                os.makedirs(dir_path, exist_ok=True)
                
                # Save image
                image_path = f"{dir_path}/{show}_{episode}_{index}.png"
                image.save(image_path)
                
                return image_path
        
        raise ValueError("No image data in API response")
```

### Phase 3: Integration & Performance Tests (Week 2)

#### 3.1 Integration with Existing System

**Red Phase**: Write integration tests
```python
class TestSystemIntegration:
    """Test integration with existing video generation system"""
    
    @pytest.fixture
    def mock_video_generator(self):
        """Mock existing video generator components"""
        from unittest.mock import Mock
        generator = Mock()
        generator.process_episode_by_numbers = Mock(return_value=Mock(success=True))
        return generator
    
    @pytest.mark.asyncio
    async def test_integration_with_media_utils(self, image_generator, tmp_path):
        """Test integration with existing media_utils.py"""
        from media.media_utils import create_images
        
        # Mock the original create_images to use our parallel version
        sentences = ["Scene 1", "Scene 2", "Scene 3"]
        
        # This should eventually replace the sequential version
        results = await image_generator.generate_images_parallel(
            sentences, "test_show", "1", "1"
        )
        
        assert len(results) == len(sentences)
        assert all(result.success for result in results)
    
    @pytest.mark.asyncio
    async def test_performance_improvement(self, image_generator):
        """Test that parallel generation is faster than sequential"""
        sentences = [f"Test scene {i}" for i in range(6)]
        
        # Time parallel generation
        start_parallel = time.time()
        parallel_results = await image_generator.generate_images_parallel(
            sentences, "test_show", "1", "1"
        )
        parallel_time = time.time() - start_parallel
        
        # Time sequential generation (simulated)
        start_sequential = time.time()
        sequential_results = []
        for i, sentence in enumerate(sentences):
            result = await image_generator.generate_single_image(
                sentence, "test_show", "1", "1", i
            )
            sequential_results.append(result)
        sequential_time = time.time() - start_sequential
        
        # Parallel should be significantly faster
        improvement_ratio = sequential_time / parallel_time
        assert improvement_ratio > 1.5  # At least 50% improvement
        assert len(parallel_results) == len(sequential_results)
```

**Green Phase**: Implement integration adapter
```python
# agents/parallel_image_adapter.py
"""Adapter to integrate parallel image generation with existing system"""

from typing import List
from agents.parallel_image_generator import ParallelImageGenerator
import google.generativeai as genai

class ParallelImageAdapter:
    """Adapter for integrating parallel image generation"""
    
    def __init__(self, max_concurrent: int = 3, rate_limit_delay: float = 0.5):
        self.ai_client = genai.Client()
        self.generator = ParallelImageGenerator(
            ai_client=self.ai_client,
            max_concurrent=max_concurrent,
            rate_limit_delay=rate_limit_delay
        )
    
    async def create_images_parallel(self, sentences: List[str], episode: str,
                                   season: str, show: str) -> None:
        """Drop-in replacement for media_utils.create_images"""
        results = await self.generator.generate_images_parallel(
            sentences, show, season, episode
        )
        
        # Log results for monitoring
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        if failed > 0:
            logger.warning(f"Image generation: {successful} successful, {failed} failed")
        else:
            logger.info(f"Successfully generated {successful} images in parallel")
        
        # Raise exception if too many failures
        failure_rate = failed / len(results) if results else 0
        if failure_rate > 0.3:  # More than 30% failures
            raise RuntimeError(f"High failure rate in image generation: {failure_rate:.1%}")
```

#### 3.2 Performance and Load Testing

**Red Phase**: Write performance tests
```python
class TestPerformance:
    """Test performance characteristics and scalability"""
    
    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, image_generator):
        """Test memory usage doesn't grow excessively"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Generate many images
        large_batch = [f"Scene {i}" for i in range(20)]
        results = await image_generator.generate_images_parallel(
            large_batch, "test_show", "1", "1"
        )
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB)
        assert memory_increase < 100 * 1024 * 1024  # 100MB
        assert len(results) == 20
    
    @pytest.mark.asyncio
    async def test_concurrent_batches(self, image_generator):
        """Test handling multiple concurrent batches"""
        batch1 = [f"Batch1 Scene {i}" for i in range(5)]
        batch2 = [f"Batch2 Scene {i}" for i in range(5)]
        batch3 = [f"Batch3 Scene {i}" for i in range(5)]
        
        # Run multiple batches concurrently
        async with create_task_group() as tg:
            results1, results2, results3 = [], [], []
            tg.start_soon(self._run_batch, image_generator, batch1, results1)
            tg.start_soon(self._run_batch, image_generator, batch2, results2)
            tg.start_soon(self._run_batch, image_generator, batch3, results3)
        
        assert len(results1) == 5
        assert len(results2) == 5
        assert len(results3) == 5
        assert all(r.success for r in results1 + results2 + results3)
    
    async def _run_batch(self, generator, batch, results):
        """Helper to run batch and store results"""
        batch_results = await generator.generate_images_parallel(
            batch, "test_show", "1", "1"
        )
        results.extend(batch_results)
```

### Phase 4: Error Handling & Edge Cases (Week 3)

#### 4.1 Comprehensive Error Handling Tests

**Red Phase**: Write error scenario tests
```python
class TestErrorHandling:
    """Test error handling and recovery scenarios"""
    
    @pytest.mark.asyncio
    async def test_api_rate_limit_handling(self, image_generator):
        """Test handling of API rate limit errors"""
        def rate_limited_response(*args, **kwargs):
            from google.api_core.exceptions import ResourceExhausted
            raise ResourceExhausted("Quota exceeded")
        
        image_generator.ai_client.models.generate_content = rate_limited_response
        
        results = await image_generator.generate_images_parallel(
            ["test prompt"], "test_show", "1", "1"
        )
        
        assert len(results) == 1
        assert results[0].success is False
        assert "Quota exceeded" in results[0].error
    
    @pytest.mark.asyncio
    async def test_partial_batch_failure(self, image_generator):
        """Test handling when some images fail but others succeed"""
        call_count = 0
        
        def intermittent_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:  # Fail every second call
                raise Exception("Intermittent failure")
            return Mock(candidates=[Mock(content=Mock(parts=[Mock(inline_data=Mock(data=b"success"))]))])
        
        image_generator.ai_client.models.generate_content = intermittent_failure
        image_generator.max_retries = 1  # Limit retries for faster test
        
        prompts = [f"prompt {i}" for i in range(4)]
        results = await image_generator.generate_images_parallel(
            prompts, "test_show", "1", "1"
        )
        
        assert len(results) == 4
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        assert len(successful) == 2
        assert len(failed) == 2
    
    @pytest.mark.asyncio
    async def test_disk_space_error(self, image_generator, monkeypatch):
        """Test handling of disk space errors"""
        def mock_save_with_disk_error(*args, **kwargs):
            raise OSError("No space left on device")
        
        # Mock Image.save to raise disk error
        mock_image = Mock()
        mock_image.save = mock_save_with_disk_error
        monkeypatch.setattr("PIL.Image.open", Mock(return_value=mock_image))
        
        result = await image_generator.generate_single_image(
            "test prompt", "test_show", "1", "1", 0
        )
        
        assert result.success is False
        assert "No space left on device" in result.error
    
    @pytest.mark.asyncio
    async def test_network_timeout_handling(self, image_generator):
        """Test handling of network timeouts"""
        async def timeout_response(*args, **kwargs):
            await asyncio.sleep(10)  # Simulate very slow response
        
        image_generator.ai_client.models.generate_content = timeout_response
        image_generator.request_timeout = 1.0  # 1 second timeout
        
        result = await image_generator.generate_single_image(
            "test prompt", "test_show", "1", "1", 0
        )
        
        assert result.success is False
        assert "timeout" in result.error.lower()
```

**Green Phase**: Implement robust error handling
```python
# agents/parallel_image_generator.py (updated with error handling)
import asyncio
from anyio import fail_after
from google.api_core.exceptions import ResourceExhausted, DeadlineExceeded

class ParallelImageGenerator:
    def __init__(self, ai_client, max_concurrent: int = 3, rate_limit_delay: float = 0.5,
                 max_retries: int = 3, request_timeout: float = 30.0):
        self.ai_client = ai_client
        self.max_concurrent = max_concurrent
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.request_timeout = request_timeout
        self.capacity_limiter = CapacityLimiter(max_concurrent)
    
    async def generate_single_image(self, prompt: str, show: str, season: str,
                                  episode: str, index: int) -> ImageGenerationResult:
        """Generate a single image with comprehensive error handling"""
        start_time = time.time()
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                enhanced_prompt = self._enhance_prompt_for_consistency(prompt, show)
                
                # Use timeout for API call
                with fail_after(self.request_timeout):
                    response = self.ai_client.models.generate_content(
                        model="gemini-2.0-flash-preview-image-generation",
                        contents=enhanced_prompt,
                        config=types.GenerateContentConfig(
                            response_modalities=['TEXT', 'IMAGE']
                        )
                    )
                
                image_path = await self._process_and_save_image(
                    response, show, season, episode, index
                )
                
                generation_time = time.time() - start_time
                return ImageGenerationResult(
                    success=True,
                    image_path=image_path,
                    prompt=prompt,
                    index=index,
                    generation_time=generation_time
                )
                
            except ResourceExhausted as e:
                # Rate limiting - longer wait before retry
                last_error = f"Rate limit exceeded: {e}"
                logger.warning(f"Rate limit hit on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    await sleep(2.0 ** attempt)  # Exponential backoff
                    
            except (DeadlineExceeded, asyncio.TimeoutError) as e:
                # Timeout errors
                last_error = f"Request timeout: {e}"
                logger.warning(f"Timeout on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    await sleep(1.0)
                    
            except OSError as e:
                # Disk/file system errors - don't retry
                last_error = f"File system error: {e}"
                logger.error(f"File system error: {e}")
                break
                
            except Exception as e:
                # Generic errors
                last_error = f"Generation failed: {e}"
                logger.warning(f"Image generation attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await sleep(0.5 * (attempt + 1))
        
        # All attempts failed
        return ImageGenerationResult(
            success=False,
            prompt=prompt,
            index=index,
            error=last_error,
            generation_time=time.time() - start_time
        )
```

### Phase 5: Monitoring & Observability (Week 3)

#### 5.1 Performance Monitoring Tests

**Red Phase**: Write monitoring tests
```python
class TestMonitoring:
    """Test monitoring and observability features"""
    
    @pytest.mark.asyncio
    async def test_performance_metrics_collection(self, image_generator):
        """Test that performance metrics are collected correctly"""
        prompts = [f"Scene {i}" for i in range(5)]
        
        results = await image_generator.generate_images_parallel(
            prompts, "test_show", "1", "1"
        )
        
        metrics = image_generator.get_performance_metrics()
        
        assert 'total_requests' in metrics
        assert 'successful_requests' in metrics
        assert 'failed_requests' in metrics
        assert 'average_generation_time' in metrics
        assert 'concurrent_batches_processed' in metrics
        
        assert metrics['total_requests'] == 5
        assert metrics['successful_requests'] + metrics['failed_requests'] == 5
    
    @pytest.mark.asyncio
    async def test_error_rate_tracking(self, image_generator):
        """Test error rate tracking and alerting"""
        # Mock high failure rate
        image_generator.ai_client.models.generate_content.side_effect = Exception("Simulated failure")
        
        prompts = [f"Scene {i}" for i in range(10)]
        results = await image_generator.generate_images_parallel(
            prompts, "test_show", "1", "1"
        )
        
        metrics = image_generator.get_performance_metrics()
        error_rate = metrics['failed_requests'] / metrics['total_requests']
        
        assert error_rate == 1.0  # 100% failure rate
        
        # Should trigger alert for high error rate
        alerts = image_generator.get_active_alerts()
        assert any("high_error_rate" in alert['type'] for alert in alerts)
    
    def test_resource_usage_monitoring(self, image_generator):
        """Test resource usage monitoring"""
        import psutil
        
        # Monitor resource usage
        initial_stats = image_generator.get_resource_stats()
        
        assert 'cpu_percent' in initial_stats
        assert 'memory_usage_mb' in initial_stats
        assert 'open_connections' in initial_stats
        assert initial_stats['memory_usage_mb'] > 0
```

**Green Phase**: Implement monitoring and metrics
```python
# agents/parallel_image_generator.py (add monitoring)
import psutil
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta

class ParallelImageGenerator:
    def __init__(self, ai_client, max_concurrent: int = 3, rate_limit_delay: float = 0.5,
                 max_retries: int = 3, request_timeout: float = 30.0):
        # ... existing initialization ...
        
        # Monitoring
        self.metrics = defaultdict(int)
        self.generation_times = deque(maxlen=100)  # Keep last 100 times
        self.alerts = []
        self.start_time = datetime.now()
        self._lock = threading.Lock()
    
    def _record_metrics(self, result: ImageGenerationResult):
        """Record metrics for monitoring"""
        with self._lock:
            self.metrics['total_requests'] += 1
            
            if result.success:
                self.metrics['successful_requests'] += 1
            else:
                self.metrics['failed_requests'] += 1
            
            if result.generation_time:
                self.generation_times.append(result.generation_time)
            
            # Check for alerts
            self._check_alert_conditions()
    
    def _check_alert_conditions(self):
        """Check for alert conditions"""
        total = self.metrics['total_requests']
        if total < 10:  # Need minimum samples
            return
        
        failed = self.metrics['failed_requests']
        error_rate = failed / total
        
        # Alert on high error rate
        if error_rate > 0.3:  # More than 30% failures
            alert = {
                'type': 'high_error_rate',
                'message': f'Error rate is {error_rate:.1%}',
                'timestamp': datetime.now(),
                'severity': 'high' if error_rate > 0.5 else 'medium'
            }
            self.alerts.append(alert)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        with self._lock:
            metrics = dict(self.metrics)
            
            if self.generation_times:
                metrics['average_generation_time'] = sum(self.generation_times) / len(self.generation_times)
                metrics['max_generation_time'] = max(self.generation_times)
                metrics['min_generation_time'] = min(self.generation_times)
            
            metrics['uptime_seconds'] = (datetime.now() - self.start_time).total_seconds()
            
            return metrics
    
    def get_resource_stats(self) -> Dict[str, Any]:
        """Get current resource usage statistics"""
        process = psutil.Process()
        
        return {
            'cpu_percent': process.cpu_percent(),
            'memory_usage_mb': process.memory_info().rss / 1024 / 1024,
            'open_connections': len(process.connections()),
            'threads': process.num_threads()
        }
    
    def get_active_alerts(self) -> List[Dict]:
        """Get active alerts"""
        # Return alerts from last hour
        cutoff = datetime.now() - timedelta(hours=1)
        return [alert for alert in self.alerts if alert['timestamp'] > cutoff]
    
    async def generate_images_parallel(self, prompts: List[str], show: str,
                                     season: str, episode: str) -> List[ImageGenerationResult]:
        """Generate multiple images in parallel with metrics collection"""
        results = []
        
        async with create_task_group() as tg:
            for index, prompt in enumerate(prompts):
                tg.start_soon(
                    self._generate_with_metrics,
                    prompt, show, season, episode, index, results
                )
        
        return results
    
    async def _generate_with_metrics(self, prompt: str, show: str, season: str,
                                   episode: str, index: int, results: List):
        """Generate image with metrics collection"""
        async with self.capacity_limiter:
            await sleep(self.rate_limit_delay)
            result = await self.generate_single_image(prompt, show, season, episode, index)
            
            # Record metrics
            self._record_metrics(result)
            results.append(result)
```

### Phase 6: Integration & Production Readiness (Week 4)

#### 6.1 Production Integration Tests

**Red Phase**: Write production readiness tests
```python
class TestProductionIntegration:
    """Test production readiness and system integration"""
    
    @pytest.mark.asyncio
    async def test_replacement_of_sequential_create_images(self, image_generator, monkeypatch):
        """Test that parallel version can replace sequential create_images"""
        from media.media_utils import create_images
        from agents.parallel_image_adapter import ParallelImageAdapter
        
        adapter = ParallelImageAdapter(max_concurrent=2, rate_limit_delay=0.1)
        
        # Mock the original function to use our parallel version
        async def mock_create_images(sentences, episode, season, show):
            await adapter.create_images_parallel(sentences, episode, season, show)
        
        monkeypatch.setattr("media.media_utils.create_images", mock_create_images)
        
        # Test with realistic data
        sentences = [
            "Deku training with All Might in the beach",
            "Class 1-A students in their hero costumes",
            "Villains attacking the USJ facility"
        ]
        
        # Should complete without errors
        await create_images(sentences, "4", "1", "My Hero Academia")
    
    @pytest.mark.asyncio
    async def test_main_workflow_integration(self, image_generator):
        """Test integration with main workflow orchestrator"""
        from agents.workflow_orchestrator import WorkflowOrchestrator
        
        # Mock workflow orchestrator to use parallel image generation
        orchestrator = WorkflowOrchestrator()
        
        # This should work with existing workflow
        episode_data = {
            'show_name': 'My Hero Academia',
            'season': 1,
            'episode': 4,
            'content': {
                'scenes': [
                    {'description': 'Opening scene'},
                    {'description': 'Character development'},
                    {'description': 'Climactic battle'}
                ]
            }
        }
        
        # Should integrate smoothly with existing workflow
        result = await orchestrator.process_with_parallel_images(episode_data, image_generator)
        assert result.success is True
        
    def test_configuration_management(self, image_generator):
        """Test configuration management for production"""
        from config.settings import get_settings
        
        settings = get_settings()
        
        # Should read configuration from settings
        production_generator = ParallelImageGenerator(
            ai_client=Mock(),
            max_concurrent=settings.parallel_image_max_concurrent,
            rate_limit_delay=settings.parallel_image_rate_limit_delay,
            max_retries=settings.parallel_image_max_retries
        )
        
        assert production_generator.max_concurrent > 0
        assert production_generator.rate_limit_delay > 0
        assert production_generator.max_retries > 0
```

**Green Phase**: Implement production configuration
```python
# config/settings.py (add parallel image settings)
class Settings:
    # ... existing settings ...
    
    # Parallel Image Generation Settings
    parallel_image_max_concurrent: int = 3
    parallel_image_rate_limit_delay: float = 0.5
    parallel_image_max_retries: int = 3
    parallel_image_request_timeout: float = 30.0
    parallel_image_enable_monitoring: bool = True

# agents/workflow_orchestrator.py (update for parallel images)
class WorkflowOrchestrator:
    def __init__(self):
        # ... existing initialization ...
        
        # Initialize parallel image generator
        settings = get_settings()
        ai_client = genai.Client()
        
        self.parallel_image_generator = ParallelImageGenerator(
            ai_client=ai_client,
            max_concurrent=settings.parallel_image_max_concurrent,
            rate_limit_delay=settings.parallel_image_rate_limit_delay,
            max_retries=settings.parallel_image_max_retries,
            request_timeout=settings.parallel_image_request_timeout
        )
    
    async def process_with_parallel_images(self, episode_data: Dict, 
                                         image_generator: ParallelImageGenerator) -> ProcessingResult:
        """Process episode using parallel image generation"""
        try:
            scenes = episode_data['content']['scenes']
            prompts = [scene['description'] for scene in scenes]
            
            # Generate images in parallel
            image_results = await image_generator.generate_images_parallel(
                prompts, 
                episode_data['show_name'],
                str(episode_data['season']),
                str(episode_data['episode'])
            )
            
            # Check for failures
            failed_images = [r for r in image_results if not r.success]
            if len(failed_images) > len(image_results) * 0.3:  # More than 30% failed
                return ProcessingResult(
                    success=False,
                    error=f"Too many image generation failures: {len(failed_images)}/{len(image_results)}"
                )
            
            return ProcessingResult(
                success=True,
                data={
                    'image_results': image_results,
                    'metrics': image_generator.get_performance_metrics()
                }
            )
            
        except Exception as e:
            logger.error(f"Parallel image processing failed: {e}")
            return ProcessingResult(success=False, error=str(e))
```

---

#### TASK 6.3: Documentation Updates

**Prerequisites**:
- All previous tasks completed successfully
- Parallel image generation fully implemented and tested
- Performance benchmarks completed

**🔴 RED PHASE - Documentation Requirements Tests**

**Action 6.3.1**: Create documentation verification tests
```python
# tests/test_documentation.py
"""Test documentation completeness and accuracy."""
import pytest
import os
from pathlib import Path


class TestDocumentation:
    """Test documentation requirements."""
    
    def test_readme_contains_parallel_image_section(self):
        """Test that README contains parallel image generation documentation."""
        readme_path = Path(__file__).parent.parent / "README.md"
        assert readme_path.exists(), "README.md must exist"
        
        content = readme_path.read_text()
        
        # Check for parallel image generation section
        assert "Parallel Image Generation" in content
        assert "60-70% performance improvement" in content
        assert "AnyIO" in content
        assert "concurrent processing" in content
        
    def test_readme_contains_usage_examples(self):
        """Test that README contains usage examples."""
        readme_path = Path(__file__).parent.parent / "README.md"
        content = readme_path.read_text()
        
        # Check for usage examples
        assert "ParallelImageGenerator" in content
        assert "generate_images_parallel" in content
        
    def test_readme_performance_metrics_documented(self):
        """Test that performance metrics are documented."""
        readme_path = Path(__file__).parent.parent / "README.md"
        content = readme_path.read_text()
        
        assert "Performance Improvements" in content
        assert "image generation time" in content
```

**🟢 GREEN PHASE - Update README Documentation**

**Action 6.3.2**: Update README.md with parallel image generation section
```markdown
# Add to README.md (insert after existing improvements section)

## ⚡ Performance Improvements - Parallel Image Generation

### Overview
The system now includes **parallel image generation** capabilities that reduce video creation time by **60-70%** through concurrent processing.

### Key Features
- **Concurrent Processing**: Generate multiple images simultaneously using AnyIO structured concurrency
- **Rate Limiting**: Respect API limits while maximizing throughput with configurable delays
- **Error Handling**: Comprehensive retry mechanisms with exponential backoff
- **Resource Management**: Efficient memory usage and connection management
- **Monitoring**: Real-time performance metrics and alerting

### Technical Implementation
- **Technology Stack**: AnyIO for structured concurrency, pytest for comprehensive testing
- **Architecture**: Modular design with clean separation of concerns
- **Reliability**: 90%+ test coverage with TDD methodology
- **Standards**: Full PEP 8 compliance for code documentation

### Performance Metrics
- **Speed Improvement**: 60-70% reduction in image generation time
- **Concurrent Tasks**: Configurable (default: 3 concurrent images)
- **Memory Efficiency**: <100MB additional memory usage
- **Error Resilience**: <30% failure rate under adverse conditions

### Usage Example

```python
from agents.parallel_image_generator import ParallelImageGenerator
import google.generativeai as genai

# Initialize with custom configuration
client = genai.Client()
generator = ParallelImageGenerator(
    ai_client=client,
    max_concurrent=3,
    rate_limit_delay=0.5,
    max_retries=3
)

# Generate images concurrently
prompts = [
    "Anime character training scene",
    "Epic battle sequence", 
    "Character development moment"
]

results = await generator.generate_images_parallel(
    prompts, "My Hero Academia", "1", "4"
)

# Check results
successful = [r for r in results if r.success]
print(f"Generated {len(successful)}/{len(results)} images successfully")
```

### Configuration
Configure parallel image generation in `config/settings.py`:

```python
# Parallel Image Generation Settings
parallel_image_max_concurrent: int = 3      # Concurrent tasks
parallel_image_rate_limit_delay: float = 0.5  # API delay (seconds)
parallel_image_max_retries: int = 3         # Retry attempts
parallel_image_request_timeout: float = 30.0  # Request timeout
```

### Integration with Existing Workflow
The parallel image generator integrates seamlessly with the existing video creation pipeline:

1. **Backward Compatible**: Maintains existing API signatures
2. **Drop-in Replacement**: Can replace sequential image generation
3. **Monitoring Integration**: Works with existing quality agents
4. **Error Handling**: Integrates with workflow orchestrator error handling
```

**Action 6.3.3**: Update CLI Commands documentation section
```markdown
# Add to CLI Commands section in README.md

### 🖼️ **Parallel Image Generation Commands**

| Command | Description | Arguments | Flags |
|---------|-------------|-----------|-------|
| `test-parallel-images` | Test parallel image generation | `show` `season` `episode` | `--concurrent` `--delay` |
| `benchmark-parallel` | Benchmark parallel vs sequential | `show` `season` `episode` | `--runs` `--detailed` |
| `monitor-image-generation` | Monitor image generation metrics | None | `--interval` (default: 5s) |

```bash
# Examples
python main_refactored.py test-parallel-images "My Hero Academia" 1 4 --concurrent 5
python main_refactored.py benchmark-parallel "Attack on Titan" 1 1 --runs 3
python main_refactored.py monitor-image-generation --interval 10
```
```

**Action 6.3.4**: Add development documentation
```markdown
# Add to Development section in README.md

### 🔧 Development - Parallel Image Generation

#### Running Tests
```bash
# Test parallel image generation
pytest tests/test_parallel_image_generation.py -v

# Test with coverage
pytest tests/test_parallel_image_generation.py --cov=agents.parallel_image_generator --cov-report=html

# Performance tests
pytest tests/test_parallel_image_generation.py::TestPerformance -v -s

# Integration tests  
pytest tests/test_parallel_image_generation.py::TestSystemIntegration -v
```

#### Development Workflow
1. **Follow TDD**: Always write tests first (Red-Green-Refactor)
2. **PEP 8 Compliance**: All code must follow PEP 8 standards
3. **Documentation**: Update docstrings using PEP 257 conventions
4. **Performance Testing**: Verify improvements meet 60-70% target
5. **Integration Testing**: Ensure compatibility with existing system
```

**Action 6.3.5**: Update technology stack section
```markdown
# Update Technology Stack section in README.md

### Enhanced Technology Stack

#### AI & Machine Learning
- **Google Gemini 2.0 Flash** - Content generation and analysis
- **Gemini 2.5 Flash TTS** - Professional voice narration  
- **Gemini 2.0 Flash Image Generation** - AI-generated visual assets (now with parallel processing)
- **ChromaDB** - Vector database for character analysis
- **Sentence Transformers** - Semantic embeddings and similarity search

#### Performance & Concurrency (NEW)
- **AnyIO** - Structured concurrency framework for parallel processing
- **Asyncio** - Asynchronous I/O operations
- **Concurrent Processing** - Parallel image generation with rate limiting

#### Media Processing
- **MoviePy** - Video compilation and editing
- **PIL (Pillow)** - Image processing and manipulation
- **FFmpeg** - Audio/video encoding (via MoviePy)

#### Testing & Quality
- **pytest** - Testing framework with comprehensive fixtures
- **pytest-asyncio** - Asynchronous test support
- **pytest-cov** - Code coverage analysis
- **TDD Methodology** - Test-driven development approach
```

**Verification 6.3.5**: Validate documentation updates
```bash
# Test README documentation
pytest tests/test_documentation.py -v

# Verify README contains all required sections
grep -E "(Parallel Image Generation|Performance Improvements|AnyIO)" README.md

# Check for broken links or formatting issues
python -m py_compile README.md  # If using Python markdown validator
```

**🔵 REFACTOR PHASE - Documentation Quality Improvements**

**Action 6.3.6**: Validate documentation standards
```bash
# Check markdown formatting
markdownlint README.md

# Verify code examples are syntactically correct
python -m py_compile -  # Test Python code blocks

# Spell check documentation
# aspell check README.md  # If available
```

**Success Criteria for Task 6.3**:
- [ ] README.md updated with parallel image generation section
- [ ] Usage examples included and tested
- [ ] Performance metrics clearly documented  
- [ ] CLI commands documented with examples
- [ ] Development workflow documented
- [ ] Technology stack updated
- [ ] All documentation tests pass
- [ ] Markdown formatting validated

**Failure Handling**: If documentation updates fail:
1. Verify README.md file permissions and path
2. Check for markdown syntax errors
3. Validate code examples compile correctly
4. Ensure all links and references are accurate
5. Run documentation tests to identify missing sections

---

## 📊 Success Metrics & Validation

### Performance Targets
- **60-70% reduction** in total image generation time
- **< 30% failure rate** under normal operation
- **< 100MB additional memory** usage during processing
- **< 1 second overhead** for parallelization setup

### Quality Targets
- **90%+ test coverage** for parallel image generation code
- **Zero regression** in image quality compared to sequential generation
- **Consistent error handling** across all failure scenarios
- **Production-ready monitoring** and alerting

## 🚀 Deployment Plan

### Phase 1: Development Environment (Week 4)
1. Deploy to development environment with feature flag
2. Run comprehensive test suite
3. Performance baseline comparison
4. Code review and optimization

### Phase 2: Staging Environment (Week 5)
1. Deploy to staging with production-like load
2. Load testing with realistic episode data
3. Monitor resource usage and error rates
4. Integration testing with full video pipeline

### Phase 3: Production Rollout (Week 6)
1. Canary deployment (10% of traffic)
2. Gradual rollout to 50%, then 100%
3. Monitor performance metrics and error rates
4. Rollback plan if issues detected

## 🔧 Development Commands

```bash
# Run TDD cycle
pytest tests/test_parallel_image_generation.py -v

# Run specific test phase
pytest tests/test_parallel_image_generation.py::TestParallelImageGeneratorInfrastructure -v
pytest tests/test_parallel_image_generation.py::TestRateLimiting -v
pytest tests/test_parallel_image_generation.py::TestImageGeneration -v

# Run integration tests
pytest tests/test_parallel_image_generation.py::TestSystemIntegration -v

# Run performance tests
pytest tests/test_parallel_image_generation.py::TestPerformance -v

# Run with coverage
pytest tests/test_parallel_image_generation.py --cov=agents.parallel_image_generator --cov-report=html

# Install dependencies
pip install anyio pytest pytest-asyncio pytest-cov psutil

# Run full test suite
pytest tests/ -v --cov=agents --cov-report=term-missing
```

## 📝 TDD Benefits for This Implementation

1. **Reliability**: Each feature is thoroughly tested before implementation
2. **Design Quality**: TDD drives better API design and separation of concerns
3. **Regression Prevention**: Comprehensive test suite prevents breaking changes
4. **Documentation**: Tests serve as living documentation of expected behavior
5. **Confidence**: High test coverage provides confidence for production deployment
6. **Refactoring Safety**: Tests enable safe refactoring and optimization

## 🔍 Risk Mitigation

### Technical Risks
- **API Rate Limits**: Mitigated by configurable rate limiting and exponential backoff
- **Memory Usage**: Addressed by streaming processing and resource monitoring
- **Error Cascading**: Prevented by individual error handling and partial failure support

### Integration Risks
- **Breaking Changes**: Minimized by maintaining backward compatibility
- **Performance Regression**: Addressed by comprehensive performance testing
- **System Instability**: Mitigated by gradual rollout and feature flags

This TDD plan ensures a robust, well-tested, and production-ready parallel image generation system that significantly improves performance while maintaining reliability and quality standards.

---

## 🤖 AI Agent Execution Checklist

### Phase 1: Foundation & Infrastructure ✅
- [ ] **Task 1.1**: Test Infrastructure Setup
  - [ ] Install dependencies: `pip install anyio pytest pytest-asyncio pytest-cov psutil`
  - [ ] Create directories: `mkdir -p tests/unit tests/integration agents`
  - [ ] Write failing tests for ParallelImageGenerator
  - [ ] Implement minimal class to pass basic tests
  - [ ] Verify: `pytest tests/test_parallel_image_generation.py::TestParallelImageGeneratorInfrastructure -v`

- [ ] **Task 1.2**: Rate Limiting Implementation
  - [ ] Write failing rate limiting tests
  - [ ] Implement AnyIO CapacityLimiter integration
  - [ ] Verify concurrent limits enforced
  - [ ] Test timing requirements met

### Phase 2: Core Generation Logic ⏳
- [ ] **Task 2.1**: Image Generation Tests
- [ ] **Task 2.2**: Error Handling Implementation
- [ ] **Task 2.3**: Retry Logic with Exponential Backoff

### Phase 3: Integration Testing ⏳  
- [ ] **Task 3.1**: System Integration Tests
- [ ] **Task 3.2**: Performance Benchmarking
- [ ] **Task 3.3**: Memory Usage Validation

### Phase 4: Error Handling & Edge Cases ⏳
- [ ] **Task 4.1**: Comprehensive Error Scenarios
- [ ] **Task 4.2**: Network Timeout Handling
- [ ] **Task 4.3**: Partial Failure Recovery

### Phase 5: Monitoring & Observability ⏳
- [ ] **Task 5.1**: Metrics Collection
- [ ] **Task 5.2**: Performance Monitoring
- [ ] **Task 5.3**: Alert System

### Phase 6: Production Integration ⏳
- [ ] **Task 6.1**: Configuration Management
- [ ] **Task 6.2**: Workflow Integration
- [ ] **Task 6.3**: Documentation Updates
- [ ] **Task 6.4**: Deployment Preparation

## 🚨 Critical Success Factors for AI Agent

1. **Always follow TDD cycle**: RED → GREEN → REFACTOR
2. **Follow PEP 8 standards**: All code must comply with Python style guidelines
3. **Verify each step**: Run tests after every code change
4. **Handle failures gracefully**: Each task has specific failure handling
5. **Maintain test coverage**: Aim for 90%+ coverage
6. **Performance validation**: Measure actual improvements
7. **Integration testing**: Ensure compatibility with existing system
8. **Documentation compliance**: Update README and maintain accurate docs

## 🛠️ Essential Commands Reference

```bash
# Test execution
pytest tests/test_parallel_image_generation.py -v
pytest tests/test_parallel_image_generation.py::TestClassName::test_method -v
pytest tests/ --cov=agents --cov-report=term-missing

# PEP 8 compliance validation
flake8 agents/parallel_image_generator.py --max-line-length=88
black --check agents/parallel_image_generator.py  # Code formatting
isort --check-only agents/parallel_image_generator.py  # Import sorting
mypy agents/parallel_image_generator.py  # Type checking

# Documentation validation
pytest tests/test_documentation.py -v
pydocstyle agents/parallel_image_generator.py  # Docstring style checking

# Development commands  
python -m pytest tests/test_parallel_image_generation.py --tb=short
python -c "import anyio; print('AnyIO available')"
python -c "from agents.parallel_image_generator import ParallelImageGenerator; print('Import successful')"

# Performance testing
python -m pytest tests/test_parallel_image_generation.py::TestPerformance -v -s
```

## 🎯 Final Validation Checklist

Before marking implementation complete, verify:

### Core Functionality ✅
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Performance improvement achieved: 60-70% faster image generation
- [ ] Error rate under 30% in failure scenarios
- [ ] Memory usage increase under 100MB
- [ ] Integration with existing workflow successful

### Code Quality & Standards ✅
- [ ] PEP 8 compliance: `flake8 agents/parallel_image_generator.py --max-line-length=88`
- [ ] Code formatting: `black --check agents/parallel_image_generator.py`
- [ ] Import sorting: `isort --check-only agents/parallel_image_generator.py`
- [ ] Type checking: `mypy agents/parallel_image_generator.py`
- [ ] Docstring standards: `pydocstyle agents/parallel_image_generator.py`

### Documentation & Usability ✅
- [ ] README.md updated with parallel image generation section
- [ ] Usage examples tested and functional
- [ ] CLI commands documented
- [ ] Performance metrics documented
- [ ] Documentation tests pass: `pytest tests/test_documentation.py -v`

### Production Readiness ✅
- [ ] Configuration management implemented
- [ ] Monitoring and alerting functional
- [ ] Error handling comprehensive
- [ ] Resource cleanup proper
- [ ] Deployment documentation complete

**Status**: Ready for AI Agent Autonomous Implementation ✅
