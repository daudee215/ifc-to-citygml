from pathlib import Path
import subprocess,json,hashlib,sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    folder=ROOT/'tools/v3_native';logged='--exact-log' in sys.argv;build=folder/('build_logged' if logged else 'build');build.mkdir(exist_ok=True)
    cgal=next(folder.glob('CGAL-*/include'));boost=next(folder.glob('boost_*/boost')).parent
    source=ROOT/'research/native_v3'/('exact_union_logged.cpp' if logged else 'exact_union.cpp');vcvars=Path('C:/Program Files/Microsoft Visual Studio/18/Community/VC/Auxiliary/Build/vcvars64.bat')
    sdk=folder/'sdk';ucrt=next(sdk.rglob('assert.h')).parent;include=[ucrt,ucrt.parent/'shared',ucrt.parent/'um',ucrt.parent/'winrt']
    ucrtlib=next(p for p in sdk.rglob('ucrt.lib') if 'enclave' not in str(p));umlib=next(sdk.rglob('kernel32.Lib'))
    command=f'call "{vcvars}"\nif errorlevel 1 exit /b 1\nset INCLUDE={";".join(str(p) for p in include)};%INCLUDE%\nset LIB={ucrtlib.parent};{umlib.parent};%LIB%\ncl /nologo /std:c++17 /EHsc /bigobj /O1 /DCGAL_DISABLE_GMP /DBOOST_ALL_NO_LIB /I"{cgal}" /I"{boost}" "{source}" /Fe:exact_union.exe\n'
    batch=build/'compile.cmd';batch.write_text(command)
    process=subprocess.run(['cmd.exe','/d','/c',str(batch)],cwd=build,capture_output=True,text=True,timeout=600)
    (build/'build.log').write_text(process.stdout+'\n'+process.stderr,encoding='utf-8')
    record={'status':'built' if process.returncode==0 else 'build_failed','exit_code':process.returncode,'command':command,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'arithmetic':'CGAL Simple_cartesian<Quotient<MP_Float>>','licence':'CGAL PMP GPL/commercial; local research binary, not distributed in preserved converter release'}
    if process.returncode==0:record['executable_sha256']=hashlib.sha256((build/'exact_union.exe').read_bytes()).hexdigest()
    (build/'BUILD_MANIFEST.json').write_text(json.dumps(record,indent=2))
    print(json.dumps(record));print((process.stdout+process.stderr)[-3500:])
if __name__=='__main__':main()
