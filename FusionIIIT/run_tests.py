#!/usr/bin/env python
"""
Simple test runner for health_center tests
Handles import and dependency issues gracefully
"""
import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Fusion.settings.development')

# Setup Django
try:
    django.setup()
except Exception as e:
    print(f"Warning: Django setup encountered error: {e}")
    print("Attempting to continue anyway...")

# Import test runner
try:
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=False, keepdb=True)
    
    # Run tests for health_center
    failures = test_runner.run_tests(["applications.health_center.tests"])
    
    # Exit with proper code
    sys.exit(bool(failures))
except Exception as e:
    print(f"Error running tests: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
