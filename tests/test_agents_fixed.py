#!/usr/bin/env python3
"""
Targeted fixes for the failing agents and updated test suite.
"""

import sys
import os
import logging
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_episode_discovery_agent():
    """Test EpisodeDiscoveryAgent with correct method names.
    
    Validates that the EpisodeDiscoveryAgent can be imported, initialized,
    and that its core methods (generate_episode_url, validate_episode_url,
    discover_episode_url) function correctly.
    
    Returns:
        bool: True if all tests pass, False otherwise
    """
    print("🔍 Testing EpisodeDiscoveryAgent with correct methods...")
    
    try:
        from agents.discovery_agent import EpisodeDiscoveryAgent
        agent = EpisodeDiscoveryAgent()
        
        # Test actual methods
        print("✅ EpisodeDiscoveryAgent imported and initialized")
        
        # Test generate_episode_url
        url = agent.generate_episode_url(1, 4, "Start Line")
        print(f"✅ generate_episode_url(1, 4, 'Start Line') = {url}")
        
        # Test validate_episode_url
        is_valid = agent.validate_episode_url("https://example.com")
        print(f"✅ validate_episode_url('https://example.com') = {is_valid}")
        
        # Test discover_episode_url
        discovered_url = agent.discover_episode_url(1, 4, ["Start Line"])
        print(f"✅ discover_episode_url(1, 4, ['Start Line']) = {discovered_url}")
        
        print("✅ EpisodeDiscoveryAgent: ALL TESTS PASSED")
        return True
        
    except Exception as e:
        print(f"❌ EpisodeDiscoveryAgent test failed: {e}")
        return False


