#!/usr/bin/env python3
"""Skill: remote-control"""
import argparse
import logging
import sys

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Skill: remote-control")
    parser.parse_args()
    logger.info("Skill %s invoked", "remote-control")
    return 0

if __name__ == "__main__":
    sys.exit(main())
