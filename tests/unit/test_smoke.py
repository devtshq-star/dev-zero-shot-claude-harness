def test_package_importable():
    from config.settings import get_settings  # noqa: F401
    from api._common import ok              # noqa: F401
    from db.models import Base              # noqa: F401
    from graph.agent import agentic_ai      # noqa: F401
    from tools.csv_profiling import profile_dataframe  # noqa: F401
    from tools.code_sandbox import execute_code        # noqa: F401
