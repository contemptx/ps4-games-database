"""Dispatch deployment and a finite number of resumable metadata batches."""
import os
import subprocess
n=int(os.environ['BATCHES_LEFT'])
if not 1<=n<=120: raise ValueError('Batch count outside 1-120')
subprocess.run(['gh','workflow','run','static.yml','--ref','main'],check=True)
if os.environ.get('CAN_CONTINUE')=='true' and n>1:
    subprocess.run(['gh','workflow','run','file-sizes.yml','--ref','main','-f','batches_left='+str(n-1)],check=True)
    print('Next size batch dispatched')
else: print('Size pass stopped: no runnable queue or batch budget reached')
