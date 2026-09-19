#!/usr/bin/env python3
"""
Unit tests for Adaptive Quality Management System.

This module tests the adaptive quality system that dynamically adjusts
quality settings based on context, system resources, deadlines, and
performance constraints.

Following TDD methodology - these tests should FAIL initially (RED phase).
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

# Import the module we're testing - will fail initially
try:
    from core.adaptive_quality_manager import (
        AdaptiveQualityManager,
        QualityProfile,
        SystemResources,
    )
except ImportError:
    # Expected to fail in RED phase
    pass


class TestAdaptiveQualityManager:
    """Test suite for adaptive quality settings."""

    @pytest.fixture
    def quality_manager(self):
        """Create AdaptiveQualityManager instance."""
        return AdaptiveQualityManager()

    @pytest.fixture
    def mock_system_resources_high(self):
        """Mock high-resource system."""
        return SystemResources(
            memory_gb=16.0, cpu_cores=8, cpu_usage_percent=25.0, available_disk_gb=500.0
        )

    @pytest.fixture
    def mock_system_resources_low(self):
        """Mock low-resource system."""
        return SystemResources(
            memory_gb=2.0, cpu_cores=2, cpu_usage_percent=85.0, available_disk_gb=10.0
        )

    @pytest.mark.asyncio
    async def test_quality_profile_selection_by_context(self, quality_manager):
        """
        Test quality profile selection based on context.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Different contexts (testing, preview, production) select appropriate profiles
        - Context-based selection follows logical quality hierarchy
        - Profile selection is deterministic for same context
        - Invalid contexts are handled gracefully
        """
        # Test different contexts
        contexts = ["draft", "preview", "production"]

        for context in contexts:
            # Act
            profile = await quality_manager.select_quality_profile(context=context)

            # Assert
            assert isinstance(profile, QualityProfile), (
                f"Should return QualityProfile for {context}"
            )
            assert profile.name == context, f"Profile name should match context {context}"

            # Validate quality hierarchy
            if context == "draft":
                assert profile.image_quality <= 0.7, "Draft should have lower image quality"
                assert profile.processing_priority == "speed", "Draft should prioritize speed"
            elif context == "preview":
                assert 0.7 < profile.image_quality <= 0.9, "Preview should have medium quality"
                assert profile.processing_priority == "balanced", "Preview should be balanced"
            elif context == "production":
                assert profile.image_quality > 0.9, "Production should have highest quality"
                assert profile.processing_priority == "quality", (
                    "Production should prioritize quality"
                )

        # Test invalid context
        with pytest.raises(KeyError):
            await quality_manager.select_quality_profile(context="invalid_context")

    @pytest.mark.asyncio
    async def test_resource_based_quality_adjustment(
        self, quality_manager, mock_system_resources_low, mock_system_resources_high
    ):
        """
        Test quality adjustment based on available system resources.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Low resources trigger quality downgrade
        - High resources allow maximum quality
        - Memory constraints are respected (<4GB limit)
        - CPU usage affects concurrent job limits
        """
        with patch.object(
            quality_manager,
            "_get_system_resources",
            return_value=mock_system_resources_low,
        ):
            # Act - Request production quality on low-resource system
            low_resource_profile = await quality_manager.select_quality_profile(
                context="production"
            )

            # Assert - Should be downgraded
            assert low_resource_profile.memory_limit_mb <= 2048, (
                "Memory limit should be reduced for low-resource system"
            )
            assert low_resource_profile.max_concurrent_jobs <= 2, (
                "Concurrent jobs should be limited on low-resource system"
            )

        with patch.object(
            quality_manager,
            "_get_system_resources",
            return_value=mock_system_resources_high,
        ):
            # Act - Request production quality on high-resource system
            high_resource_profile = await quality_manager.select_quality_profile(
                context="production"
            )

            # Assert - Should maintain high quality
            assert high_resource_profile.memory_limit_mb >= 4096, (
                "Memory limit should be higher for high-resource system"
            )
            assert high_resource_profile.image_quality >= 0.9, (
                "Image quality should be maintained on high-resource system"
            )

    @pytest.mark.asyncio
    async def test_deadline_pressure_quality_adaptation(self, quality_manager):
        """
        Test quality adaptation based on deadline pressure.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Tight deadlines prioritize speed over quality
        - Loose deadlines allow maximum quality
        - Deadline pressure calculation is accurate
        - Quality degradation is proportional to time pressure
        """
        # Test with tight deadline (1 hour from now)
        tight_deadline = datetime.now() + timedelta(hours=1)

        with patch.object(quality_manager, "_get_system_resources") as mock_resources:
            mock_resources.return_value = SystemResources(8.0, 4, 50.0, 100.0)

            # Act
            tight_profile = await quality_manager.select_quality_profile(
                context="production", deadline=tight_deadline
            )

            # Assert
            assert tight_profile.processing_priority in [
                "speed",
                "balanced",
            ], "Tight deadline should prioritize speed or balanced processing"
            assert tight_profile.max_concurrent_jobs >= 3, (
                "Tight deadline should increase concurrent processing"
            )

        # Test with loose deadline (1 week from now)
        loose_deadline = datetime.now() + timedelta(weeks=1)

        with patch.object(quality_manager, "_get_system_resources") as mock_resources:
            mock_resources.return_value = SystemResources(8.0, 4, 50.0, 100.0)

            # Act
            loose_profile = await quality_manager.select_quality_profile(
                context="production", deadline=loose_deadline
            )

            # Assert
            assert loose_profile.processing_priority == "quality", (
                "Loose deadline should prioritize quality"
            )
            assert loose_profile.image_quality >= 0.9, (
                "Loose deadline should maintain high image quality"
            )

    @pytest.mark.asyncio
    async def test_quality_metrics_tracking(self, quality_manager):
        """
        Test quality metrics tracking for optimization.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Quality settings are recorded with performance metrics
        - Metrics include processing time, memory usage, output quality
        - Historical data influences future quality decisions
        - Metrics are properly structured and accessible
        """
        # Arrange
        quality_profile = QualityProfile(
            name="test_profile",
            image_quality=0.8,
            video_resolution=(1920, 1080),
            compression_level=85,
            processing_priority="balanced",
            max_concurrent_jobs=4,
            memory_limit_mb=2048,
        )

        processing_metrics = {
            "processing_time_ms": 1500,
            "memory_usage_mb": 1800,
            "output_quality_score": 0.85,
            "cpu_usage_percent": 65.0,
        }

        # Act
        quality_manager.record_quality_metrics(quality_profile, processing_metrics)

        # Assert
        assert hasattr(quality_manager, "quality_history"), "Should maintain quality history"
        assert len(quality_manager.quality_history) > 0, "Should record quality metrics"

        # Check recorded data structure
        recorded_entry = quality_manager.quality_history[-1]
        assert "profile_name" in recorded_entry, "Should record profile name"
        assert "timestamp" in recorded_entry, "Should record timestamp"
        assert "processing_metrics" in recorded_entry, "Should record processing metrics"

    def test_system_resource_monitoring(self, quality_manager):
        """
        Test system resource monitoring using psutil.

        RED PHASE: This test should FAIL initially.

        Validates:
        - System resources are accurately monitored
        - Resource data includes memory, CPU, disk usage
        - Resource monitoring doesn't significantly impact performance
        - Edge cases (unavailable resources) are handled
        """
        # Act
        resources = quality_manager._get_system_resources()

        # Assert
        assert isinstance(resources, SystemResources), "Should return SystemResources object"
        assert resources.memory_gb > 0, "Should report positive memory amount"
        assert resources.cpu_cores > 0, "Should report positive CPU core count"
        assert 0.0 <= resources.cpu_usage_percent <= 100.0, "CPU usage should be valid percentage"
        assert resources.available_disk_gb >= 0, "Available disk should be non-negative"

        # Test multiple calls for consistency
        resources_2 = quality_manager._get_system_resources()
        assert isinstance(resources_2, SystemResources), "Should consistently return valid data"

    @pytest.mark.asyncio
    async def test_memory_constraint_enforcement(self, quality_manager):
        """
        Test memory constraint enforcement (<4GB peak usage).

        RED PHASE: This test should FAIL initially.

        Validates:
        - Memory limits are enforced in quality profiles
        - Peak usage constraint (<4GB) is respected
        - Memory-intensive settings are automatically downgraded
        - Memory monitoring affects profile selection
        """
        # Test with high memory demand context
        with patch.object(quality_manager, "_get_system_resources") as mock_resources:
            # Simulate system with limited memory
            mock_resources.return_value = SystemResources(3.0, 8, 30.0, 100.0)

            # Act
            profile = await quality_manager.select_quality_profile(context="production")

            # Assert
            assert profile.memory_limit_mb < 4096, (
                "Memory limit should be under 4GB for constrained system"
            )
            assert profile.memory_limit_mb <= 3000, (
                "Memory limit should respect available system memory"
            )

        # Test memory usage validation
        test_profile = QualityProfile(
            name="memory_test",
            image_quality=1.0,
            video_resolution=(3840, 2160),  # 4K - high memory usage
            compression_level=100,
            processing_priority="quality",
            max_concurrent_jobs=1,
            memory_limit_mb=5000,  # Exceeds 4GB limit
        )

        # Act
        validated_profile = quality_manager._validate_memory_constraints(test_profile)

        # Assert
        assert validated_profile.memory_limit_mb <= 4096, (
            "Memory constraint should enforce 4GB limit"
        )

    @pytest.mark.asyncio
    async def test_profile_adjustment_for_low_resources(self, quality_manager):
        """
        Test profile adjustment for low-resource environments.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Quality profiles are downgraded appropriately
        - Essential functionality is maintained
        - Graceful degradation preserves core features
        - Adjustment is proportional to resource constraints
        """
        # Arrange
        base_profile = QualityProfile(
            name="high_demand",
            image_quality=1.0,
            video_resolution=(1920, 1080),
            compression_level=95,
            processing_priority="quality",
            max_concurrent_jobs=8,
            memory_limit_mb=4096,
        )

        # Store original values for comparison
        original_quality = base_profile.image_quality

        low_resources = SystemResources(1.5, 2, 90.0, 5.0)  # Very constrained

        # Act
        adjusted_profile = quality_manager._adjust_profile_for_resources(
            base_profile, low_resources, time_pressure=0.8
        )

        # Assert
        assert adjusted_profile.image_quality < original_quality, (
            "Image quality should be reduced for low resources"
        )
        assert adjusted_profile.max_concurrent_jobs <= 2, (
            "Concurrent jobs should be limited for low CPU"
        )
        assert adjusted_profile.memory_limit_mb <= 1300, (
            "Memory limit should be reduced for low memory system"
        )
        assert adjusted_profile.processing_priority == "speed", (
            "Should prioritize speed under resource pressure"
        )

    def test_time_pressure_calculation(self, quality_manager):
        """
        Test time pressure calculation from deadlines.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Time pressure is calculated correctly from deadlines
        - Pressure values are in valid range (0.0-1.0)
        - Different deadline scenarios produce appropriate pressure
        - No deadline results in zero pressure
        """
        # Test immediate deadline (high pressure)
        immediate_deadline = datetime.now() + timedelta(minutes=30)
        immediate_pressure = quality_manager._calculate_time_pressure(immediate_deadline)

        assert 0.8 <= immediate_pressure <= 1.0, (
            f"Immediate deadline should create high pressure, got {immediate_pressure:.3f}"
        )

        # Test moderate deadline (medium pressure)
        moderate_deadline = datetime.now() + timedelta(hours=4)
        moderate_pressure = quality_manager._calculate_time_pressure(moderate_deadline)

        assert 0.3 <= moderate_pressure <= 0.7, (
            f"Moderate deadline should create medium pressure, got {moderate_pressure:.3f}"
        )

        # Test distant deadline (low pressure)
        distant_deadline = datetime.now() + timedelta(days=1)
        distant_pressure = quality_manager._calculate_time_pressure(distant_deadline)

        assert 0.0 <= distant_pressure <= 0.3, (
            f"Distant deadline should create low pressure, got {distant_pressure:.3f}"
        )

        # Test no deadline
        no_deadline_pressure = quality_manager._calculate_time_pressure(None)
        assert no_deadline_pressure == 0.0, "No deadline should result in zero pressure"

    def test_quality_profile_validation(self, quality_manager):
        """
        Test quality profile validation and constraints.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Quality profiles have valid parameter ranges
        - Profile constraints are enforced
        - Invalid profiles are corrected or rejected
        - Default profiles meet system requirements
        """
        # Test default profiles are valid
        for profile_name in ["draft", "preview", "production"]:
            profile = quality_manager.quality_profiles[profile_name]

            # Assert valid ranges
            assert 0.0 <= profile.image_quality <= 1.0, (
                f"{profile_name} should have valid image quality"
            )
            assert profile.video_resolution[0] > 0 and profile.video_resolution[1] > 0, (
                f"{profile_name} should have valid resolution"
            )
            assert 0 <= profile.compression_level <= 100, (
                f"{profile_name} should have valid compression level"
            )
            assert profile.max_concurrent_jobs > 0, (
                f"{profile_name} should have positive concurrent jobs"
            )
            assert profile.memory_limit_mb > 0, f"{profile_name} should have positive memory limit"

        # Test profile ordering (draft < preview < production)
        draft = quality_manager.quality_profiles["draft"]
        preview = quality_manager.quality_profiles["preview"]
        production = quality_manager.quality_profiles["production"]

        assert draft.image_quality <= preview.image_quality <= production.image_quality, (
            "Quality should increase: draft <= preview <= production"
        )

    @pytest.mark.asyncio
    async def test_performance_optimization_feedback(self, quality_manager):
        """
        Test performance optimization based on historical data.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Historical performance data influences future decisions
        - Optimization learning improves quality selection over time
        - Performance feedback loop works correctly
        - Bad performing profiles are avoided
        """
        # Arrange - Record some performance history
        good_profile = QualityProfile("good_profile", 0.8, (1920, 1080), 85, "balanced", 4, 2048)
        bad_profile = QualityProfile("bad_profile", 1.0, (3840, 2160), 100, "quality", 8, 6000)

        # Record good performance
        quality_manager.record_quality_metrics(
            good_profile,
            {
                "processing_time_ms": 800,
                "memory_usage_mb": 1500,
                "output_quality_score": 0.9,
                "success": True,
            },
        )

        # Record bad performance (memory exceeded)
        quality_manager.record_quality_metrics(
            bad_profile,
            {
                "processing_time_ms": 5000,
                "memory_usage_mb": 5500,  # Exceeds 4GB limit
                "output_quality_score": 0.95,
                "success": False,
            },
        )

        # Act - Request optimized profile
        with patch.object(quality_manager, "_get_system_resources") as mock_resources:
            mock_resources.return_value = SystemResources(4.0, 4, 50.0, 100.0)

            optimized_profile = await quality_manager.select_quality_profile(
                context="production", use_optimization=True
            )

            # Assert - Should avoid bad profile characteristics
            assert optimized_profile.memory_limit_mb <= 4096, (
                "Should avoid memory-excessive settings based on history"
            )
            assert optimized_profile.max_concurrent_jobs <= 6, (
                "Should limit concurrent jobs based on performance history"
            )

    @pytest.mark.asyncio
    async def test_quality_adaptation_edge_cases(self, quality_manager):
        """
        Test quality adaptation edge cases and boundary conditions.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Extreme resource constraints are handled
        - Zero or negative values are handled gracefully
        - Boundary conditions don't cause crashes
        - Fallback behavior works for edge cases
        """
        # Test with extremely low resources
        extreme_low_resources = SystemResources(0.5, 1, 99.0, 0.1)

        with patch.object(
            quality_manager, "_get_system_resources", return_value=extreme_low_resources
        ):
            # Act
            profile = await quality_manager.select_quality_profile(context="production")

            # Assert - Should still return valid profile
            assert isinstance(profile, QualityProfile), (
                "Should return valid profile for extreme constraints"
            )
            assert profile.memory_limit_mb > 0, "Should maintain positive memory limit"
            assert profile.max_concurrent_jobs >= 1, "Should maintain at least 1 concurrent job"
            assert profile.image_quality > 0, "Should maintain positive image quality"

        # Test with past deadline (negative time pressure)
        past_deadline = datetime.now() - timedelta(hours=1)
        pressure = quality_manager._calculate_time_pressure(past_deadline)

        assert pressure >= 0.0, "Past deadline should not create negative pressure"
        assert pressure <= 1.0, "Past deadline pressure should be clamped to valid range"

    @pytest.mark.asyncio
    async def test_profile_copying_and_modification(self, quality_manager):
        """
        Test profile copying and safe modification.

        RED PHASE: This test should FAIL initially.

        Validates:
        - Original profiles are not modified during adjustment
        - Profile copying creates independent instances
        - Modifications don't affect original profile templates
        - Memory references are properly managed
        """
        # Arrange
        original_profile = quality_manager.quality_profiles["production"]
        original_quality = original_profile.image_quality

        # Act - Modify a copy
        with patch.object(quality_manager, "_get_system_resources") as mock_resources:
            mock_resources.return_value = SystemResources(1.0, 1, 95.0, 1.0)  # Force downgrade

            modified_profile = await quality_manager.select_quality_profile(context="production")

            # Assert
            assert (
                quality_manager.quality_profiles["production"].image_quality == original_quality
            ), "Original profile should not be modified"
            assert modified_profile.image_quality != original_quality, (
                "Modified profile should have different quality"
            )
            assert modified_profile is not original_profile, (
                "Should return different object instance"
            )


class TestQualityProfileDataStructures:
    """Test quality profile data structures and validation."""

    def test_quality_profile_creation(self):
        """Test QualityProfile creation and validation."""
        # Act
        profile = QualityProfile(
            name="test",
            image_quality=0.8,
            video_resolution=(1920, 1080),
            compression_level=85,
            processing_priority="balanced",
            max_concurrent_jobs=4,
            memory_limit_mb=2048,
        )

        # Assert
        assert profile.name == "test"
        assert profile.image_quality == 0.8
        assert profile.video_resolution == (1920, 1080)
        assert profile.compression_level == 85
        assert profile.processing_priority == "balanced"
        assert profile.max_concurrent_jobs == 4
        assert profile.memory_limit_mb == 2048

    def test_system_resources_creation(self):
        """Test SystemResources creation and validation."""
        # Act
        resources = SystemResources(
            memory_gb=8.0, cpu_cores=4, cpu_usage_percent=50.0, available_disk_gb=100.0
        )

        # Assert
        assert resources.memory_gb == 8.0
        assert resources.cpu_cores == 4
        assert resources.cpu_usage_percent == 50.0
        assert resources.available_disk_gb == 100.0


if __name__ == "__main__":
    # Run tests to verify they fail (RED phase)
    pytest.main([__file__, "-v"])
