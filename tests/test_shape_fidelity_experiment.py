"""Independent analytic examples and deliberate footprint corruptions."""
from pathlib import Path
import importlib.util
import math
import sys

import pytest
from shapely import affinity
from shapely.geometry import box, shape

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from shape_fidelity_experiment import reference, compare, read_footprint


def test_l_shape_bounding_loss_matches_closed_form():
    expected=reference('l_shape',0)
    metrics=compare(box(100,200,112,208),expected)
    assert metrics['intersection_over_union']==pytest.approx(51/96)
    assert metrics['symmetric_difference_m2']==pytest.approx(45)
    assert metrics['area_overestimate_percent']==pytest.approx(100*45/51)


def test_rotated_rectangle_box_matches_closed_form():
    expected=reference('rectangle',45)
    # Rotated 12 x 8 rectangle has side extent (12 + 8)/sqrt(2).
    assert expected['aabb_area_m2']==pytest.approx(200)
    assert expected['aabb_volume_m3']==pytest.approx(1200)
    assert expected['volume_m3']==576


def test_courtyard_fill_is_detected_even_when_external_boundary_matches():
    expected=reference('courtyard',0)
    metrics=compare(box(100,200,112,210),expected)
    assert metrics['intersection_over_union']==pytest.approx(.8)
    assert metrics['reference_holes']==1 and metrics['exported_holes']==0
    assert metrics['symmetric_difference_m2']==pytest.approx(24)
    assert metrics['boundary_hausdorff_m']>0


@pytest.mark.parametrize('corruption',['translation','units','reflection'])
def test_corrupted_placement_or_scale_cannot_pass(corruption):
    expected=reference('l_shape',30);ref=shape(expected['footprint'])
    if corruption=='translation':actual=affinity.translate(ref,xoff=1)
    elif corruption=='units':actual=affinity.scale(ref,1000,1000,origin=(100,200))
    else:actual=affinity.scale(ref,-1,1,origin=(100,200))
    metrics=compare(actual,expected)
    assert metrics['intersection_over_union']<.999999
    assert metrics['boundary_hausdorff_m']>5e-6


def test_setback_volume_is_not_footprint_times_maximum_height():
    expected=reference('setback',0)
    assert expected['volume_m3']==360
    assert expected['aabb_volume_m3']==576


def test_valid_rectangle_projection_from_actual_xml(tmp_path):
    p=tmp_path/'surface.gml'
    p.write_text('''<root xmlns:gml="http://www.opengis.net/gml/3.2"><gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>100 200 10 112 200 10 112 208 10 100 208 10 100 200 10</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon></root>''')
    footprint,rings=read_footprint(p)
    assert compare(footprint,reference('rectangle',0))['intersection_over_union']==1
    assert len(rings)==1


def test_unclosed_xml_ring_is_rejected(tmp_path):
    p=tmp_path/'unclosed.gml'
    p.write_text('''<root xmlns:gml="http://www.opengis.net/gml/3.2"><gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>0 0 0 1 0 0 1 1 0 0 1 0</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon></root>''')
    with pytest.raises(AssertionError):read_footprint(p)
