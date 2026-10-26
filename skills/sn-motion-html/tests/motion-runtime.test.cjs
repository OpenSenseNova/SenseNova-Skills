const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const {test} = require('node:test');
const source = fs.readFileSync(require('node:path').join(__dirname, '../assets/template/src/motion-runtime.js'), 'utf8');
function fixture({reduced=false, snap=true, media=false, linger=0.35}={}) {
  const listeners = new Map(), frames = new Map(); let now=0,id=0;
  class Element {
    constructor(tag='div'){this.tagName=tag;this.duration=5;this.currentTime=0;this.children=[];this.dataset={};this.style={setProperty(){}};this.events={};this.classList={add(){},toggle(){}};this.scrollHeight=0;this.clientHeight=0;this.scrollTop=0;this.parentElement=null;this.attrs={};}
    append(...nodes){for(const node of nodes){this.children.push(node);node.parentElement=this;if(media&&node.tagName==='video')node.events.loadeddata?.();}}
    appendChild(node){this.append(node);}
    replaceChildren(){this.children=[];}
    addEventListener(event, cb){this.events[event]=cb;}
    setAttribute(k,v){this.attrs[k]=v;}
    removeAttribute(k){delete this.attrs[k];}
    closest(){return null;}
  }
  const root=new Element();
  const ctx={console, innerHeight:720,innerWidth:1200,scrollY:0,performance:{now:()=>now},
    matchMedia:()=>({matches:reduced}),document:{createElement:t=>new Element(t),documentElement:new Element(),body:new Element(),querySelector:()=>null,hidden:false},
    getComputedStyle:e=>({overflowY:e.overflowY||'visible'}),
    requestAnimationFrame:cb=>{frames.set(++id,cb);return id;},cancelAnimationFrame:i=>frames.delete(i),
    addEventListener:(name,cb)=>listeners.set(name,cb),removeEventListener:name=>listeners.delete(name),
    fetch:()=>media ? ({value:{ok:true,blob:()=>({})},then(fn){this.value=fn(this.value);return this;},catch(){return this;}}) : ({then(){return this;},catch(fn){fn();return this;}}), URL:{createObjectURL(){return 'blob:test';},revokeObjectURL(){}}};
  ctx.window=ctx;ctx.scrollTo=({top})=>{ctx.scrollY=top;listeners.get('scroll')?.();};
  vm.runInNewContext(source,ctx);
  const destroy=ctx.mountMotionHTML(root,{scrollSnap:snap,connectorSpan:1.2,connectorPlaybackRate:0.8,snapThreshold:160,
    chapters:[{title:'A',span:4.6,clip:'scene-a',linger},{title:'B',span:4.6,clip:'scene-b',linger},{title:'C',span:4.6,clip:'scene-c',linger}],connectors:['connector-1','connector-2']});
  // Fixture fetches resolve locally; no network or generated media is needed.
  function wheel(delta,options={}){let prevented=false;listeners.get('wheel')?.({deltaY:delta,deltaX:0,deltaMode:0,target:root,preventDefault:()=>prevented=true,...options});return prevented;}
  function advance(ms){for(let left=ms;left>0;){let step=Math.min(16,left);left-=step;now+=step;const callbacks=[...frames.values()];frames.clear();callbacks.forEach(cb=>cb(now));}}
  return {ctx,root,listeners,frames,wheel,advance,destroy,Element,setNow:n=>now=n};
}
test('wheel threshold holds, commits once, plays by elapsed time and lands with readable copy',()=>{
 const f=fixture();f.wheel(3312);assert(Math.abs(f.ctx.scrollY-3311)<0.01);assert.equal(f.root.dataset.transition,undefined);
 f.wheel(80);assert(Math.abs(f.ctx.scrollY-3311)<0.01);f.wheel(90);assert.equal(f.root.dataset.transition,'playing');
 const start=f.ctx.scrollY;f.advance(1000);const moved=f.ctx.scrollY-start;
 assert(moved>140&&moved<200,'one second advances ~173px of the 864px connector');
 const y=f.ctx.scrollY;f.wheel(100000);assert.equal(f.ctx.scrollY,y,'wheel burst cannot fast-forward');
 f.advance(4100);assert.equal(f.root.dataset.transition,undefined);assert(Math.abs(f.ctx.scrollY-4177)<0.01);
 const copyLayer=f.root.children[1];assert.equal(copyLayer.children[1].style.opacity,1);
 f.wheel(100000);assert(Math.abs(f.ctx.scrollY-4177)<0.01,'cooldown suppresses chained transition');
 f.destroy();assert(!f.listeners.has('wheel'));f.advance(2000);assert.equal(f.frames.size,0);
});
test('reverse traversal completes and stops on departure scene',()=>{
 const f=fixture();f.ctx.scrollTo({top:4177});f.wheel(-200);assert.equal(f.root.dataset.transition,'playing');
 f.advance(5100);assert.equal(f.root.dataset.transition,undefined);assert(Math.abs(f.ctx.scrollY-3311)<0.01);
 assert.equal(f.root.children[1].children[0].style.opacity,1);
});
test('small separated gestures do not accumulate stale intent',()=>{
 const f=fixture();f.wheel(3312);f.wheel(100);f.advance(300);f.wheel(100);assert.equal(f.root.dataset.transition,undefined);
});
test('direction reversal releases boundary instead of committing',()=>{
 const f=fixture();f.wheel(3312);f.wheel(100);f.wheel(-200);assert.equal(f.root.dataset.transition,undefined);assert(f.ctx.scrollY<3311);
});
test('reduced motion and explicit opt-out retain native scrolling',()=>{
 for(const options of [{reduced:true},{snap:false}]){const f=fixture(options);assert.equal(f.wheel(5000),false);assert.equal(f.root.dataset.transition,undefined);f.destroy();}
});
test('zoom, horizontal scroll, dialogs and nested copy scroll are not hijacked',()=>{
 const f=fixture();assert.equal(f.wheel(100,{ctrlKey:true}),false);assert.equal(f.wheel(10,{deltaX:100}),false);
 f.ctx.document.querySelector=()=>({});assert.equal(f.wheel(100),false);f.ctx.document.querySelector=()=>null;
 const copy=new f.Element();copy.scrollHeight=1000;copy.clientHeight=200;copy.overflowY='auto';copy.parentElement=f.root;
 assert.equal(f.wheel(100,{target:copy}),false);copy.scrollTop=800;assert.equal(f.wheel(100,{target:copy}),true);
});
test('external scrolling cancels automatic motion without fighting scrollbar',()=>{
 const f=fixture();f.wheel(5000);assert.equal(f.root.dataset.transition,'playing');f.ctx.scrollTo({top:100});f.advance(6000);assert.equal(f.ctx.scrollY,100);assert.equal(f.root.dataset.transition,undefined);
});
test('navigation cancels animation and makes destination copy readable',()=>{
 const f=fixture();f.wheel(5000);const nav=f.root.children[4];nav.children[2].events.click();f.advance(6000);
 assert.equal(f.root.dataset.transition,undefined);assert(Math.abs(f.ctx.scrollY-8352)<0.01);assert.equal(f.root.children[1].children[2].style.opacity,1);
});

