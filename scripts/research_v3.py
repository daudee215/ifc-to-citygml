from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'research'),str(ROOT/'src')]
def main():
    import argparse
    from ifc_citygml.common import write_json
    p=argparse.ArgumentParser(description='Evidence-constrained IFC to CityGML V3 research')
    sub=p.add_subparsers(dest='command',required=True)
    prepare=sub.add_parser('prepare');prepare.add_argument('--partition',choices=['development','holdout'],required=True);prepare.add_argument('--count',type=int,required=True);prepare.add_argument('--output',required=True)
    benchmark=sub.add_parser('benchmark');benchmark.add_argument('manifest');benchmark.add_argument('--output',required=True);benchmark.add_argument('--workers',type=int,default=3)
    conversion=sub.add_parser('convert');conversion.add_argument('input');conversion.add_argument('--output',required=True);conversion.add_argument('--policy');conversion.add_argument('--experimental-ifc43',action='store_true')
    general=sub.add_parser('generalise');general.add_argument('report');general.add_argument('--contract');general.add_argument('--output',required=True)
    incremental=sub.add_parser('update');incremental.add_argument('input');incremental.add_argument('--cache',required=True);incremental.add_argument('--output',required=True);incremental.add_argument('--skip-rebuild-verification',action='store_true')
    tracing=sub.add_parser('trace');tracing.add_argument('report');tracing.add_argument('--guid');tracing.add_argument('--output',required=True)
    agreement=sub.add_parser('review-agreement');agreement.add_argument('first');agreement.add_argument('second');agreement.add_argument('--output',required=True)
    evaluate=sub.add_parser('evaluate-review');evaluate.add_argument('report');evaluate.add_argument('annotations');evaluate.add_argument('--output',required=True)
    template=sub.add_parser('review-template');template.add_argument('report');template.add_argument('--output',required=True)
    sensitivity=sub.add_parser('sensitivity');sensitivity.add_argument('profiles');sensitivity.add_argument('hazard');sensitivity.add_argument('--crs',required=True);sensitivity.add_argument('--coordinate-status',required=True);sensitivity.add_argument('--offsets',required=True);sensitivity.add_argument('--provenance',required=True);sensitivity.add_argument('--output',required=True)
    diagnostic=sub.add_parser('topology');diagnostic.add_argument('input');diagnostic.add_argument('--output',required=True)
    args=p.parse_args()
    if args.command=='prepare':
        from ifc_citygml_v3.fixtures import prepare
        if args.count<1:raise ValueError('Positive count required')
        r=prepare(args.output,args.partition,args.count);print('Prepared',len(r['cases']),args.partition,'cases')
    elif args.command=='benchmark':
        from ifc_citygml_v3.safe_benchmark import run
        r=run(args.manifest,args.output,args.workers);print('Completed',r['attempts'],'attempts')
    elif args.command=='convert':
        from ifc_citygml_v3.converter import convert
        from ifc_citygml_v3.policy import Policy
        folder=Path(args.output)
        if folder.exists():raise FileExistsError('Preserve existing artifacts')
        folder.mkdir(parents=True);policy=Policy.from_dict(json.loads(Path(args.policy).read_text())) if args.policy else Policy()
        from ifc_citygml_v3.source43 import extract_sources
        source=extract_sources(args.input,allow_ifc43=args.experimental_ifc43)
        r,data=convert(args.input,policy,source)
        if data:(folder/('model.'+r['status']+'.gml')).write_bytes(data)
        write_json(folder/'report.json',r);print(r['status'])
    elif args.command=='generalise':
        from ifc_citygml_v3.generalisation import choose,QueryContract
        folder=Path(args.output)
        if folder.exists():raise FileExistsError('Preserve existing artifacts')
        folder.mkdir(parents=True);contract=QueryContract(**json.loads(Path(args.contract).read_text())) if args.contract else QueryContract()
        r,outputs=choose(json.loads(Path(args.report).read_text()),contract)
        for name,out in outputs.items():
            (folder/(name+'.gml')).write_bytes(out['data']);write_json(folder/(name+'.source_links.json'),out['source_links'])
        write_json(folder/'index.json',r);print(r['status'],r['selected'])
    elif args.command=='update':
        from ifc_citygml_v3.incremental import update
        folder=Path(args.output)
        if folder.exists():raise FileExistsError('Preserve existing outputs')
        folder.mkdir(parents=True);r,data=update(args.input,args.cache,verify_rebuild=not args.skip_rebuild_verification)
        if data:(folder/('model.'+r['status']+'.gml')).write_bytes(data)
        write_json(folder/'report.json',r);print(r['status'],r['incremental']['strategy'])
    else:
        if Path(args.output).exists():raise FileExistsError('Preserve existing evidence')
        if args.command=='trace':
            from ifc_citygml_v3.trace import query_guid,jsonld
            report=json.loads(Path(args.report).read_text());r=query_guid(report,args.guid) if args.guid else jsonld(report)
        elif args.command=='review-agreement':
            import csv
            from ifc_citygml_v3.annotations import reviewer_agreement
            with open(args.first,newline='',encoding='utf-8') as f:first=list(csv.DictReader(f))
            with open(args.second,newline='',encoding='utf-8') as f:second=list(csv.DictReader(f))
            r=reviewer_agreement(first,second)
        elif args.command=='review-template':
            import csv
            from ifc_citygml_lab.semantics import annotation_template
            report=json.loads(Path(args.report).read_text());rows=annotation_template(report)
            for row in rows:row.update(input_sha256=report['input_sha256'],output_sha256=report.get('output_sha256',''))
            with open(args.output,'w',newline='',encoding='utf-8') as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['input_sha256','output_sha256','region_id','reference_label']);writer.writeheader();writer.writerows(rows)
            print('Blank scoped review template:',args.output);return
        elif args.command=='sensitivity':
            from ifc_citygml_v3.sensitivity import profile_sensitivity
            r=profile_sensitivity(json.loads(Path(args.profiles).read_text()),json.loads(Path(args.hazard).read_text()),args.crs,args.coordinate_status,json.loads(args.offsets),args.provenance)
        elif args.command=='topology':
            from ifc_citygml_v3.diagnostics import topology
            from ifc_citygml_lab.metrics import read_geometry
            r=topology(read_geometry(Path(args.input).read_bytes())['mesh'])
        else:
            import csv
            from ifc_citygml_v3.annotations import evaluate_scoped
            with open(args.annotations,newline='',encoding='utf-8') as f:references=list(csv.DictReader(f))
            r=evaluate_scoped(json.loads(Path(args.report).read_text()),references)
        write_json(Path(args.output),r);print(args.output)
if __name__=='__main__':main()
