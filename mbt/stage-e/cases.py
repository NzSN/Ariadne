"""Deterministic Stage E inputs and TLA tables; never imports or executes Rust."""
from copy import deepcopy
import json
import hashlib
import os
from pathlib import Path
import subprocess


def va(address): return f"0x{address:016x}"
def edge(src, dst, kind="next"): return {"src":va(src),"dst":va(dst),"kind":kind}
def ms_base():
    values={"rax":["zero","five","other"],"zf":["false","true"]}
    states={"entry":{"status":"running","valuation":deepcopy(values)},
            "rax-five":{"status":"running","valuation":{"rax":["five"],"zf":["false","true"]}},
            "zf-true":{"status":"running","valuation":{"rax":["five"],"zf":["true"]}},
            "returned":{"status":"returned","valuation":{"rax":["five"],"zf":["true"]}}}
    effects=[{"va":va(a),"uses":[],"must_defs":[],"may_defs":[]} for a in range(1,6)]
    effects[0].update(must_defs=["rax"],may_defs=["rax"])
    effects[1].update(uses=["rax"],must_defs=["zf"],may_defs=["zf"])
    effects[2]["uses"]=["zf"]
    return {"schema":"ariadne.machine-state-request/v1","snapshot_id":"machine-state-snapshot",
            "nodes":[va(a) for a in range(1,6)],"structural_edges":[edge(1,2),edge(2,3),edge(3,4,"taken"),edge(3,5,"fallthrough")],
            "value_domain":values,"catalogue":states,"effects":effects,
            "entry_states":[{"va":va(1),"states":["entry"]}],
            "steps":[{"edge":edge(1,2),"before":"entry","after":"rax-five"},{"edge":edge(2,3),"before":"rax-five","after":"zf-true"},{"edge":edge(3,4,"taken"),"before":"zf-true","after":"zf-true"}],
            "terminal_transitions":[{"site":va(a),"before":"zf-true","after":"returned","outcome":"returned"} for a in [4,5]],
            "complete_sites":[va(a) for a in range(1,6)],"adapter_obligations":[]}


