"""Palatino edition with depth-tested building illustrations and restrained typography."""
import base64
import subprocess
import build_research_figures as b

b.OUT=b.ROOT/'reports/methodology_palatino'
b.FIG=b.OUT/'figures';b.FIG.mkdir(exist_ok=True)
b.NAVY,b.TEAL,b.AMBER,b.RUST,b.BLUE='#243536','#4c7271','#9b8561','#9a6556','#748d99'
b.MUTED,b.LINE,b.PALE='#626b69','#d9dedb','#f4f5f2'


def start(n,title,sub):
    b.parts.clear();b.rect(0,0,1200,880,'white')
    b.text(55,48,f'Figure {n}     /     IFC to CityGML',17,b.MUTED)
    b.text(55,104,title,32,b.NAVY,400)
    b.text(55,145,sub,18,b.MUTED)
    b.line(55,171,1145,171,b.LINE,1)


def save(name,source,note):
    b.line(55,785,1145,785,b.LINE,1)
    b.text(55,817,source,15,b.MUTED)
    b.text(55,845,note,15,b.MUTED)
    svg='<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1200" height="880" viewBox="0 0 1200 880"><g font-family="Palatino Linotype, Palatino, serif">'+''.join(b.parts)+'</g></svg>'
    path=b.FIG/(name+'.svg');path.write_text(svg,encoding='utf-8')
    subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless','--disable-gpu','--hide-scrollbars','--force-device-scale-factor=2','--window-size=1200,880',f'--screenshot={b.FIG/(name+".png")}',path.as_uri()],capture_output=True,check=True)


def geometry():
    start(2,'Building representations from one IFC','Duplex benchmark   ·   Same view and scale   ·   Exported geometry in local metres')
    for i,(title,ss) in enumerate(zip(['Bounding block','Exterior surfaces','Source surfaces'],[['Six bounding faces','Selected physical bodies'],['4,104 boundary polygons','Rule based surface classes'],['9,420 source triangles','137 represented features']])):
        x=55+i*370
        b.text(x,231,chr(97+i),19,b.MUTED)
        b.text(x+28,231,title,25,b.NAVY)
        data=base64.b64encode((b.OUT/f'depth_model_{i}.png').read_bytes()).decode()
        b.parts.append(f'<image x="{x-6}" y="278" width="365" height="355" xlink:href="data:image/png;base64,{data}"/>')
        b.lines(x,693,ss,20,b.MUTED,30)
    save('02_building_representations','Source: frozen v0.6 Duplex CityGML outputs. Geometry is unchanged; visibility uses a depth buffer.','Roof colour identifies the recorded exterior class. Source surfaces use one uniform colour; neither view proves Solid validity.')


def validation():
    start(3,'Validation questions and their evidence','Three complementary checks   ·   A separate volume diagnostic for surface outputs')
    items=[('01','Schema','Is the XML well formed','against the target schema?', ['Official CityGML XSDs','Unique identifiers','Resolved references']),
           ('02','Geometry','Is the declared geometry','valid under its own rules?', ['Solid for bounding blocks','MultiSurface for surfaces','Recorded tool tolerances']),
           ('03','Correspondence','Does the output retain','the selected source content?', ['Feature identities and links','Fresh source extraction','Explicit omission records'])]
    for i,(num,title,q1,q2,detail) in enumerate(items):
        x=55+i*370
        b.text(x,239,num,20,b.TEAL)
        b.text(x,292,title,30,b.NAVY)
        b.lines(x,349,[q1,q2],22,b.NAVY,32)
        b.line(x,421,x+315,421,b.LINE,1)
        b.lines(x,466,detail,20,b.MUTED,37)
        if i<2:b.line(x+342,230,x+342,590,b.LINE,1)
    b.line(55,626,1145,626,b.LINE,1)
    b.text(55,675,'Additional Solid diagnostic',25,b.NAVY)
    b.lines(440,672,['Surface output is also tested as a candidate closed volume.','This additional test is not applicable to an already declared Solid.'],20,b.MUTED,31)
    save('03_validation_layers','Source: converter v0.6 validation records, independent source audits and val3dity 2.7.0.','Valid triangles do not establish a watertight volume, geographic accuracy or independent semantic truth.')


if __name__=='__main__':
    b.start=start;b.save=save
    for f in [b.workflow,geometry,validation,b.outcomes,b.source_audit,b.context]:f()
    print('Created six Palatino figures, including corrected depth-tested roof rendering')
