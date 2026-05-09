#!/usr/bin/env python3
"""Skill: openai-speech"""
import argparse
import logging
import sys

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Skill: openai-speech")
    parser.parse_args()
    logger.info("Skill %s invoked", "openai-speech")
    return 0

if __name__ == "__main__":
    sys.exit(main())
