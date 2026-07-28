"""
Global utility classes and functions
"""
from typing import NamedTuple

class Limits(NamedTuple):
    """
    Named tuple to indicate upper and lower limits of a parameter.
    """
    min : float
    max : float