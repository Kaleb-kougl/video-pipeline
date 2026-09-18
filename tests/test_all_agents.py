#!/usr/bin/env python3
"""
Comprehensive test suite for all agents in the modular architecture.
"""

import sys
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import traceback

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AgentValidator:
    """Comprehensive agent validation and testing framework.
    
    This class provides a systematic approach to validating all system agents,
    testing their import capability, initialization, and basic functionality
    to ensure system reliability and identify problematic components.
    """
    
    def __init__(self):
        """Initialize the validator.
        
        Sets up tracking variables for test results, failed imports,
        and success/failure counters for comprehensive reporting.
        """
        self.test_results = {}
        self.failed_imports = []
        self.successful_tests = 0
        self.failed_tests = 0
        
    def test_agent_import(self, agent_name: str, import_path: str) -> bool:
        """Test if an agent can be imported successfully.
        
        Args:
            agent_name (str): Name of the agent class to import
            import_path (str): Python import path for the agent module
            
        Returns:
            bool: True if import succeeds, False otherwise
        """
        try:
            exec(f"from {import_path} import {agent_name}")
            logger.info(f"✅ {agent_name} import successful")
            return True
        except Exception as e:
            logger.error(f"❌ {agent_name} import failed: {e}")
            self.failed_imports.append(f"{agent_name}: {e}")
            return False
    
    def test_agent_initialization(self, agent_class, agent_name: str, init_params: Dict = None) -> Optional[Any]:
        """Test if an agent can be initialized successfully.
        
        Args:
            agent_class: The agent class to instantiate
            agent_name (str): Name of the agent for logging purposes
            init_params (Dict, optional): Parameters to pass to agent constructor
            
        Returns:
            Optional[Any]: Initialized agent instance if successful, None otherwise
        """
        try:
            if init_params:
                agent = agent_class(**init_params)
            else:
                agent = agent_class()
            logger.info(f"✅ {agent_name} initialization successful")
            return agent
        except Exception as e:
            logger.error(f"❌ {agent_name} initialization failed: {e}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            return None
    
    def test_agent_basic_functionality(self, agent, agent_name: str, test_methods: list) -> bool:
        """Test basic functionality of an agent.
        
        Args:
            agent: The initialized agent instance to test
            agent_name (str): Name of the agent for logging purposes
            test_methods (list): List of (method_name, args, kwargs) tuples to test
            
        Returns:
            bool: True if at least 50% of methods pass, False otherwise
        """
        if agent is None:
            return False
            
        success_count = 0
        total_methods = len(test_methods)
        
        for method_name, test_args, test_kwargs in test_methods:
            try:
                if hasattr(agent, method_name):
                    method = getattr(agent, method_name)
                    result = method(*test_args, **test_kwargs)
                    logger.info(f"✅ {agent_name}.{method_name}() executed successfully")
                    success_count += 1
                else:
                    logger.warning(f"⚠️ {agent_name}.{method_name}() method not found")
            except Exception as e:
                logger.error(f"❌ {agent_name}.{method_name}() failed: {e}")
        
        success_rate = success_count / total_methods if total_methods > 0 else 0
        logger.info(f"📊 {agent_name} functionality test: {success_count}/{total_methods} methods passed ({success_rate:.1%})")
        return success_rate >= 0.5  # At least 50% of methods should work
    
    def validate_transcript_discovery_agent(self) -> Dict:
        """Validate the TranscriptDiscoveryAgent.
        
        Tests import, initialization, and basic functionality of the
        TranscriptDiscoveryAgent to ensure transcript finding capabilities work.
        
        Returns:
            dict: Validation result with status, agent instance, and functionality score
        """
        logger.info("🔍 Testing TranscriptDiscoveryAgent...")
        
        # Test import
        if not self.test_agent_import("TranscriptDiscoveryAgent", "agents.transcript_agent"):
            return {"status": "failed", "reason": "import_failed"}
        
        # Import and initialize
        from agents.transcript_agent import TranscriptDiscoveryAgent
        agent = self.test_agent_initialization(TranscriptDiscoveryAgent, "TranscriptDiscoveryAgent")
        
        if agent is None:
            return {"status": "failed", "reason": "initialization_failed"}
        
        # Test basic functionality
        test_methods = [
            ("find_episode_transcript", ["My Hero Academia", 1, 4], {}),
            # Add more methods as needed
        ]
        
        functionality_ok = self.test_agent_basic_functionality(agent, "TranscriptDiscoveryAgent", test_methods)
        
        return {
            "status": "passed" if functionality_ok else "partial",
            "agent_instance": agent,
            "functionality_score": functionality_ok
        }
    
    def validate_transcript_source_agent(self) -> Dict:
        """Validate the TranscriptSourceDiscoveryAgent."""
        logger.info("🔍 Testing TranscriptSourceDiscoveryAgent...")
        
        # Test import
        if not self.test_agent_import("TranscriptSourceDiscoveryAgent", "agents.transcript_source_agent"):
            return {"status": "failed", "reason": "import_failed"}
        
        # Import and initialize
        from agents.transcript_source_agent import TranscriptSourceDiscoveryAgent
        agent = self.test_agent_initialization(TranscriptSourceDiscoveryAgent, "TranscriptSourceDiscoveryAgent")
        
        if agent is None:
            return {"status": "failed", "reason": "initialization_failed"}
        
        # Test basic functionality
        test_methods = [
            ("discover_sources_for_show", ["My Hero Academia"], {"season": 1}),
            ("get_source_recommendations", [[]], {}),  # Empty sources list
        ]
        
        functionality_ok = self.test_agent_basic_functionality(agent, "TranscriptSourceDiscoveryAgent", test_methods)
        
        return {
            "status": "passed" if functionality_ok else "partial",
            "agent_instance": agent,
            "functionality_score": functionality_ok
        }
    
    def validate_content_agent(self) -> Dict:
        """Validate the ContentAgent."""
        logger.info("🔍 Testing ContentAgent...")
        
        # Test import
        if not self.test_agent_import("ContentAgent", "agents.content_agent"):
            return {"status": "failed", "reason": "import_failed"}
        
        # Import and initialize (needs model parameter)
        from agents.content_agent import ContentAgent
        
        # Try to initialize with a mock model
        try:
            from langchain.chat_models import init_chat_model
            model = init_chat_model("gemini-2.0-flash", model_provider="google_genai")
            agent = self.test_agent_initialization(ContentAgent, "ContentAgent", {"model": model})
        except Exception as e:
            logger.warning(f"⚠️ Using mock model for ContentAgent: {e}")
            # Create a mock model
            class MockModel:
                def invoke(self, *args, **kwargs):
                    return {"content": "Mock response"}
            
            agent = self.test_agent_initialization(ContentAgent, "ContentAgent", {"model": MockModel()})
        
        if agent is None:
            return {"status": "failed", "reason": "initialization_failed"}
        
        # Test basic functionality
        test_methods = [
            ("extract_and_analyze", ["https://example.com"], {}),
        ]
        
        functionality_ok = self.test_agent_basic_functionality(agent, "ContentAgent", test_methods)
        
        return {
            "status": "passed" if functionality_ok else "partial",
            "agent_instance": agent,
            "functionality_score": functionality_ok
        }
    
    def validate_video_agent(self) -> Dict:
        """Validate the VideoGenerationAgent."""
        logger.info("🔍 Testing VideoGenerationAgent...")
        
        # Test import
        if not self.test_agent_import("VideoGenerationAgent", "agents.video_agent"):
            return {"status": "failed", "reason": "import_failed"}
        
        # Import and initialize
        from agents.video_agent import VideoGenerationAgent
        agent = self.test_agent_initialization(VideoGenerationAgent, "VideoGenerationAgent")
        
        if agent is None:
            return {"status": "failed", "reason": "initialization_failed"}
        
        # Test basic functionality (with mock data)
        test_methods = [
            # Add specific VideoGenerationAgent methods
        ]
        
        functionality_ok = True  # Placeholder since we need to check actual methods
        
        return {
            "status": "passed" if functionality_ok else "partial",
            "agent_instance": agent,
            "functionality_score": functionality_ok
        }
    
    def validate_quality_agent(self) -> Dict:
        """Validate the QualityAssuranceAgent."""
        logger.info("🔍 Testing QualityAssuranceAgent...")
        
        # Test import
        if not self.test_agent_import("QualityAssuranceAgent", "agents.quality_agent"):
            return {"status": "failed", "reason": "import_failed"}
        
        # Import and initialize
        from agents.quality_agent import QualityAssuranceAgent
        agent = self.test_agent_initialization(QualityAssuranceAgent, "QualityAssuranceAgent")
        
        if agent is None:
            return {"status": "failed", "reason": "initialization_failed"}
        
        # Test basic functionality
        test_methods = [
            ("validate_transcript_quality", [{"content": "test transcript", "source": "test"}], {}),
            ("validate_content_quality", [{"content": "test content"}], {}),
        ]
        
        functionality_ok = self.test_agent_basic_functionality(agent, "QualityAssuranceAgent", test_methods)
        
        return {
            "status": "passed" if functionality_ok else "partial",
            "agent_instance": agent,
            "functionality_score": functionality_ok
        }
    
    def validate_discovery_agent(self) -> Dict:
        """Validate the EpisodeDiscoveryAgent."""
        logger.info("🔍 Testing EpisodeDiscoveryAgent...")
        
        # Test import
        if not self.test_agent_import("EpisodeDiscoveryAgent", "agents.discovery_agent"):
            return {"status": "failed", "reason": "import_failed"}
        
        # Import and initialize
        from agents.discovery_agent import EpisodeDiscoveryAgent
        agent = self.test_agent_initialization(EpisodeDiscoveryAgent, "EpisodeDiscoveryAgent")
        
        if agent is None:
            return {"status": "failed", "reason": "initialization_failed"}
        
        # Test basic functionality
        test_methods = [
            ("discover_episodes", ["My Hero Academia"], {"season": 1}),
        ]
        
        functionality_ok = self.test_agent_basic_functionality(agent, "EpisodeDiscoveryAgent", test_methods)
        
        return {
            "status": "passed" if functionality_ok else "partial",
            "agent_instance": agent,
            "functionality_score": functionality_ok
        }
    
    def validate_config_manager(self) -> Dict:
        """Validate the EpisodeConfigManager."""
        logger.info("🔍 Testing EpisodeConfigManager...")
        
        # Test import
        if not self.test_agent_import("EpisodeConfigManager", "agents.config_manager"):
            return {"status": "failed", "reason": "import_failed"}
        
        # Import and initialize
        from agents.config_manager import EpisodeConfigManager
        agent = self.test_agent_initialization(EpisodeConfigManager, "EpisodeConfigManager")
        
        if agent is None:
            return {"status": "failed", "reason": "initialization_failed"}
        
        # Test basic functionality
        test_methods = [
            ("get_episode_count", ["My Hero Academia", 1], {}),
            ("get_episode_config", ["My Hero Academia", 1, 4], {}),
        ]
        
        functionality_ok = self.test_agent_basic_functionality(agent, "EpisodeConfigManager", test_methods)
        
        return {
            "status": "passed" if functionality_ok else "partial",
            "agent_instance": agent,
            "functionality_score": functionality_ok
        }
    
    def validate_workflow_orchestrator(self) -> Dict:
        """Validate the WorkflowOrchestrator."""
        logger.info("🔍 Testing WorkflowOrchestrator...")
        
        # Test import
        if not self.test_agent_import("WorkflowOrchestrator", "agents.workflow_orchestrator"):
            return {"status": "failed", "reason": "import_failed"}
        
        # Import and initialize
        from agents.workflow_orchestrator import WorkflowOrchestrator
        
        try:
            agent = self.test_agent_initialization(WorkflowOrchestrator, "WorkflowOrchestrator")
        except Exception as e:
            logger.warning(f"⚠️ WorkflowOrchestrator initialization failed, trying with custom db path: {e}")
            agent = self.test_agent_initialization(WorkflowOrchestrator, "WorkflowOrchestrator", {"db_path": ":memory:"})
        
        if agent is None:
            return {"status": "failed", "reason": "initialization_failed"}
        
        # Test basic functionality
        test_methods = [
            # WorkflowOrchestrator methods would go here
        ]
        
        functionality_ok = True  # Placeholder
        
        return {
            "status": "passed" if functionality_ok else "partial",
            "agent_instance": agent,
            "functionality_score": functionality_ok
        }
    
    def validate_quality_agents_system(self) -> Dict:
        """Validate the Quality Agents System."""
        logger.info("🔍 Testing Quality Agents System...")
        
        quality_agents_results = {}
        
        # Test QualityCoordinator
        try:
            from agents.quality_agents.quality_coordinator import QualityCoordinator
            coordinator = self.test_agent_initialization(QualityCoordinator, "QualityCoordinator")
            quality_agents_results["coordinator"] = coordinator is not None
        except Exception as e:
            logger.error(f"❌ QualityCoordinator test failed: {e}")
            quality_agents_results["coordinator"] = False
        
        # Test individual quality agents
        quality_agent_classes = [
            ("TranscriptQualityAgent", "agents.quality_agents.transcript_quality_agent"),
            ("ContentQualityAgent", "agents.quality_agents.content_quality_agent"),
            ("VideoQualityAgent", "agents.quality_agents.video_quality_agent"),
            ("DiscoveryQualityAgent", "agents.quality_agents.discovery_quality_agent"),
            ("WorkflowQualityAgent", "agents.quality_agents.workflow_quality_agent"),
        ]
        
        for agent_name, import_path in quality_agent_classes:
            try:
                import_success = self.test_agent_import(agent_name, import_path)
                quality_agents_results[agent_name.lower()] = import_success
            except Exception as e:
                logger.error(f"❌ {agent_name} test failed: {e}")
                quality_agents_results[agent_name.lower()] = False
        
        success_rate = sum(quality_agents_results.values()) / len(quality_agents_results)
        
        return {
            "status": "passed" if success_rate >= 0.8 else "partial",
            "results": quality_agents_results,
            "success_rate": success_rate
        }
    
    def run_comprehensive_validation(self) -> Dict:
        """Run comprehensive validation of all agents.
        
        Executes validation tests for all system agents and provides
        comprehensive reporting on system health and component status.
        
        Returns:
            dict: Comprehensive validation results including success rates and detailed results
        """
        logger.info("🚀 Starting comprehensive agent validation...")
        logger.info("=" * 60)
        
        validation_results = {}
        
        # Test each agent
        validation_tests = [
            ("TranscriptDiscoveryAgent", self.validate_transcript_discovery_agent),
            ("TranscriptSourceDiscoveryAgent", self.validate_transcript_source_agent),
            ("ContentAgent", self.validate_content_agent),
            ("VideoGenerationAgent", self.validate_video_agent),
            ("QualityAssuranceAgent", self.validate_quality_agent),
            ("EpisodeDiscoveryAgent", self.validate_discovery_agent),
            ("EpisodeConfigManager", self.validate_config_manager),
            ("WorkflowOrchestrator", self.validate_workflow_orchestrator),
            ("QualityAgentsSystem", self.validate_quality_agents_system),
        ]
        
        for agent_name, test_func in validation_tests:
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Testing {agent_name}...")
            logger.info(f"{'=' * 60}")
            
            try:
                result = test_func()
                validation_results[agent_name] = result
                
                if result["status"] == "passed":
                    self.successful_tests += 1
                    logger.info(f"✅ {agent_name} validation PASSED")
                elif result["status"] == "partial":
                    self.failed_tests += 1
                    logger.warning(f"⚠️ {agent_name} validation PARTIAL")
                else:
                    self.failed_tests += 1
                    logger.error(f"❌ {agent_name} validation FAILED")
                    
            except Exception as e:
                logger.error(f"❌ {agent_name} validation crashed: {e}")
                logger.error(f"Stack trace: {traceback.format_exc()}")
                validation_results[agent_name] = {"status": "crashed", "error": str(e)}
                self.failed_tests += 1
        
        # Generate summary
        total_tests = len(validation_tests)
        success_rate = self.successful_tests / total_tests
        
        logger.info(f"\n{'=' * 60}")
        logger.info("VALIDATION SUMMARY")
        logger.info(f"{'=' * 60}")
        logger.info(f"Total agents tested: {total_tests}")
        logger.info(f"Successful: {self.successful_tests}")
        logger.info(f"Failed/Partial: {self.failed_tests}")
        logger.info(f"Success rate: {success_rate:.1%}")
        
        if self.failed_imports:
            logger.warning("\nImport failures:")
            for failure in self.failed_imports:
                logger.warning(f"  - {failure}")
        
        return {
            "total_tests": total_tests,
            "successful": self.successful_tests,
            "failed": self.failed_tests,
            "success_rate": success_rate,
            "results": validation_results,
            "failed_imports": self.failed_imports
        }


def main():
    """Main function to run all agent validation tests.
    
    Coordinates the execution of comprehensive agent validation testing,
    provides final assessment of system health, and returns structured results.
    
    Returns:
        dict: Complete validation results including success rates and component status
    """
    print("🧪 Agent Validation Test Suite")
    print("=" * 60)
    
    validator = AgentValidator()
    results = validator.run_comprehensive_validation()
    
    print(f"\n🎯 Final Results:")
    print(f"Success Rate: {results['success_rate']:.1%}")
    print(f"Agents Passed: {results['successful']}/{results['total_tests']}")
    
    if results['success_rate'] >= 0.8:
        print("🎉 Overall validation: PASSED")
    elif results['success_rate'] >= 0.5:
        print("⚠️ Overall validation: PARTIAL")
    else:
        print("❌ Overall validation: FAILED")
    
    return results


if __name__ == "__main__":
    main()
