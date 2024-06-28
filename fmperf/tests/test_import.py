import unittest
import logging


# Configure logging
logging.basicConfig(filename='test_logs.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s:%(message)s', filemode='w')
logging.debug('Logging configured successfully')

# Test class to check if the imports are working for the files in the examples folder
class TestImports(unittest.TestCase):
    def setUp(self):
        # Setup code goes here
        logging.info("Running a test case.")

    def tearDown(self):
        # Teardown code can go here, if we needed to clean up after tests
        pass

    def test_fmperf_import(self):
        """Test if fmperf import works correctly."""
        try:
            import fmperf
            self.assertIsNotNone(fmperf)
            logging.info("test_fmperf_import passed.")
        except Exception as e:
            logging.error(f"test_fmperf_import failed: {e}")
            raise

if __name__ == '__main__':
    unittest.main()
    logging.getLogger().handlers[0].flush()
