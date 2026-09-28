#!/usr/bin/env python3
"""Explicitly dispatch Pages and the next finite processing batch."""
import os
import subprocess


def main():
    budget = int(os.environ['BATCHES_LEFT'])
    if not 1 <= budget <= 120:
        raise ValueError('Batch budget must be 1–120')
    subprocess.run(['gh', 'workflow', 'run', 'static.yml', '--ref', 'main'], check=True)
    if os.environ.get('CAN_CONTINUE') == 'true' and budget > 1:
        subprocess.run(['gh', 'workflow', 'run', 'full-index.yml', '--ref', 'main',
                        '-f', 'limit=100', '-f', 'batches_left=' + str(budget - 1)], check=True)
        print('Next batch dispatched; remaining batch budget: ' + str(budget - 1))
    else:
        print('Processing stopped: queues finished/paused, no progress, or batch budget reached.')


if __name__ == '__main__':
    main()
