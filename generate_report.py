#!/usr/bin/env python3
"""Convenience launcher: python generate_report.py [report.xml]"""
import sys

from burp_report.cli import main

if __name__ == "__main__":
    sys.exit(main())
