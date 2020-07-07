"""
A wrapper class around all methods exposed in api.py
"""

import types


class ProctoringService:
    """
    An xBlock service for xBlocks to talk to the Proctoring subsystem. This class basically introspects
    and exposes all functions in the api libraries, so it is a direct pass through.

    NOTE: This is a Singleton class. We should only have one instance of it!
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        """
        This is the class factory to make sure this is a Singleton
        """
        if not cls._instance:
            cls._instance = super(ProctoringService, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        """
        Class initializer, which just inspects the libraries and exposes the same functions
        as a direct pass through
        """
        # pylint: disable=import-outside-toplevel
        from edx_proctoring import api as edx_proctoring_api
        self._bind_to_module_functions(edx_proctoring_api)

    def _bind_to_module_functions(self, module):
        """
        Bind module functions. Since we use underscores to mean private methods, let's exclude those.
        """
        for attr_name in dir(module):
            attr = getattr(module, attr_name, None)
            if isinstance(attr, types.FunctionType) and not attr_name.startswith('_'):
                if not hasattr(self, attr_name):
                    setattr(self, attr_name, attr)
