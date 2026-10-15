from pathlib import Path
import hashlib,json,os,subprocess
root=Path('/home/nzsn/Repos/Ariadne-guard-admission-20261014');out=Path('/work/guard-admission-20261014')
row=json.loads((out/'next-blocker.json').read_text())['failure']
snapshot='minidump-captured-amd64-v1:9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab'
identity=hashlib.sha256(snapshot.encode()).hexdigest();runtime=root/'tmp/bap-setup/stable'
text=f"ARIADNE-BAP-LIFT 1 windows-amd64 {identity}\nbatch 0 1\n{row['va']} {row['bytes']}\n"
env={**os.environ,'LD_LIBRARY_PATH':str(runtime/'usr/local/lib')+':'+str(runtime/'usr/lib/x86_64-linux-gnu'),'XDG_STATE_HOME':str(runtime/'state'),'XDG_CACHE_HOME':str(runtime/'cache')}
p=subprocess.run([str(root/'target/ariadne-bap-lift'),str(runtime/'usr/local/lib/bap')],input=text,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=30,check=True)
(out/'next-blocker-bap-input.txt').write_text(text);(out/'next-blocker-bap-output.jsonl').write_text(p.stdout)
(out/'next-blocker-bap-stderr.log').write_text(p.stderr)
rows=[json.loads(s) for s in p.stdout.splitlines()];assert rows[1]['va']==row['va'] and rows[1]['bytes']==row['bytes']
(out/'next-blocker-bil.json').write_text(json.dumps(rows[1],indent=2)+'\n')
print('raw captured BIL saved',row['va'],rows[1]['opcode'],'bytes',row['bytes'],'statements',len(rows[1]['bil']))