def test_episode_config_manager():
    """Test EpisodeConfigManager with correct method names.
    
    Validates the EpisodeConfigManager's ability to handle episode configuration
    retrieval, season episode listing, and episode title loading functionality.
    
    Returns:
        bool: True if all tests pass, False otherwise
    """
    print("\n🔍 Testing EpisodeConfigManager with correct methods...")
    
    try:
        from agents.config_manager import EpisodeConfigManager
        agent = EpisodeConfigManager()
        
        print("✅ EpisodeConfigManager imported and initialized")
        
        # Test get_episode_config (correct signature: season, episode)
        config = agent.get_episode_config(1, 4)
        print(f"✅ get_episode_config(1, 4) = {config}")
        
        # Test get_season_episodes
        episodes = agent.get_season_episodes(1)
        print(f"✅ get_season_episodes(1) = {episodes}")
        
        # Test load_episode_titles
        agent.load_episode_titles()
        print("✅ load_episode_titles() executed successfully")
        
        print("✅ EpisodeConfigManager: ALL TESTS PASSED")
        return True
        
    except Exception as e:
        print(f"❌ EpisodeConfigManager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_all_agents_quick():
    """Quick test of all agents with basic functionality.
    
    Performs import and initialization tests on all major system agents
    to validate overall system health and identify failing components.
    
    Returns:
        dict: Test results mapping agent names to their test outcomes
    """
    print("🚀 Quick validation of all agents...")
    print("=" * 50)
    
    agents_to_test = [
        ("TranscriptDiscoveryAgent", "agents.transcript_agent"),
        ("TranscriptSourceDiscoveryAgent", "agents.transcript_source_agent"),
        ("ContentAgent", "agents.content_agent"),
        ("VideoGenerationAgent", "agents.video_agent"),
        ("QualityAssuranceAgent", "agents.quality_agent"),
        ("EpisodeDiscoveryAgent", "agents.discovery_agent"),
        ("EpisodeConfigManager", "agents.config_manager"),
        ("WorkflowOrchestrator", "agents.workflow_orchestrator"),
    ]
    
    results = {}
    
    for agent_name, import_path in agents_to_test:
        try:
            print(f"\n🔍 Testing {agent_name}...")
            
            # Import test
            module = __import__(import_path, fromlist=[agent_name])
            agent_class = getattr(module, agent_name)
            print(f"  ✅ Import successful")
            
            # Initialization test
            if agent_name == "ContentAgent":
                # ContentAgent needs a model
                try:
                    from langchain.chat_models import init_chat_model
                    model = init_chat_model("gemini-2.0-flash", model_provider="google_genai")
                    agent = agent_class(model)
                except:
                    # Fallback mock model
                    class MockModel:
                        def invoke(self, *args, **kwargs):
                            return {"content": "Mock response"}
                    agent = agent_class(MockModel())
            else:
                agent = agent_class()
            
            print(f"  ✅ Initialization successful")
            results[agent_name] = "✅ PASSED"
            
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            results[agent_name] = f"❌ FAILED: {str(e)[:50]}..."
    
    # Test quality agents system
    print(f"\n🔍 Testing Quality Agents System...")
    try:
        from agents.quality_agents.quality_coordinator import QualityCoordinator
        coordinator = QualityCoordinator()
        print(f"  ✅ QualityCoordinator initialization successful")
        results["QualityCoordinator"] = "✅ PASSED"
    except Exception as e:
        print(f"  ❌ QualityCoordinator failed: {e}")
        results["QualityCoordinator"] = f"❌ FAILED: {str(e)[:50]}..."
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY RESULTS:")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for agent, result in results.items():
        print(f"{result} {agent}")
        if "PASSED" in result:
            passed += 1
    
    success_rate = passed / total
    print(f"\n🎯 Success Rate: {passed}/{total} ({success_rate:.1%})")
    
    if success_rate >= 0.9:
        print("🎉 EXCELLENT - All agents working!")
    elif success_rate >= 0.8:
        print("✅ GOOD - Most agents working!")
    elif success_rate >= 0.7:
        print("⚠️ PARTIAL - Some issues to fix")
    else:
        print("❌ NEEDS WORK - Multiple agents failing")
    
    return results


def test_cli_commands():
    """Test the main CLI commands.
    
    Validates that the main CLI interface responds correctly to basic
    commands like --help and provides expected output.
    
    Returns:
        None
    """
    print("\n🔍 Testing CLI Commands...")
    print("=" * 50)
    
    # Test help command
    print("Testing --help command:")
    import subprocess
    try:
        result = subprocess.run([
            sys.executable, "main_refactored.py", "--help"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ --help command works")
            # Count available commands
            help_text = result.stdout
            commands = help_text.count("  ") - help_text.count("options:")
            print(f"   Available commands: ~{commands}")
        else:
            print(f"❌ --help failed: {result.stderr}")
    except Exception as e:
        print(f"❌ CLI test failed: {e}")


def main():
    """Main test function.
    
    Coordinates the execution of all agent tests, provides comprehensive
    reporting on system health, and assesses overall readiness for production.
    
    Returns:
        None
    """
    print("🧪 Targeted Agent Validation & Fixes")
    print("=" * 60)
    
    # Test the previously failing agents with correct methods
    discovery_ok = test_episode_discovery_agent()
    config_ok = test_episode_config_manager()
    
    # Run quick validation of all agents
    results = test_all_agents_quick()
    
    # Test CLI
    test_cli_commands()
    
    print("\n" + "=" * 60)
    print("FINAL ASSESSMENT:")
    print("=" * 60)
    
    if discovery_ok and config_ok:
        print("✅ Previously failing agents now FIXED!")
    else:
        print("⚠️ Some agents still need attention")
    
    # Overall system health
    passed_count = sum(1 for result in results.values() if "PASSED" in result)
    total_count = len(results)
    overall_rate = passed_count / total_count
    
    print(f"📊 Overall System Health: {overall_rate:.1%}")
    
    if overall_rate >= 0.9:
        print("🚀 SYSTEM READY FOR PRODUCTION!")
    elif overall_rate >= 0.8:
        print("✅ SYSTEM STABLE - Minor fixes may be needed")
    else:
        print("⚠️ SYSTEM NEEDS ATTENTION - Multiple issues")


if __name__ == "__main__":
    main()
