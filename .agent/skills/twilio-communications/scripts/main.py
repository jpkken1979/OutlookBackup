#!/usr/bin/env python3
"""Skill: twilio-communications"""
import argparse
import logging
import sys

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Skill: twilio-communications")
    parser.parse_args()
    logger.info("Skill %s invoked", "twilio-communications")
    return 0

if __name__ == "__main__":
    sys.exit(main())
