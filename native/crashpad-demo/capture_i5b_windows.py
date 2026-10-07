#!/usr/bin/env python3
"""Create six owned local I5b Windows captures; uploads remain disabled."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from run_windows import sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if sys.platform!='win32': parser.error('native Windows Python is required')
    records=[]
    for label,profile in [('positive','zero-base-offset'),('refuted','null-write'),('unknown','zero-base-offset-indexed')]:
        for mode in ['partial','full']:
            directory=args.output/(label+'-'+mode)
            if not directory.exists():
                subprocess.run([sys.executable,str(Path(__file__).with_name('run_windows.py')),
                    '--build',str(args.build),'--output',str(directory),'--mode',mode,'--profile',profile,
                    '--minimal-environment','--check-failures'],check=True)
            record=json.loads((directory/'capture.json').read_text())
            if (record['buildRecordSha256']!=sha(args.build) or record['mode']!=mode
                or record['profile']!=profile or record['uploadsEnabled'] is not False
                or record['childEnvironment']['policy']!='minimal-windows/v1'
                or record['dump']['sha256']!=sha(directory/'capture.dmp')):
                raise RuntimeError('existing capture is not the exact requested owned case: '+str(directory))
            records.append(dict(label=label,mode=mode,path=str(directory.resolve()),capture=record))
            print(label,mode,'capture verified',flush=True)
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'i5b-capture-bundle.json').write_text(json.dumps(dict(
        schema='ariadne.i5b-capture-bundle/v1',buildSha256=sha(args.build),cases=records),indent=2)+'\n')


if __name__=='__main__': main()
