"""PythonAnywhere WSGI entrypoint.

In the PythonAnywhere WSGI configuration file, add this project directory to
sys.path and import `application` from this file.
"""
from app import app as application
