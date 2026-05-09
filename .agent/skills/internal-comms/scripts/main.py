#!/usr/bin/env python3
"""Skill: internal-comms"""
import argparse
import logging
import sys

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Skill: internal-comms")
    parser.parse_args()
    logger.info("Skill %s invoked", "internal-comms")
    return 0

if __name__ == "__main__":
    sys.exit(main())
