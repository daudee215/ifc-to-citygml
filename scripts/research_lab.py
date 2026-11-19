"""Run the modular research implementation without changing frozen installation."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src')]

def main():
    import argparse
    from ifc_citygml.common import write_json
    parser=argparse.ArgumentParser(description='IFC to CityGML research laboratory')
    commands=parser.add_subparsers(dest='command',required=True)
    prepare=commands.add_parser('prepare');prepare.add_argument('kind',choices=['gaps','smoke','development','locked']);prepare.add_argument('--output',required=True);prepare.add_argument('--count',type=int)
    benchmark=commands.add_parser('benchmark');benchmark.add_argument('manifest');benchmark.add_argument('--output',required=True);benchmark.add_argument('--workers',type=int,default=2);benchmark.add_argument('--backends',nargs='+');benchmark.add_argument('--samples',type=int,default=128)
    convert=commands.add_parser('convert');convert.add_argument('input');convert.add_argument('--output',required=True);convert.add_argument('--backend',default='guarded')
    contracts=commands.add_parser('contracts');contracts.add_argument('--output',required=True)
    for name in ['inventory','torino-context']:
        command=commands.add_parser(name);command.add_argument('--output',required=True)
    coordinate=commands.add_parser('coordinates');coordinate.add_argument('input');coordinate.add_argument('--output',required=True)
    annotate=commands.add_parser('annotation-template');annotate.add_argument('report');annotate.add_argument('--output',required=True)
    semantic=commands.add_parser('evaluate-semantics');semantic.add_argument('report');semantic.add_argument('annotations');semantic.add_argument('--output',required=True)
    args=parser.parse_args()
    if args.command=='prepare':
        from ifc_citygml_lab.fixtures import prepare_suite
        result=prepare_suite(args.output,args.kind,args.count);print('Prepared',len(result['cases']),'inputs')
    elif args.command=='benchmark':
        from ifc_citygml_lab.benchmark import run
        result=run(args.manifest,args.output,args.backends,args.workers,args.samples);print('Completed',result['attempts'],'attempts')
    elif args.command=='contracts':
        from ifc_citygml_lab.contracts import default_contracts
        write_json(Path(args.output),default_contracts());print(args.output)
    elif args.command=='convert':
        from ifc_citygml_lab.geometry import convert_research
        result,data=convert_research(Path(args.input),args.backend);path=Path(args.output)
        if path.exists() or path.with_suffix('.report.json').exists():raise FileExistsError('Do not overwrite research artifacts')
        path.parent.mkdir(parents=True,exist_ok=True)
        if data:
            path=path if result['status']=='accepted' else path.with_suffix('.'+result['status']+'.gml')
            if path.exists() or path.with_suffix('.report.json').exists():raise FileExistsError('Preserve prior candidate and report')
            path.write_bytes(data)
        write_json(path.with_suffix('.report.json'),result);print(result['status'],path)
    elif args.command in ['inventory','torino-context','coordinates']:
        if Path(args.output).exists():raise FileExistsError('Preserve existing evidence')
        if args.command=='inventory':
            from ifc_citygml_lab.corpus import inventory
            result=inventory(ROOT)
        elif args.command=='torino-context':
            from ifc_citygml_lab.urban import torino_context
            result=torino_context(ROOT)
        else:
            from ifc_citygml_lab.coordinates import audit_chain
            result=audit_chain(args.input)
        write_json(Path(args.output),result);print(args.output)
    elif args.command in ['annotation-template','evaluate-semantics']:
        import json,csv
        from ifc_citygml_lab.semantics import export_annotation_csv,face_predictions,evaluate_annotations
        if Path(args.output).exists():raise FileExistsError('Preserve existing evidence')
        result=json.loads(Path(args.report).read_text())
        if args.command=='annotation-template':export_annotation_csv(args.output,result)
        else:
            with open(args.annotations,encoding='utf-8',newline='') as f:references=list(csv.DictReader(f))
            write_json(Path(args.output),evaluate_annotations(face_predictions(result),references))
        print(args.output)

if __name__=='__main__':main()
