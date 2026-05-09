#!/usr/bin/env python3
"""Skill: fp-ts-errors"""
import argparse
import logging
import sys

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Skill: fp-ts-errors")
    parser.parse_args()
    logger.info("Skill %s invoked", "fp-ts-errors")
    return 0

if __name__ == "__main__":
    sys.exit(main())
