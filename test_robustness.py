"""
Test script to verify the robustness of the Compensation Aggregator application.
Tests error handling, retry mechanisms, and configuration loading.
"""

import unittest
import logging
import time
import os
import sys
import requests
from unittest.mock import patch, MagicMock

# Configure basic logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import application modules
import config
import error_utils
import html_to_markdown
from html_to_markdown import convert_to_markdown, fallback_html_to_markdown

class TestErrorHandling(unittest.TestCase):
    """Test the error handling utilities."""
    
    def test_application_error(self):
        """Test the ApplicationError class."""
        # Create an original error
        original = ValueError("Original error")
        
        # Create an application error with the original error
        app_error = error_utils.ApplicationError("Application error", original)
        
        # Check error properties
        self.assertEqual(app_error.message, "Application error")
        self.assertEqual(app_error.original_error, original)
        self.assertEqual(str(app_error), "Application error")
    
    def test_with_logging_decorator(self):
        """Test the with_logging decorator."""
        # Create a test function with the decorator
        @error_utils.with_logging
        def test_func(x, y):
            return x + y
        
        # Call the function and check the result
        result = test_func(2, 3)
        self.assertEqual(result, 5)
        
        # Test with exception
        @error_utils.with_logging
        def failing_func():
            raise ValueError("Test error")
        
        # The function should still raise the exception
        with self.assertRaises(ValueError):
            failing_func()
    
    def test_with_retry_decorator(self):
        """Test the with_retry decorator."""
        # Create a test function that fails twice then succeeds
        attempts = []
        
        def test_func():
            attempts.append(1)
            if len(attempts) < 3:
                raise ValueError(f"Failure {len(attempts)}")
            return "success"
        
        # Give the function a name attribute
        test_func.__name__ = "test_func"
        
        # Apply the retry decorator
        decorated_func = error_utils.with_retry(
            max_attempts=3,
            backoff_factor=0.1,  # Small backoff for faster tests
            exceptions=(ValueError,)
        )(test_func)
        
        # Call the function and check the result
        result = decorated_func()
        self.assertEqual(result, "success")
        self.assertEqual(len(attempts), 3)
        
        # Test with all attempts failing
        attempts.clear()
        
        def always_fails():
            attempts.append(1)
            raise ValueError("Always fails")
        
        always_fails.__name__ = "always_fails"
        
        # Apply the retry decorator
        failing_func = error_utils.with_retry(
            max_attempts=3,
            backoff_factor=0.1,
            exceptions=(ValueError,)
        )(always_fails)
        
        # The function should raise the exception after all attempts
        with self.assertRaises(ValueError):
            failing_func()
        
        # Should have tried the maximum number of times
        self.assertEqual(len(attempts), 3)
    
    def test_safe_execute(self):
        """Test the safe_execute function."""
        # Test with a function that succeeds
        def success_func():
            return "success"
        
        result = error_utils.safe_execute(success_func)
        self.assertEqual(result, "success")
        
        # Test with a function that fails
        def failing_func():
            raise ValueError("Test error")
        
        # Should return the default value
        result = error_utils.safe_execute(failing_func, default_value="default")
        self.assertEqual(result, "default")
        
        # Test with a function that fails and no default value
        result = error_utils.safe_execute(failing_func)
        self.assertIsNone(result)

class TestConfiguration(unittest.TestCase):
    """Test the configuration module."""
    
    def test_load_config(self):
        """Test loading configuration."""
        # Get the full configuration
        full_config = config.get_config()
        
        # Check that all expected sections are present
        expected_sections = [
            "base_dir", "app_env", "logging", "streamlit", 
            "scraping", "api", "data_processing", "env"
        ]
        for section in expected_sections:
            self.assertIn(section, full_config)
        
        # Test getting a specific section
        scraping_config = config.get_config("scraping")
        self.assertIn("default_max_depth", scraping_config)
        self.assertIn("default_max_breadth", scraping_config)
        
        # Test getting a non-existent section
        nonexistent = config.get_config("nonexistent")
        self.assertEqual(nonexistent, {})

class MockResponse:
    """Mock response object for testing."""
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code
    
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP Error: {self.status_code}")

class TestHtmlToMarkdown(unittest.TestCase):
    """Test the HTML to Markdown conversion with error handling."""
    
    @patch('html_to_markdown.requests.get')
    def test_convert_to_markdown_with_valid_url(self, mock_get):
        """Test converting a valid URL to markdown."""
        # Configure the mock response
        mock_get.return_value = MockResponse("# Test Markdown")
        
        # Call the function
        result = html_to_markdown.convert_to_markdown("https://example.com")
        
        # Check the result
        self.assertEqual(result, "# Test Markdown")
        
        # Verify the mock was called
        mock_get.assert_called_once()
    
    @patch('html_to_markdown.retry_with_backoff', side_effect=lambda *args, **kwargs: lambda f: f)
    @patch('html_to_markdown.requests.get')
    @patch('html_to_markdown.fallback_html_to_markdown')
    def test_convert_to_markdown_with_error(self, mock_fallback, mock_get, mock_retry):
        """Test handling errors in markdown conversion."""
        # Configure the mock to raise an exception
        mock_get.side_effect = requests.RequestException("Test error")
        
        # Configure the fallback to return a specific value
        mock_fallback.return_value = "Fallback content"
        
        # Call the function
        result = html_to_markdown.convert_to_markdown("https://example.com")
        
        # Check that the fallback content was returned
        self.assertEqual(result, "Fallback content")
        
        # Verify the fallback was called
        mock_fallback.assert_called_once()
        
        # We don't assert on mock_get.assert_called_once() because the retry logic
        # may cause it to be called multiple times

def run_tests():
    """Run all tests."""
    # Create a test suite with all test cases
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(TestErrorHandling))
    test_suite.addTest(unittest.makeSuite(TestConfiguration))
    test_suite.addTest(unittest.makeSuite(TestHtmlToMarkdown))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Return success/failure
    return result.wasSuccessful()

if __name__ == "__main__":
    # Configure logging
    config.configure_logging()
    
    # Run the tests
    success = run_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)
