#!/usr/bin/env python
"""
Test runner script for Phase 3 tests
Usage: python run_tests.py [options]
"""
import sys
import os
import django
from django.conf import settings
from django.test.utils import get_runner

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aiagentplatform.settings')
django.setup()


def run_tests():
    """Run all Phase 3 tests"""
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=False, keepdb=False)
    
    # Specify test labels
    test_labels = [
        'agents.tests.test_agent_factory',
        'agents.tests.test_integrations',
        'agents.tests.test_performance',
    ]
    
    print("=" * 70)
    print("RUNNING PHASE 3 TESTS")
    print("=" * 70)
    print(f"Test modules: {len(test_labels)}")
    print()
    
    failures = test_runner.run_tests(test_labels)
    
    print()
    print("=" * 70)
    if failures:
        print(f"TESTS FAILED: {failures} failure(s)")
        print("=" * 70)
        sys.exit(1)
    else:
        print("ALL TESTS PASSED ✓")
        print("=" * 70)
        sys.exit(0)


def run_specific_tests(test_type):
    """Run specific type of tests"""
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=False, keepdb=False)
    
    test_mapping = {
        'factory': ['agents.tests.test_agent_factory.AgentFactoryCreationTests',
                   'agents.tests.test_agent_factory.AgentFactoryExecutionTests'],
        'tools': ['agents.tests.test_agent_factory.ToolRegistryTests'],
        'integrations': ['agents.tests.test_integrations.IntegrationModelTests',
                        'agents.tests.test_integrations.IntegrationViewTests'],
        'performance': ['agents.tests.test_performance.PerformanceTests'],
        'security': ['agents.tests.test_performance.SecurityTests'],
        'memory': ['agents.tests.test_performance.MemoryTests'],
        'errors': ['agents.tests.test_performance.ErrorHandlingTests'],
    }
    
    if test_type not in test_mapping:
        print(f"Unknown test type: {test_type}")
        print(f"Available types: {', '.join(test_mapping.keys())}")
        sys.exit(1)
    
    test_labels = test_mapping[test_type]
    
    print("=" * 70)
    print(f"RUNNING {test_type.upper()} TESTS")
    print("=" * 70)
    
    failures = test_runner.run_tests(test_labels)
    
    if failures:
        print(f"\n{test_type.upper()} TESTS FAILED: {failures} failure(s)")
        sys.exit(1)
    else:
        print(f"\n{test_type.upper()} TESTS PASSED ✓")
        sys.exit(0)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        test_type = sys.argv[1]
        run_specific_tests(test_type)
    else:
        run_tests()