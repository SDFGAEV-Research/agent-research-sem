import unittest


class PublicAPIImportTests(unittest.TestCase):
    def test_core_public_packages_import(self):
        import research_platform.observability.telemetry as telemetry
        import research_platform.reliability.forensics as forensics
        import research_platform.model.serving as model_serving
        import research_platform.operator as operator
        import research_platform.model.request.prompt.runtime as prompt_runtime
        for module in (telemetry, forensics, model_serving, operator, prompt_runtime):
            self.assertIsNotNone(module)


if __name__ == '__main__':
    unittest.main()
