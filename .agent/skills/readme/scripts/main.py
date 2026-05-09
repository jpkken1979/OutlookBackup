#!/usr/bin/env python3
"""Skill: readme"""
import argparse
import logging
import sys

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Skill: readme")
    parser.parse_args()
    logger.info("Skill %s invoked", "readme")
    return 0

if __name__ == "__main__":
    sys.exit(main())
