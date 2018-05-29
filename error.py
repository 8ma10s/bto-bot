class DirectoryNotFoundError(Exception):
    """Exception thrown when a specified directory is not found"""
class FileNotFoundError(Exception):
    """Exception thrown when a specified file is not found"""

class NotADirectoryError(Exception):
    """Exception thrown when a specified directory is a file"""

class InvalidParametersError(Exception):
    """Exception thrown when parameter(s) passed to a function is invalid"""