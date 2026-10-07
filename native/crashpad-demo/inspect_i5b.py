#!/usr/bin/env python3
"""Independent raw minidump/PE oracle for three exact controlled I5b recipes."""
import argparse
import json
from pathlib import Path
from inspect_capture import BinaryFile, Minidump, PortableExecutable, require, unique_object, witness_address

RECIPES={
    'ariadne-crashpad-zero-base-offset-v1':('c7410805000000',8,'consistent_with_evidence'),
    'ariadne-crashpad-null-write-v1':('c70105000000',0,'refuted_under_premises'),
    'ariadne-crashpad-zero-base-offset-indexed-v1':('c744110805000000',8,'unknown'),
}


def inspect(directory):
    records=[]
    try:
        for name in ['capture.dmp','witness.json','ariadne_crash_demo.exe']:
            records.append(BinaryFile(directory/name))
        dump_raw,witness_raw,pe_raw=records
        require(witness_raw.size<=16384,'oversized witness')
        witness=json.loads(witness_raw.read(0,witness_raw.size,'witness'),object_pairs_hook=unique_object)
        profile=witness['integration_profile']
        require(profile in RECIPES,'unsupported controlled profile')
        encoding,expected_address,expected_conclusion=RECIPES[profile]
        require(witness['expected_access']=='write' and witness['expected_width_bytes']==4
            and witness['expected_store_value']==5 and witness['explicit_code_range_registered'] is True,
            'wrong intended controlled access')
        require(int(witness['expected_data_address'],16)==expected_address,'wrong intended data address')
        dump=Minidump(dump_raw)
        system=dump.system()
        require(dump.process_id()==witness['process_id'],'process identity differs')
        stream=dump.stream(6,168)
        thread,alignment,code,flags,chain,site,count,unused=dump_raw.unpack('<IIIIQQII',stream.offset,'exception')
        require(code==0xc0000005 and flags in [0,1] and chain==0 and count==2
            and alignment==unused==0,'unsupported exception record')
        operation,data_address=dump_raw.unpack('<QQ',stream.offset+40,'AV parameters')
        require(operation==1 and data_address==expected_address,'observed access differs from recipe')
        size,offset=dump.location(stream.offset+160,'exception context')
        require(1232<=size<=65536,'unsupported context extent')
        context_flags,=dump_raw.unpack('<I',offset+48,'context flags')
        require(context_flags & 0x00ff0000==0x00100000 and context_flags & 3==3,'invalid context groups')
        rcx,rdx=dump_raw.unpack('<QQ',offset+128,'RCX/RDX observations')
        rip,=dump_raw.unpack('<Q',offset+248,'RIP observation')
        require(rip==site and rcx==0,'fault-site/base observation differs')
        if expected_conclusion=='unknown': require(rdx==0,'indexed control has nonzero index')
        entry=witness_address(witness['fault_function_entry'],'entry')
        require(entry==site,'controlled assembly entry is not the fault site')
        module=dump.module(entry,site)
        pe=PortableExecutable(pe_raw)
        require(module['timestamp']==pe.timestamp and module['size_of_image']==pe.image_size,'PE metadata mismatch')
        dump.memory(thread)
        full=witness['dump_mode']=='full'
        require(witness['dump_mode'] in ['partial','full'] and dump.header['mini_dump_with_full_memory']==full,'wrong dump mode')
        require((9 in dump.streams and 5 not in dump.streams) if full else (5 in dump.streams and 9 not in dump.streams),'wrong memory stream')
        code_bytes,capture=dump.read_code(site,len(bytes.fromhex(encoding))+1)
        require(code_bytes==bytes.fromhex(encoding+'c3'),'captured encoding differs from hand-reviewed recipe')
        pe_bytes,mapping=pe.code(site-module['base_address'],len(code_bytes))
        require(code_bytes==pe_bytes,'captured instructions differ from PE bytes')
        return dict(schema='ariadne.i5b-controlled-inspection/v1',passed=True,profile=profile,
            expectedConclusion=expected_conclusion,mode=witness['dump_mode'],system=system,
            inputs={name:record.identity() for name,record in zip(['dump','witness','executable'],records)},
            query=dict(entry=f'0x{entry:016x}',site=f'0x{site:016x}',memory_access=0),
            observed=dict(exceptionCode=code,operation=operation,dataAddress=data_address,rcx=rcx,rdx=rdx,rip=rip,
                contextFlags=context_flags,exceptionOffset=stream.offset,contextOffset=offset,contextBytes=size),
            instruction=dict(bytes=encoding,base='rcx',displacement=expected_address,
                index='rdx' if expected_conclusion=='unknown' else None,accessWidth=32,role='store'),
            capture=capture,peComparison=dict(mapping=mapping,bytes=pe_bytes.hex(),equal=True),
            scope='Exact controlled raw-file/PE recipe inspection; no Ariadne/BAP invocation, history, root cause or timing qualification.')
    finally:
        for record in records: record.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    record=inspect(args.capture)
    args.output.write_text(json.dumps(record,indent=2)+'\n')
    print('Independent I5b capture inspection PASS:',args.output)


if __name__=='__main__': main()
