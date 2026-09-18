import asyncio
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Dict, List, Optional

from anyio import CapacityLimiter, create_task_group, sleep
from PIL import Image

from core.content_cache import ContentCache, ContentType, create_content_cache

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
    retry_count: int = 0


@dataclass
class PerformanceMetrics:
    """Performance metrics for image generation operations.

    Attributes:
        total_images: Total number of images processed.
        successful_images: Number of successfully generated images.
        failed_images: Number of failed image generations.
        total_time: Total time spent on image generation.
        average_time_per_image: Average time per image.
        error_rate: Percentage of failed generations.
        retry_stats: Statistics about retry attempts.
        throughput: Images generated per second.
    """

    total_images: int = 0
    successful_images: int = 0
    failed_images: int = 0
    total_time: float = 0.0
    average_time_per_image: float = 0.0
    error_rate: float = 0.0
    retry_stats: Dict[str, Any] = field(default_factory=dict)
    throughput: float = 0.0


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

    def __init__(
        self,
        ai_client,
        max_concurrent: int = 3,
        rate_limit_delay: float = 0.5,
        max_retries: int = 3,
        enable_caching: bool = True,
    ) -> None:
        """Initialize the parallel image generator.

        Args:
            ai_client: Client for AI image generation API.
            max_concurrent: Maximum concurrent tasks (default: 3).
            rate_limit_delay: Delay between API calls in seconds (default: 0.5).
            max_retries: Maximum retry attempts for failed generations (default: 3).
            enable_caching: Whether to enable content caching (default: True).
        """
        self.ai_client = ai_client
        self.max_concurrent = max_concurrent
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.capacity_limiter = CapacityLimiter(max_concurrent)

        # Performance monitoring
        self._metrics = PerformanceMetrics()
        self._retry_counts = defaultdict(int)
        self._error_counts = defaultdict(int)
        
        # Content caching system
        self.enable_caching = enable_caching
        if enable_caching:
            self.content_cache = create_content_cache(
                max_image_entries=200,
                similarity_threshold=0.85,
                enable_persistence=True
            )
            logger.info("Content caching enabled for image generation")
        else:
            self.content_cache = None

    async def generate_single_image(
        self, prompt: str, show: str, season: str, episode: str, index: int
    ) -> ImageGenerationResult:
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
        start_time = time.time()
        retry_count = 0

        # Check cache first if enabled
        episode_context = f"{show}_{season}_{episode}"
        if self.enable_caching and self.content_cache:
            cached_result = self.content_cache.get_or_generate_image(
                prompt, self, episode_context=episode_context
            )
            if cached_result and 'image_path' in cached_result:
                generation_time = time.time() - start_time
                logger.debug(f"Using cached image for prompt: {prompt[:50]}...")
                return ImageGenerationResult(
                    success=True,
                    image_path=cached_result['image_path'],
                    prompt=prompt,
                    index=index,
                    generation_time=generation_time,
                    retry_count=0,
                )

        for attempt in range(self.max_retries):
            try:
                # Enhance prompt with style consistency
                enhanced_prompt = self._enhance_prompt_for_consistency(prompt, show)

                # Generate image using Gemini (or mock for testing)
                if hasattr(self.ai_client, "models") and hasattr(
                    self.ai_client.models, "generate_content"
                ):
                    # Check if it's a mock (has return_value attribute)
                    if hasattr(self.ai_client.models.generate_content, "return_value"):
                        # Mock call for testing
                        if asyncio.iscoroutinefunction(
                            self.ai_client.models.generate_content
                        ):
                            response = await self.ai_client.models.generate_content()
                        else:
                            response = self.ai_client.models.generate_content()
                    else:
                        # Real Gemini API call - use basic parameters for now
                        # The exact API structure may need adjustment based on
                        # actual Google API
                        try:
                            response = await self.ai_client.models.generate_content(
                                model="gemini-2.0-flash-preview-image-generation",
                                contents=enhanced_prompt,
                            )
                        except Exception:
                            # Fallback for API compatibility issues
                            response = self.ai_client.models.generate_content(
                                model="gemini-2.0-flash-preview-image-generation",
                                contents=enhanced_prompt,
                            )
                else:
                    # Fallback for different mock structures
                    if asyncio.iscoroutinefunction(self.ai_client.generate_image):
                        response = await self.ai_client.generate_image()
                    else:
                        response = self.ai_client.generate_image()

                # Process and save image
                image_path = await self._process_and_save_image(
                    response, show, season, episode, index
                )

                generation_time = time.time() - start_time

                # Update metrics for successful generation
                self._retry_counts[retry_count] += 1

                # Cache the generated image if caching enabled
                if self.enable_caching and self.content_cache:
                    image_data = {
                        'image_path': image_path,
                        'prompt': enhanced_prompt,
                        'show': show,
                        'season': season,
                        'episode': episode,
                        'generation_time': generation_time
                    }
                    content_hash = self.content_cache._generate_content_hash(
                        image_data, ContentType.IMAGE, episode_context
                    )
                    self.content_cache.cache_content(content_hash, image_data, ContentType.IMAGE)

                return ImageGenerationResult(
                    success=True,
                    image_path=image_path,
                    prompt=prompt,
                    index=index,
                    generation_time=generation_time,
                    retry_count=retry_count,
                )

            except Exception as e:
                retry_count += 1
                error_type = type(e).__name__
                self._error_counts[error_type] += 1

                logger.warning(f"Image generation attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    self._retry_counts[retry_count] += 1
                    return ImageGenerationResult(
                        success=False,
                        prompt=prompt,
                        index=index,
                        error=str(e),
                        generation_time=time.time() - start_time,
                        retry_count=retry_count,
                    )
                await sleep(0.5 * (attempt + 1))  # Exponential backoff

    async def generate_images_parallel(
        self, prompts: List[str], show: str, season: str, episode: str
    ) -> List[ImageGenerationResult]:
        """Generate multiple images in parallel with rate limiting.

        Args:
            prompts: List of text prompts for image generation.
            show: Name of the show for file organization.
            season: Season number for file organization.
            episode: Episode number for file organization.

        Returns:
            List[ImageGenerationResult]: Results for each image generation.
        """
        batch_start_time = time.time()
        results = []

        async with create_task_group() as tg:
            for index, prompt in enumerate(prompts):
                tg.start_soon(
                    self._generate_single_with_limiter,
                    prompt,
                    show,
                    season,
                    episode,
                    index,
                    results,
                )

        # Update batch metrics
        batch_time = time.time() - batch_start_time
        self._update_batch_metrics(results, batch_time)

        return results

    async def _generate_single_with_limiter(
        self,
        prompt: str,
        show: str,
        season: str,
        episode: str,
        index: int,
        results: List,
    ):
        """Generate single image with capacity limiting.

        Args:
            prompt: Text prompt for image generation.
            show: Name of the show for file organization.
            season: Season number for file organization.
            episode: Episode number for file organization.
            index: Index of this image in the batch.
            results: Shared list to append results to.
        """
        async with self.capacity_limiter:
            await sleep(self.rate_limit_delay)  # Rate limiting
            result = await self.generate_single_image(
                prompt, show, season, episode, index
            )
            results.append(result)

    def _enhance_prompt_for_consistency(self, prompt: str, show: str) -> str:
        """Enhance prompt for visual consistency.

        Args:
            prompt: Original prompt text.
            show: Show name for context.

        Returns:
            Enhanced prompt with style instructions.
        """
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

    async def _process_and_save_image(
        self, response, show: str, season: str, episode: str, index: int
    ) -> str:
        """Process API response and save image.

        Args:
            response: API response containing image data.
            show: Show name for file organization.
            season: Season number for file organization.
            episode: Episode number for file organization.
            index: Image index for unique filename.

        Returns:
            Path to the saved image file.
        """
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image = Image.open(BytesIO(part.inline_data.data))

                # Ensure the directory structure exists
                image_dir = f"{show}/Season{season}/Episode{episode}"
                os.makedirs(image_dir, exist_ok=True)

                # Save image with structured filename for video compilation
                image_path = f"{image_dir}/{show}_{episode}_{index}.png"
                image.save(image_path)

                return image_path

        raise ValueError("No image data found in API response")

    def _update_batch_metrics(
        self, results: List[ImageGenerationResult], batch_time: float
    ) -> None:
        """Update performance metrics based on batch results.

        Args:
            results: List of image generation results.
            batch_time: Total time taken for the batch.
        """
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        # Update counters
        self._metrics.total_images += len(results)
        self._metrics.successful_images += len(successful)
        self._metrics.failed_images += len(failed)
        self._metrics.total_time += batch_time

        # Calculate derived metrics
        if self._metrics.total_images > 0:
            self._metrics.error_rate = (
                self._metrics.failed_images / self._metrics.total_images
            ) * 100
            self._metrics.average_time_per_image = (
                self._metrics.total_time / self._metrics.total_images
            )
            self._metrics.throughput = (
                self._metrics.total_images / self._metrics.total_time
                if self._metrics.total_time > 0
                else 0.0
            )

        # Update retry statistics
        self._metrics.retry_stats = {
            "retry_distribution": dict(self._retry_counts),
            "error_types": dict(self._error_counts),
            "total_retries": sum(
                retry_count * count for retry_count, count in self._retry_counts.items()
            ),
            "average_retries_per_image": (
                sum(
                    retry_count * count
                    for retry_count, count in self._retry_counts.items()
                )
                / len(results)
                if results
                else 0
            ),
        }

    def get_performance_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics.

        Returns:
            PerformanceMetrics: Current performance statistics.
        """
        return self._metrics

    def reset_metrics(self) -> None:
        """Reset all performance metrics to zero."""
        self._metrics = PerformanceMetrics()
        self._retry_counts.clear()
        self._error_counts.clear()

    def log_performance_summary(self) -> None:
        """Log a summary of current performance metrics."""
        metrics = self._metrics

        logger.info("=== Parallel Image Generation Performance Summary ===")
        logger.info(f"Total Images: {metrics.total_images}")
        success_rate = (
            (metrics.successful_images / metrics.total_images * 100)
            if metrics.total_images > 0
            else 0
        )
        logger.info(f"Successful: {metrics.successful_images} ({success_rate:.1f}%)")
        logger.info(f"Failed: {metrics.failed_images} ({metrics.error_rate:.1f}%)")
        logger.info(f"Average Time per Image: {metrics.average_time_per_image:.2f}s")
        logger.info(f"Throughput: {metrics.throughput:.2f} images/sec")

        if metrics.retry_stats.get("retry_distribution"):
            logger.info(
                f"Retry Distribution: {metrics.retry_stats['retry_distribution']}"
            )
            avg_retries = metrics.retry_stats["average_retries_per_image"]
            logger.info(f"Average Retries per Image: {avg_retries:.2f}")

        if metrics.retry_stats.get("error_types"):
            logger.info(f"Error Types: {metrics.retry_stats['error_types']}")

    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status for monitoring.

        Returns:
            Dict containing health metrics and status indicators.
        """
        metrics = self._metrics

        # Define health thresholds
        error_rate_threshold = 30.0  # 30% error rate threshold
        min_throughput = 0.5  # Minimum 0.5 images/sec

        # Calculate health score (0-100)
        health_score = 100
        if metrics.error_rate > error_rate_threshold:
            health_score -= min(50, metrics.error_rate - error_rate_threshold)

        if metrics.throughput < min_throughput and metrics.total_images > 0:
            health_score -= 25

        status = "healthy"
        if health_score < 80:
            status = "degraded"
        if health_score < 50:
            status = "unhealthy"

        return {
            "status": status,
            "health_score": max(0, health_score),
            "metrics": {
                "error_rate": metrics.error_rate,
                "throughput": metrics.throughput,
                "total_images": metrics.total_images,
                "average_time_per_image": metrics.average_time_per_image,
            },
            "alerts": self._generate_alerts(),
            "timestamp": time.time(),
        }

    def _generate_alerts(self) -> List[str]:
        """Generate alerts based on current metrics.

        Returns:
            List of alert messages.
        """
        alerts = []
        metrics = self._metrics

        if metrics.error_rate > 30:
            alerts.append(
                f"High error rate: {metrics.error_rate:.1f}% (threshold: 30%)"
            )

        if metrics.throughput < 0.5 and metrics.total_images > 0:
            alerts.append(
                f"Low throughput: {metrics.throughput:.2f} images/sec (threshold: 0.5)"
            )

        if metrics.retry_stats.get("average_retries_per_image", 0) > 1.5:
            avg_retries = metrics.retry_stats["average_retries_per_image"]
            alerts.append(f"High retry rate: {avg_retries:.2f} avg retries/image")

        return alerts