def machine_cases():
    base=ms_base(); cases={"MachineStateReplay":base}
    def add(name,edit):
        request=deepcopy(base); request["snapshot_id"]+="/"+name; edit(request); cases[name]=request
    add("MSIncomplete",lambda r:r["complete_sites"].remove(va(3)))
    add("MSEmptyRoots",lambda r:r.update(entry_states=[]))
    add("MSMultipleRoots",lambda r:r["entry_states"].append({"va":va(5),"states":["zf-true"]}))
    def join(r):r["steps"].append({"edge":edge(3,5,"fallthrough"),"before":"zf-true","after":"zf-true"})
    add("MSBothBranches",join)
    def loop(r):
        r["structural_edges"].append(edge(4,3));r["steps"].append({"edge":edge(4,3),"before":"zf-true","after":"zf-true"})
    add("MSLoop",loop)
    def self_loop(r):
        r["structural_edges"].append(edge(4,4));r["steps"].append({"edge":edge(4,4),"before":"zf-true","after":"zf-true"})
    add("MSSelfLoop",self_loop)
    def aliases(r):
        r["catalogue"]["twin"]=deepcopy(r["catalogue"]["zf-true"])
        r["steps"].append({"edge":edge(2,3),"before":"rax-five","after":"twin"})
        r["steps"].append({"edge":edge(3,5,"fallthrough"),"before":"twin","after":"twin"})
    add("MSEqualValuations",aliases)
    def terminals(r):
        for outcome in ["faulted","stopped"]:
            r["catalogue"][outcome]={"status":outcome,"valuation":deepcopy(r["catalogue"]["returned"]["valuation"])}
            r["terminal_transitions"].append({"site":va(4),"before":"zf-true","after":outcome,"outcome":outcome})
    add("MSTerminalAlternatives",terminals)
    def uncertainty(r):
        r["complete_sites"]=[]
        r["adapter_obligations"]=[{"site":va(5),"reason":reason} for reason in ["unknown-memory","unmodeled-exception","unmodeled-system-call","unmodeled-concurrency"]]
    add("MSUncertainty",uncertainty)
    def summary(r):r["structural_edges"][0]["kind"]="summary";r["steps"][0]["edge"]["kind"]="summary"
    add("MSSummary",summary)
    def relocate(r,offset):
        for field in ["nodes","complete_sites"]:r[field]=[va(int(a,16)+offset) for a in r[field]]
        for field in ["structural_edges"]:
            for e in r[field]:e["src"]=va(int(e["src"],16)+offset);e["dst"]=va(int(e["dst"],16)+offset)
        for s in r["steps"]:
            s["edge"]["src"]=va(int(s["edge"]["src"],16)+offset);s["edge"]["dst"]=va(int(s["edge"]["dst"],16)+offset)
        for field,key in [("effects","va"),("entry_states","va"),("terminal_transitions","site"),("adapter_obligations","site")]:
            for row in r[field]:row[key]=va(int(row[key],16)+offset)
    add("MSSparse",lambda r:relocate(r,4095))
    add("MSHighVA",lambda r:relocate(r,2**64-6))
    for size in [2,4,8]:
        nodes=[va(a*13) for a in range(1,size+1)]
        r={"schema":base["schema"],"snapshot_id":f"generated-chain-{size}","nodes":nodes,
           "value_domain":{"x":["unknown"]},"catalogue":{s:{"status":"running" if s=="live" else "stopped","valuation":{"x":["unknown"]}} for s in ["live","stop"]},
           "structural_edges":[{"src":a,"dst":b,"kind":"next"} for a,b in zip(nodes,nodes[1:])],
           "entry_states":[{"va":nodes[0],"states":["live"]}],"effects":[{"va":a,"uses":[],"may_defs":[],"must_defs":[]} for a in nodes],
           "steps":[{"edge":{"src":a,"dst":b,"kind":"next"},"before":"live","after":"live"} for a,b in zip(nodes,nodes[1:])],
           "terminal_transitions":[{"site":nodes[-1],"before":"live","after":"stop","outcome":"stopped"}],"complete_sites":nodes,"adapter_obligations":[]}
        cases[f"MSChain{size}"]=r
    return cases


def ir_base():
    def ins(block,index,uses=()):return {"block":block,"index":index,"uses":list(uses),"phi_incoming":[],"memory_preds":[],"call_targets":[]}
    instructions={"entry.br":ins("entry",0,["arg.cond"]),"left.def":ins("left",0),"left.store":ins("left",1,["arg.ptr","left.value"]),"left.br":ins("left",2),"right.def":ins("right",0),"right.store":ins("right",1,["arg.ptr","right.value"]),"right.br":ins("right",2),"join.phi":ins("join",0,["left.value","right.value"]),"join.call":ins("join",1,["joined.value"]),"join.load":ins("join",2,["arg.ptr"]),"join.combine":ins("join",3,["joined.value","loaded.value"]),"join.ret":ins("join",4,["result.value"])}
    instructions["join.phi"]["phi_incoming"]=[{"pred":"left","value":"left.value"},{"pred":"right","value":"right.value"}]
    instructions["join.load"]["memory_preds"]=["left.store","right.store","join.call"]
    instructions["join.call"]["call_targets"]=["possible.callee"]
    return {"schema":"ariadne.llvm-ir-request/v1","artifact_id":"fixture.bc.sha256","module_id":"fixture-module","function_id":"fixture-function","verified_ir":True,"entry_block":"entry",
            "blocks":{"entry":{"terminator":"entry.br","kind":"br","successors":[{"dst":"left","kind":"true"},{"dst":"right","kind":"false"}]},"left":{"terminator":"left.br","kind":"br","successors":[{"dst":"join","kind":"next"}]},"right":{"terminator":"right.br","kind":"br","successors":[{"dst":"join","kind":"next"}]},"join":{"terminator":"join.ret","kind":"ret","successors":[]}},
            "instructions":instructions,"values":{**{v:{"kind":"argument","def_site":"entry.br"} for v in ["arg.cond","arg.ptr"]},**{v:{"kind":"instruction","def_site":i} for v,i in [("left.value","left.def"),("right.value","right.def"),("joined.value","join.phi"),("loaded.value","join.load"),("result.value","join.combine")]}},
            "phi_nodes":["join.phi"],"call_sites":["join.call"],"callees":["possible.callee"],"complete_calls":[],"adapter_obligations":[],"slice_seeds":["join.ret"]}


