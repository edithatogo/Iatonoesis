import pytest
from iatonoesis.doclaynet_external import box, match, select, threshold, metrics, geometry


def meta(i,doc,cat='manuals'):
    return dict(image_id=i,original_filename=doc,page_hash=f'hash-{i}',doc_category=cat,coco_width=100,coco_height=100)


def test_geometry_and_class_match_are_distinct():
    gold=[('text',[0,0,10,10]),('table',[20,20,40,40])]
    pred=[('text',[0,0,10,10],.9),('text',[20,20,40,40],.8),('text',[0,0,10,10],.7)]
    assert match(gold,pred,.5,True)==(1,2,1)
    assert match(gold,pred,.5,False)==(2,1,0)
    assert box([2,3,4,5])==[2.,3.,6.,8.]
    with pytest.raises(ValueError): box([0,0,0,1])


def test_document_and_page_disjoint_sampling():
    val=[('v',i,meta(i,doc)) for i,doc in enumerate(['a','a','b','c'])]
    test=[('t',i,meta(i+10,doc)) for i,doc in enumerate(['a','d','e'])]
    v,t,a=select(val,test,2)
    assert len(v)==2 and len(t)==2 and a['overlap_documents']==1
    assert {x[2]['original_filename'] for x in v}.isdisjoint(x[2]['original_filename'] for x in t)
    assert v==select(list(reversed(val)),test,2)[0]


def test_threshold_and_metrics_do_not_credit_abstention():
    rows=[{'gold':[('text',[0,0,10,10])],'pred':[('text',[0,0,10,10],.8),('text',[50,50,60,60],.2)],'category':'manuals'}]
    assert threshold(rows)==.5
    assert metrics(rows,.5,1,True)['f1']==1
    assert metrics(rows,.9,1,True)['fn']==1
    assert metrics(rows,.9,1,True)['f1']==0


def test_conventional_pixel_segmentation():
    Image=pytest.importorskip('PIL.Image'); Draw=pytest.importorskip('PIL.ImageDraw')
    pytest.importorskip('numpy'); pytest.importorskip('scipy.ndimage')
    im=Image.new('RGB',(100,100),'white'); d=Draw.Draw(im); d.rectangle((10,10,60,20),fill='black'); d.rectangle((10,60,60,70),fill='black')
    preds=geometry(im)
    assert len(preds)==2 and all(x[0]=='text' for x in preds)


def test_end_to_end_arms_and_review_denominators():
    from iatonoesis.doclaynet_external import evaluate, hybrid
    a=[('text',[0,0,10,10],.8)]; b=[('text',[0,0,10,10],.9),('table',[20,20,40,40],.7)]
    assert hybrid(b,a)==b
    assert len(hybrid(a,b))==2
    row={'identity':'x','category':'manuals','gold':[('text',[0,0,10,10]),('table',[20,20,40,40])],'geometry':a,'heron':b,'hybrid':hybrid(b,a),'seconds':dict(geometry=.1,heron=.2,hybrid=.3)}
    r=evaluate([row],[row,dict(row,identity='y')]); assert r['heron']['test']['60']['typed_0.5']['f1']==1
    assert r['heron']['review_frontier'][0]['metrics']['fn']==4
    assert r['geometry']['categories']['manuals']['fn']==2


def test_exact_source_pin_and_cli(monkeypatch,tmp_path):
    import json,sys
    from types import SimpleNamespace as NS
    from iatonoesis import doclaynet_external as m
    info=NS(siblings=[NS(rfilename='f',size=1,lfs=NS(sha256='a'*64))])
    assert m.file_pin(info,'f',1)=='a'*64
    with pytest.raises(ValueError): m.file_pin(info,'f',2)
    with pytest.raises(ValueError): m.file_pin(NS(siblings=[NS(rfilename='f',size=1,lfs={'sha256':'x'})]),'f',1)
    dest=tmp_path/'x.json';monkeypatch.setattr(sys,'argv',['run','--output',str(dest)])
    monkeypatch.setattr(m,'run',lambda root:{'scope':'fixture'})
    m.main();assert json.loads(dest.read_text())=={'scope':'fixture'}
    def fail(root): raise ValueError('fixture')
    monkeypatch.setattr(m,'run',fail)
    with pytest.raises(ValueError): m.main()
    assert json.loads(dest.read_text())['status']=='failed'


def test_full_run_retains_scope_and_metadata(monkeypatch,tmp_path):
    from iatonoesis import doclaynet_external as m
    v=[('v',0,meta(1,'a'))];t=[('t',0,meta(2,'b'))]
    monkeypatch.setattr(m,'acquire',lambda root: ({},{'val':v,'test':t},{'revision':'pinned'}))
    monkeypatch.setattr(m,'detector',lambda root:(None,{'revision':'pinned'}))
    def execute(paths,selected,predict):
        return [dict(identity=str(s[2]['image_id']),category='manuals',gold=[('text',[0,0,1,1])],geometry=[],heron=[],hybrid=[],seconds=dict(geometry=0,heron=0,hybrid=0)) for s in selected]
    monkeypatch.setattr(m,'execute',execute)
    out=m.run(tmp_path)
    assert out['test_pages']==1 and out['validation_pages']==1
    assert out['arms']['heron']['test']['60']['typed_0.5']['fn']==1
    assert 'not_unseen_source' in out['scope']