test('a five-second decoded connector takes 6.25 seconds at 0.8x, not wheel speed',()=>{
 const f=fixture({media:true});f.wheel(5000);f.advance(5000);assert.equal(f.root.dataset.transition,'playing');
 assert(f.ctx.scrollY<4176);f.advance(1350);assert.equal(f.root.dataset.transition,undefined);assert(Math.abs(f.ctx.scrollY-4177)<0.01);
});


test('reading slowdown keeps the video advancing through the middle in both directions', () => {
  for (const linger of [0, 0.35, 0.6]) {
    const f = fixture({media: true, snap: false, linger});
    const video = f.root.children[0].children[0].children.at(-1);
    let previous;
    for (let step = 15; step <= 35; step++) {
      f.ctx.scrollTo({top: (step / 50) * 3312});
      f.advance(800);
      if (previous !== undefined) assert(video.currentTime > previous + 0.025, 'forward scrubbing must not freeze');
      previous = video.currentTime;
    }
    for (let step = 34; step >= 15; step--) {
      f.ctx.scrollTo({top: (step / 50) * 3312});
      f.advance(800);
      assert(video.currentTime < previous - 0.025, 'reverse scrubbing must not freeze');
      previous = video.currentTime;
    }
    f.destroy();
  }
});

test('copy stays visible when scrolling resumes after a snapped landing', () => {
  const f = fixture({media: true});
  f.wheel(5000);
  f.advance(6400);
  assert.equal(f.root.dataset.transition, undefined);
  assert.equal(f.root.children[1].children[1].style.opacity, 1);
  f.advance(400);
  f.wheel(50);
  assert.equal(f.root.children[1].children[1].style.opacity, 1);
  f.destroy();
});

test('pending decoding coalesces seek writes without stalling progress smoothing', () => {
  const f = fixture({media: true});
  const video = f.root.children[0].children[0].children.at(-1);
  video.seeking = true;
  f.ctx.scrollTo({top: 1656});
  f.advance(1000);
  assert.equal(video.currentTime, 0, 'do not issue another seek while decoding');
  video.seeking = false;
  f.advance(16);
  assert(Math.abs(video.currentTime - 2.5) < 0.03, 'catch up on the first frame after decoding');
  f.destroy();
});
