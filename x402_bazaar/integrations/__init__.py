"""Optional integrations for AI frameworks."""

__all__: list[str] = []

try:
    from .langchain import X402CallTool as LangChainCallTool, X402SearchTool

    __all__.extend(["X402SearchTool", "LangChainCallTool"])
except ImportError:
    pass

try:
    from .crewai import X402CallTool as CrewAICallTool, X402SearchTool as CrewAISearchTool

    __all__.extend(["CrewAISearchTool", "CrewAICallTool"])
except ImportError:
    pass
