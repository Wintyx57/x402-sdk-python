"""Optional integrations for AI frameworks."""

__all__: list[str] = []

try:
    from .langchain import X402CallTool as LangChainCallTool  # noqa: F401
    from .langchain import X402SearchTool  # noqa: F401

    __all__.extend(["X402SearchTool", "LangChainCallTool"])
except ImportError:
    pass

try:
    from .crewai import X402CallTool as CrewAICallTool  # noqa: F401
    from .crewai import X402SearchTool as CrewAISearchTool  # noqa: F401

    __all__.extend(["CrewAISearchTool", "CrewAICallTool"])
except ImportError:
    pass
