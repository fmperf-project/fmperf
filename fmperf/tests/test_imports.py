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

    def test_kubernetes_imports(self):
        """Test if Kubernetes imports work correctly."""
        try:
            import kubernetes
            from kubernetes import client, config
            self.assertIsNotNone(kubernetes)
            self.assertIsNotNone(client)
            self.assertIsNotNone(config)
            logging.info("test_kubernetes_imports passed.")
        except Exception as e:
            logging.error(f"test_kubernetes_imports failed: {e}")
            raise

    def test_fmperf_imports(self):
        """Test if fmperf imports work correctly."""
        try:
            from fmperf import Cluster
            from fmperf import TGISModelSpec, vLLMModelSpec, HomogeneousWorkloadSpec, HeterogeneousWorkloadSpec, RealisticWorkloadSpec
            from fmperf.utils import run_benchmark
            self.assertIsNotNone(Cluster)
            self.assertIsNotNone(TGISModelSpec)
            self.assertIsNotNone(vLLMModelSpec)
            self.assertIsNotNone(HomogeneousWorkloadSpec)
            self.assertIsNotNone(HeterogeneousWorkloadSpec)
            self.assertIsNotNone(RealisticWorkloadSpec)
            self.assertIsNotNone(run_benchmark)
            logging.info("test_fmperf_imports passed.")
        except Exception as e:
            logging.error(f"test_fmperf_imports failed: {e}")
            raise

# Test class to check if kubernetes python API is working
class TestKubernetes(unittest.TestCase):
    def setUp(self):
        # # Setup code goes here. We are assuming a cluster is already created by the user
        logging.info("Running a test case.")

    def tearDown(self):
        # Close the Kubernetes client to release resources
        self.v1.api_client.close()

    def test_kubernetes_connection(self):
        """Test if a Kubernetes client can be established"""
        try:
            from kubernetes import client, config
            config.load_kube_config()
            # Create a Kubernetes API client
            api_client = client.ApiClient()
            # Test connection by retrieving cluster information
            self.v1 = client.CoreV1Api(api_client)
            ret = self.v1.list_pod_for_all_namespaces(watch=False)
            self.assertTrue(ret.items)
            logging.info("test_connection_to_cluster passed.")
        except Exception as e:
            logging.error("test_connection_to_cluster failed.")
            self.fail(f"Failed to connect to Kubernetes cluster: {str(e)}")


if __name__ == '__main__':
    unittest.main()
    logging.getLogger().handlers[0].flush()