def ir_cases():
    base=ir_base();cases={"LLVMIRReplay":base}
    def add(name,edit):
        r=deepcopy(base);r["artifact_id"]+="/"+name;edit(r);cases[name]=r
    add("IREmptySeeds",lambda r:r.update(slice_seeds=[]))
    add("IRMultipleSeeds",lambda r:r.update(slice_seeds=["left.store","join.ret"]))
    add("IRCompleteCall",lambda r:r.update(complete_calls=["join.call"]))
    def uncertain(r):r["adapter_obligations"]=[{"site":"join.load","reason":reason} for reason in ["unsupported-instruction","incomplete-semantics","unknown-memory-alias","unmodeled-exception","unmodeled-system-call","unmodeled-concurrency"]]
    add("IRUncertainty",uncertain)
    def missing_memory(r):r["instructions"]["join.load"]["memory_preds"]=[];r["adapter_obligations"]=[{"site":"join.load","reason":"unknown-memory-alias"}]
    add("IRMissingMemory",missing_memory)
    def loop(r):r["blocks"]["right"]["successors"]=[{"dst":"right","kind":"false"},{"dst":"join","kind":"true"}];r["instructions"]["right.br"]["uses"]=["arg.cond"]
    add("IRLoop",loop)
    def two_phi(r):
        for i in r["instructions"].values():
            if i["block"]=="join" and i["index"]>0:i["index"]+=1
        r["instructions"]["join.phi2"]=deepcopy(r["instructions"]["join.phi"]);r["instructions"]["join.phi2"]["index"]=1
        r["values"]["second.joined"]={"kind":"instruction","def_site":"join.phi2"}
        r["phi_nodes"].append("join.phi2");r["instructions"]["join.combine"]["uses"].append("second.joined")
    add("IRTwoPhi",two_phi)
    for term in ["resume","unreachable"]:add("IRExit"+term.title(),lambda r,t=term:r["blocks"]["join"].update(kind=t))
    def invoke(r):
        r["blocks"]["left"]["kind"]="invoke";r["blocks"]["left"]["successors"]=[{"dst":"join","kind":"normal"},{"dst":"error","kind":"unwind"}]
        r["blocks"]["error"]={"terminator":"error.resume","kind":"resume","successors":[]}
        r["instructions"]["error.resume"]={"block":"error","index":0,"uses":[],"phi_incoming":[],"memory_preds":[],"call_targets":[]}
        r["call_sites"].append("left.br");r["instructions"]["left.br"]["call_targets"]=["possible.callee"];r["complete_calls"].append("left.br")
    add("IRInvoke",invoke)
    for count in [2,4,8]:
        instructions={};values={}
        for n in range(count):
            instructions[f"d{n}"]={"block":"entry","index":n,"uses":[] if n==0 else [f"v{n-1}"],"phi_incoming":[],"memory_preds":[],"call_targets":[]}
            values[f"v{n}"]={"kind":"instruction","def_site":f"d{n}"}
        instructions["ret"]={"block":"entry","index":count,"uses":[f"v{count-1}"],"phi_incoming":[],"memory_preds":[],"call_targets":[]}
        cases[f"IRChain{count}"]={"schema":base["schema"],"artifact_id":f"generated-ir-chain-{count}","module_id":"chain","function_id":"f","verified_ir":True,"entry_block":"entry","blocks":{"entry":{"terminator":"ret","kind":"ret","successors":[]}},"instructions":instructions,"values":values,"phi_nodes":[],"call_sites":[],"callees":[],"complete_calls":[],"adapter_obligations":[],"slice_seeds":["ret"]}
    root = Path(__file__).resolve().parents[2]
    helper = Path(os.environ.get("ARIADNE_LLVM_IR", root / "target/ariadne-llvm-ir"))
    version = subprocess.run([str(helper), "--version"], capture_output=True, text=True, check=True).stdout.strip()
    if version != "Ariadne native LLVM IR 20.1.2":
        raise RuntimeError("native case generation requires the pinned LLVM 20.1.2 helper")
    for name in ["diamond.ll", "diamond.bc"]:
        artifact = root / "tests/ir/fixtures" / name
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        output = subprocess.run([str(helper), str(artifact), "diamond"], capture_output=True, text=True, check=True)
        doc = json.loads(output.stdout)
        if doc["verified_ir"] is not True:
            raise RuntimeError("native fixture was not verified")
        cases["IRNative" + ("Text" if name.endswith(".ll") else "Bitcode")] = {
            "schema":base["schema"], "artifact_id":"llvm-ir-artifact-v1:"+digest,
            "module_id":"module:"+digest, "function_id":doc["function_id"], "verified_ir":True,
            "entry_block":doc["entry_block"],
            **{field:{row["id"]:{key:value for key,value in row.items() if key!="id"} for row in doc[field]} for field in ["blocks","instructions","values"]},
            **{field:doc[field] for field in ["phi_nodes","call_sites","callees","complete_calls"]},
            "adapter_obligations":doc["obligations"],"slice_seeds":["i11"],
        }
    return cases


