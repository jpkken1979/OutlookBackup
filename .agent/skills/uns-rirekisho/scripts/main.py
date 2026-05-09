#!/usr/bin/env python3
"""Skill: uns-rirekisho"""
import argparse
import logging
import sys

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Skill: uns-rirekisho")
    parser.parse_args()
    logger.info("Skill %s invoked", "uns-rirekisho")
    return 0

if __name__ == "__main__":
    sys.exit(main())
