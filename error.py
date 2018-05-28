class DirectoryNotFoundError(Exception):
    """Exception thrown when a specified directory is not found"""
class FileNotFoundError(Exception):
    """Exception throw when a specified file is not found"""

class NotADirectoryError(Exception):
    """Exception thrown when a specified directory is a file"""