def tla(value):
    if isinstance(value,bool):return "TRUE" if value else "FALSE"
    if isinstance(value,int):
        return str(value) if value <= 2147483647 else "("+tla(value//1000)+" * 1000 + "+str(value%1000)+")"
    if isinstance(value,str):return json.dumps(value)
    if isinstance(value,list):return "{"+", ".join(tla(v) for v in value)+"}"
    if isinstance(value,dict):return "["+", ".join(k+" |-> "+tla(v) for k,v in value.items())+"]"
    raise ValueError(value)


def function(mapping,var="key"):
    if not mapping:return f"[{var} \\in {{}} |-> {{}}]"
    entries=list(mapping.items());body="CASE "+" [] ".join((var+" = "+tla(k)+" -> "+v) for k,v in entries[:-1])+ (" [] " if len(entries)>1 else "")+"OTHER -> "+entries[-1][1]
    if len(entries)==1:body=entries[0][1]
    return f"[{var} \\in {tla(list(mapping))} |-> {body}]"


def tables(cases,machine):
    payloads={}
    for name,r in cases.items():
        if machine:
            a=lambda value:int(value,16)
            nodes=list(map(a,r["nodes"]));cat=r["catalogue"]
            plain=lambda e:{"src":a(e["src"]),"dst":a(e["dst"]),"kind":e["kind"]}
            rows={"Snapshot":tla(r["snapshot_id"]),"Nodes":tla(nodes),"Locations":tla(list(r["value_domain"])),"States":tla(list(cat)),
                  "Domains":function({k:tla(v) for k,v in r["value_domain"].items()}),"Valuations":function({s:function({l:tla(v) for l,v in state["valuation"].items()},"location") for s,state in cat.items()},"state"),"Statuses":function({s:tla(state["status"]) for s,state in cat.items()},"state"),
                  "Roots":tla([a(e["va"]) for e in r["entry_states"]]),"Entries":function({n:tla(next((e["states"] for e in r["entry_states"] if a(e["va"])==n),[])) for n in nodes},"node"),
                  "Edges":tla([plain(e) for e in r["structural_edges"]]),"Steps":tla([{**plain(s["edge"]),"before":s["before"],"after":s["after"]} for s in r["steps"]]),"Terminals":tla([{**t,"site":a(t["site"])} for t in r["terminal_transitions"]]),"Complete":tla(list(map(a,r["complete_sites"]))),"Obligations":tla([{**o,"site":a(o["site"])} for o in r["adapter_obligations"]])}
            for key,field in [("Uses","uses"),("MustDefs","must_defs"),("MayDefs","may_defs")]:rows[key]=function({a(e["va"]):tla(e[field]) for e in r["effects"]},"node")
        else:
            ins=r["instructions"];values=r["values"];blocks=r["blocks"]
            rows={"Artifact":tla(r["artifact_id"]),"Module":tla(r["module_id"]),"Function":tla(r["function_id"]),"Verified":tla(r["verified_ir"]),"Blocks":tla(list(blocks)),"Entry":tla(r["entry_block"]),"Instructions":tla(list(ins)),"Values":tla(list(values))}
            for key,field in [("BlockOf","block"),("Index","index"),("Uses","uses"),("PhiIncoming","phi_incoming"),("MemoryPreds","memory_preds"),("CallTargets","call_targets")]:rows[key]=function({i:tla(v[field]) for i,v in ins.items()},"instruction")
            rows["Terminators"]=function({b:tla(v["terminator"]) for b,v in blocks.items()},"block")
            rows["TermInfo"]=function({b:tla({"kind":v["kind"],"successors":v["successors"]}) for b,v in blocks.items()},"block")
            for key,field in [("ValueKind","kind"),("DefSite","def_site")]:rows[key]=function({v:tla(i[field]) for v,i in values.items()},"value")
            for key,field in [("PhiNodes","phi_nodes"),("CallSites","call_sites"),("Callees","callees"),("CompleteCalls","complete_calls"),("Obligations","adapter_obligations"),("Seeds","slice_seeds")]:rows[key]=tla(r[field])
        payloads[name]=rows
    module="MachineStateCases" if machine else "LLVMIRCases"
    body=[f"---------------- MODULE {module} ----------------","EXTENDS Naturals, FiniteSets","CONSTANT\n  \\* @type: Str;\n  Case", "Cases == "+tla(list(cases))]
    machine_types={"Snapshot":"Str","Nodes":"Set(Int)","Locations":"Set(Str)","States":"Set(Str)","Domains":"Str -> Set(Str)","Valuations":"Str -> (Str -> Set(Str))","Statuses":"Str -> Str","Roots":"Set(Int)","Entries":"Int -> Set(Str)","Edges":"Set({src: Int, dst: Int, kind: Str})","Steps":"Set({src: Int, dst: Int, kind: Str, before: Str, after: Str})","Terminals":"Set({site: Int, before: Str, after: Str, outcome: Str})","Complete":"Set(Int)","Obligations":"Set({site: Int, reason: Str})","Uses":"Int -> Set(Str)","MustDefs":"Int -> Set(Str)","MayDefs":"Int -> Set(Str)"}
    ir_types={"Artifact":"Str","Module":"Str","Function":"Str","Verified":"Bool","Blocks":"Set(Str)","Entry":"Str","Instructions":"Set(Str)","Values":"Set(Str)","BlockOf":"Str -> Str","Index":"Str -> Int","Uses":"Str -> Set(Str)","PhiIncoming":"Str -> Set({pred: Str, value: Str})","MemoryPreds":"Str -> Set(Str)","CallTargets":"Str -> Set(Str)","Terminators":"Str -> Str","TermInfo":"Str -> {kind: Str, successors: Set({dst: Str, kind: Str})}","ValueKind":"Str -> Str","DefSite":"Str -> Str","PhiNodes":"Set(Str)","CallSites":"Set(Str)","Callees":"Set(Str)","CompleteCalls":"Set(Str)","Obligations":"Set({site: Str, reason: Str})","Seeds":"Set(Str)"}
    types=machine_types if machine else ir_types
    for key in next(iter(payloads.values())):
        entries=list(payloads.items());body.append("\\* @type: "+types[key]+";\n"+key+" == CASE "+" [] ".join("Case = "+tla(name)+" -> "+rows[key] for name,rows in entries))
    return "\n".join(body)+"\n=============================================================================\n"
