# fancy 技法配方（sn-ppt-dazzle）

> **使用说明**
> 1. 每个 deck 在阶段0选型时只取：**一种全局背景 + 一套入场编排体系 + 一种通用过渡**，可另加 ≤2 个交互彩蛋；同类技法不要叠加。
> 2. 按场景档位定密度：**庄重档**（商务/学术/汇报）只用标注"庄重档可用"的配方且参数取下限；**自由档**（创意/主题/发布会）可用全部配方并替换主题图形。
> 3. 配方是模式不是模板：颜色、缓动、粒子图形必须替换为本 deck 的设计 tokens 与母题，严禁照抄示例配色。
> 4. 三条全局铁律：动画挂 `.slide.active` 之下（翻回自动重播）；一切覆盖层 `pointer-events:none`；canvas `pixelRatio` 封顶 2、固定 1280×720 随 deck 整体 scale。
> 5. **按题材选技术载体，背景默认就该"活"**：CSS/SVG/Canvas-2D/shader/3D 各有所长——纯 2D/CSS 做得有创意、绑紧题材，同样是满分 fancy。**分清两种 3D 用法**：① **灵动 3D/shader 背景层**（节点球 / Fresnel 球 / shader 流场 / 粒子流）——广泛适用、科技抽象数据网络类尤其加分，不算"硬套 3D"；② **沉浸漫游场景**（可巡游 3D 世界 + 翻页相机运镜）——才只给有空间主体的题材（建筑/天体/地形地貌；分子晶体、实体产品三维也算）。**三种坍缩都别犯**：别一律 canvas 粒子、别一律沉浸漫游、也别把背景做成静态死平面。重型手法题材合适时大胆用、别因难调试回避，但服务题材不为炫而炫。
> 6. **选定即兑现**：plan 里写了 immersive_3d / 代码 3D，就必须真用 Three.js 搭出 3D 场景，不许中途降级成 2D 粒子充数（见 SKILL.md §5 招牌兑现）。
> 7. **禁网格底纹背景**：方格纸 / 蓝图网格 / 透视网格地面 / 规则点阵 / `GridHelper` 一律不做背景（被滥用的 AI 套路），要纵深用渐变光晕 / shader 噪声 / 粒子流场。

## 入场编排（entrance）

### 类级 staggered reveal（万金油底座）
页内元素依次上浮淡入的入场编排。**所有风格通用，庄重档默认首选**。

```css
.slide .reveal{opacity:0;transform:translateY(18px)}
.slide.active .reveal{animation:rev .8s cubic-bezier(.2,.7,.2,1) both}
.slide.active .reveal.d1{animation-delay:.1s}
.slide.active .reveal.d2{animation-delay:.25s}
.slide.active .reveal.d3{animation-delay:.4s}
.slide.active .reveal.d4{animation-delay:.55s}
@keyframes rev{to{opacity:1;transform:translateY(0)}}
/* 变体：免编号容器，子元素自动错峰 */
.slide.active .stagger>*{opacity:0;animation:rev .8s cubic-bezier(.2,.7,.2,1) both}
.slide.active .stagger>*:nth-child(1){animation-delay:.1s}
.slide.active .stagger>*:nth-child(2){animation-delay:.22s}
.slide.active .stagger>*:nth-child(3){animation-delay:.34s}
```

参数：时长 .6–1.1s；步进 .08–.18s；位移 12–24px；梯队 ≤6 级、总链 ≤1.2s；缓动用先快后缓。
坑：fill-mode 必须 both（delay 期间靠 from 帧兜底，否则先闪现再消失）；动画必须挂 `.slide.active` 下才能翻回重播；nth-child 按全部兄弟节点计数，级数要覆盖实际子元素数（可加 `:nth-child(n+5)` 兜底）。

### SVG 路径 draw-in（--len 变量）
折线图/路线/插画笔画像被笔逐渐画出，标注后置淡入。**庄重档可用**（数据揭示、图解、地图）；手绘/水墨风加分项。

```css
.draw{stroke-dasharray:var(--len,1500);stroke-dashoffset:var(--len,1500);
  transition:stroke-dashoffset 2.2s cubic-bezier(.6,0,.3,1)}
.slide.active .draw{stroke-dashoffset:0}          /* transition 写法离页自动回卷、重进重播 */
.late{opacity:0}
.slide.active .late{animation:lateFade .8s ease forwards}
.slide.active .late.l1{animation-delay:.7s}
.slide.active .late.l2{animation-delay:1.3s}
@keyframes lateFade{to{opacity:1}}
```
```html
<path class="draw" style="--len:1300" d="…" fill="none" stroke="url(#grad)"
      stroke-width="2.3" stroke-linecap="round"/>
```

参数：--len ≥ `path.getTotalLength()`（放大 5–10% 余量；长线 800–1500、小圆点 30–80）；单笔 1.5–2.6s；多笔梯队 .3–.5s；标注比笔画晚 .6s 起步。
坑：--len 偏小会"开场已画一截"或虚线段中途重复；图形必须 fill:none 或低 fill-opacity(.18)，否则色块先于线条闪现；animation 写法必须 forwards。

### 数据动效：count-up + 条形图重置-生长
KPI 大数字 ease-out 滚到目标值、条形图错峰生长。**庄重档数据页标配**。

```js
function countUp(el, target, dur=1400, fmt=v=>v.toFixed(1)){
  const t0=performance.now();
  (function tick(t){
    const k=Math.min(1,(t-t0)/dur), e=1-Math.pow(1-k,3);   // cubic ease-out
    el.textContent=fmt(e*target);
    if(k<1) requestAnimationFrame(tick); else el.textContent=fmt(target); // 末帧吸附精确值
  })(performance.now());
}
// 条形图每次进页重播：先归零、隔一拍再按 stagger 赋目标宽度（宽度走 CSS transition）
const obs=new MutationObserver(()=>{ if(!s.classList.contains('active'))return;
  bars.forEach(el=>el.style.width='0%');
  setTimeout(()=>bars.forEach((el,i)=>setTimeout(()=>el.style.width=el.dataset.w+'%',i*120)),100);
});
obs.observe(s,{attributes:true,attributeFilter:['class']});
```

参数：count-up 1.2–1.8s；条形 transition 0.8–1.2s、逐根 stagger 100–150ms；目标值放 data-* 与展示解耦；千分位用 toLocaleString。
坑：触发挂翻页时机而非 load；数字容器必须 `font-variant-numeric:tabular-nums` 防逐帧变宽抖布局；直接改 width 不重播——必须先归零且隔 ≥100ms 再赋值。

### 弹性 popIn stagger（CSS 变量参数化 + 待机 wiggle）
卡片/贴纸带过冲倾角依次弹入，落定后接无限轻摆保持"活着"。**仅自由档**（贴纸/漫画/儿童/Memphis/波普）。

```css
.reveal{opacity:0}
.slide.active .reveal{
  animation:popIn .7s cubic-bezier(.34,1.56,.64,1) var(--d,0s) both,
            wiggle 3.5s ease-in-out calc(var(--d,0s) + .8s) infinite}
@keyframes popIn{
  0%{opacity:0;transform:translateY(40px) scale(.55) rotate(calc(var(--rot,0deg) - 18deg))}
  100%{opacity:1;transform:translateY(0) scale(1) rotate(var(--rot,0deg))}}
@keyframes wiggle{
  0%,100%{transform:rotate(var(--rot,0deg)) translateY(0)}
  50%{transform:rotate(calc(var(--rot,0deg) + 2.5deg)) translateY(-5px)}}
```
```html
<div class="card reveal" style="--d:.25s;--rot:-3deg">…</div>
```

参数：时长 .5–.8s；步进 .08–.15s；终态倾角 ±2–8deg 相邻正负交替；过冲 bezier 第二参 1.3–1.7；wiggle 周期 3–5s、幅度 ±2–3deg / 上浮 3–6px。
坑：两段动画每个 keyframe 都要写全 `rotate(var(--rot))`，否则交接瞬间跳角；wiggle 的 delay 必须 ≥ popIn 完成时刻；一页无限循环元素 ≤3 个。

### 重物砸落（印章 / 巨字锤落 + 震屏）
印章/巨字从高空砸落，带过冲、微震与辉光爆发。**主题向自由档**（中式/复古/史诗/发布会重点页）。

```css
.slide.active .stamp{animation:drop 1.8s cubic-bezier(.34,1.56,.64,1) both}
@keyframes drop{
  0%{opacity:0;transform:rotate(-18deg) scale(3)}
  45%{opacity:1;transform:rotate(-5deg) scale(1.08)}
  58%{transform:rotate(-9deg) scale(.97) translate(1.5px,-1.5px)}   /* 落定微震 */
  100%{opacity:.85;transform:rotate(-8deg) scale(1)}}               /* .85 更像真印泥 */
/* 巨字版：0%{translateY(-220px)} → 65% 触底过冲并爆三层金色 text-shadow → 回稳；
   最后一字落地时 JS 给 .slide 加 shake 类 */
@keyframes shake{0%,100%{transform:none}22%{transform:translate(-5px,3px)}
  48%{transform:translate(4px,-2px)}72%{transform:translate(-3px,1px)}}
```

参数：初始 scale 2.5–3.5 或下落高度 180–260px；单字 .4–.7s、字间 stagger .3–.4s；微震 1–2px、震屏 3–6px/0.4s；整体 delay 排在页面其他动画之后压轴。
坑：重播必须 remove class → `void el.offsetWidth` 强制 reflow → add class 三连；shake 挂 slide 容器且 slide 自身不能再有其他 transform；text-shadow 逐帧动画昂贵，只用于少数大字并加 will-change。

### 字符级 split 仪式感标题
标题拆单字 span 逐字入场：科技档 blur 景深聚焦、文化档书法描边、文献档逐字点亮。**克制使用可入庄重档封面**。

```js
[...title.textContent].forEach(ch=>{ const sp=document.createElement('span');
  sp.innerHTML = ch===' ' ? '&nbsp;' : ch; title.appendChild(sp); });   // span 须 inline-block
function play(){ title.querySelectorAll('span').forEach((sp,k)=>{
  sp.style.transition='none';
  sp.style.opacity='0'; sp.style.transform='scale(2)'; sp.style.filter='blur(8px)';
  void sp.offsetWidth;                                  // 强制 reflow 才能重播
  sp.style.transition=`opacity .8s ease ${k*.04}s, transform .8s cubic-bezier(.2,.8,.2,1) ${k*.04}s, filter .8s ease ${k*.04}s`;
  setTimeout(()=>{ sp.style.opacity='1'; sp.style.transform='none'; sp.style.filter='none'; },30);
});}
```

参数：逐字 stagger .03–.08s（中文 ≤8 字可放宽到 .2–.8s）；blur 6–12px、起始 scale 1.5–2.5；书法描边版 stroke-dasharray 2500–3500、描边将完时 fill-opacity 淡入填实。
坑：按码点 `[...]` 拆分防中文/emoji 出错；空格换 `&nbsp;` 防 span 塌缩；重播前必须 transition:none + 强制 reflow，否则浏览器合并样式不播。

## 跨页过渡（transition）

### 方向性模糊溶解（visibility 延迟技）
新页带方向位移+blur 溶解进入，旧页反向退出。零 JS 动画代码。**庄重档默认首选，全风格通用**。

```css
.slide{position:absolute;inset:0;opacity:0;visibility:hidden;pointer-events:none;
  transform:translateX(40px);filter:blur(8px);
  transition:opacity .6s ease,filter .6s ease,transform .6s ease,
             visibility 0s linear .6s}      /* 退场播完才真正隐藏 */
.slide.active{opacity:1;visibility:visible;pointer-events:auto;
  transform:none;filter:none;
  transition:opacity .6s ease,filter .6s ease,transform .6s ease,
             visibility 0s linear 0s}       /* 入场立即可见 */
.slide.prev{transform:translateX(-40px)}    /* 看过的页向左退出 */
```
```js
slides.forEach((s,i)=>{ s.classList.remove('active','prev');
  if(i===idx) s.classList.add('active'); else if(i<idx) s.classList.add('prev'); });
```

参数：位移 16–60px；blur 6–8px；时长 .5–.9s；深色/水下主题可叠 `brightness(.3)` 且 filter 比 opacity 慢 .2–.4s 做两段式纵深。
坑：`.active` 上 visibility delay 必须归零否则新页干等；非 active 的 delay 同样不能省否则旧页瞬隐；整页 blur ≤8px 控 GPU。

### zoom-through 缩放穿越（三态 scale）
镜头一路向前穿过每一页：未来页缩在远处、翻过的页放大淡出飞过镜头。**科技/pitch/数据风**，庄重档可用。

```css
.slide{position:absolute;inset:0;opacity:0;visibility:hidden;pointer-events:none;
  transform:scale(.5);
  transition:opacity .7s ease,transform .95s cubic-bezier(.45,.05,.2,1),visibility 0s .7s}
.slide.active{opacity:1;visibility:visible;pointer-events:auto;transform:scale(1);z-index:2;
  transition:opacity .7s ease,transform .95s cubic-bezier(.45,.05,.2,1),visibility 0s 0s}
.slide.prev{opacity:0;visibility:visible;transform:scale(1.65);
  transition:opacity .7s ease,transform .95s cubic-bezier(.45,.05,.2,1),visibility 0s .7s}
```

参数：入场起点 scale .4–.6；离场终点 1.5–1.8；opacity 比 transform 短 .2–.3s 形成"先看清再到位"层次。
坑：离场页 visibility 必须延迟切换，否则没有飞过镜头的过程；`.active` 要加 z-index 压住正在放大的 `.prev`；prev 集合每次按 `idx<i` 重算保证回翻方向正确。

### 三态方向推页 / 3D 书页翻转
未来页右侧带倾角候场、已读页推到左侧屏外，像漫画分格横推或翻杂志。**自由档**（漫画/波普）；书页变体可入庄重档（画册/editorial）。

```css
.slide{position:absolute;inset:0;opacity:0;visibility:hidden;
  transform:translateX(115%) rotate(6deg);
  transition:transform .55s cubic-bezier(.55,.05,.3,1.05),opacity .35s .05s,visibility .35s}
.slide.active{opacity:1;visibility:visible;transform:none}
.slide.prev{transform:translateX(-115%) rotate(-6deg);opacity:0}
/* 书页变体（庄重档）：transform:perspective(2200px) rotateY(-14deg) translateX(60px)，
   .prev 用 rotateY(8deg) + transform-origin:right center，左右书脊互换 */
```

参数：位移 110–120%（带旋转后对角会探出 100%）；倾斜 4–8deg；bezier 末参 1.0–1.05 给轻微回弹；书页版 perspective 1800–2600px、入出场角不对称（-14/+8deg）。
坑：必须三态（默认/active/prev），两态时回翻方向反；deck 容器必须 overflow:hidden；离场页 opacity 归 0 防屏外页扫过时露出。

### overlay 遮蔽式换页（幕布 / 宫门 / 熄灯）
两扇主题化门板合拢遮屏、幕后换页、再拉开；或全局 brightness 熄灯-亮灯。把过渡本身做成叙事元素。**主题向**（剧场/宫殿/博物馆/电影感），熄灯版可入庄重暗色档。

```js
let busy=false;
function go(n){
  if(busy) return; busy=true;
  curL.style.transform=curR.style.transform='translateX(0)';     // 合拢
  setTimeout(()=>{
    setSlide(n);                                                 // 幕后换页
    requestAnimationFrame(()=>requestAnimationFrame(()=>{        // 双 rAF 等合拢态提交
      curL.style.transform='translateX(-101%)';                  // ±101% 防子像素露缝
      curR.style.transform='translateX(101%)';
      setTimeout(()=>busy=false,1100);
    }));
  },700);
}
/* 熄灯变体：背景 canvas 加 .dim{filter:brightness(.04)} 同步 slide brightness(.06)，
   黑场点 ≈ 过渡时长 80% 时换页；brightness 低值取 .03–.08 保留余光 */
```

参数：门板 transition 0.9–1.2s、重物缓动 cubic-bezier(.55,0,.25,1)；合拢等待 ≈ 0.6×transition 即可换页；解锁延时 ≈ transition 时长；门板加金边+投影+织物纹理质感大增。
坑：拉开前必须双 rAF（或强制 reflow），否则两次 transform 被合并、幕布纹丝不动；busy 锁防连按卡半开；overlay z-index 压过所有 slide 且 pointer-events:none。

### 主题粒子过场幕 + 闪白脉冲
翻页瞬间在顶层撒一波主题粒子（落叶/花瓣/气泡/像素爆散），可叠 0.15s 强调色闪白。**仅自由档**，主题图形必须替换为 deck 母题。

```js
function spawnParticles(){                       // 翻页函数里调用
  for(let i=0;i<7;i++){
    const el=document.createElement('div'); el.className='fall-p';
    el.style.left=Math.random()*1280+'px'; el.style.top='-40px';
    el.style.setProperty('--xEnd',(Math.random()*200-100)+'px');
    el.style.setProperty('--yEnd','780px');                       // 超出画面飘出
    el.style.setProperty('--rotEnd',(Math.random()*720-360)+'deg');
    el.style.animationDelay=Math.random()*.4+'s';
    el.innerHTML='<svg viewBox="0 0 30 30">…主题图形…</svg>';
    layer.appendChild(el); setTimeout(()=>el.remove(),2200);      // 自清理双保险
  }
}
/* @keyframes fall{15%{opacity:1}100%{transform:translate(var(--xEnd),var(--yEnd))
   rotate(var(--rotEnd));opacity:0}}  forwards
   闪白变体：.flash.pulse{animation:goldFlash .15s}（alpha 0→.32→0），重触发走 reflow 三连 */
```

参数：DOM 粒子 5–10 个/次（上限 ~15）；时长 1.4–2s；清理时间 > 动画时长+最大 delay；canvas 版气泡/像素爆散可到 70–800 粒、总时长 500–700ms。
坑：overlay z-index 高于所有 slide、pointer-events:none；连续翻页靠 setTimeout remove 防 DOM 堆积；canvas 版结束帧必须 clearRect 防残留。

### 单一 3D 世界相机航点运镜
全 deck 共用一个常驻 Three.js 场景，每页一个 {pos, look} 机位，翻页=相机沿抬高中点的弧线俯冲过去，HTML 内容只做淡入淡出。**与「代码搭建 3D 场景」配套的标配过渡**——凡是用了 3D 场景背景的 deck 都该用它（建筑/文旅/科技/地理/天文/产品），把"翻页"变成"在 3D 世界里移动镜头"。值得优先采用，不要因为是 3D 就回避。

```js
const SLIDES=[{pos:V(60,75,75),look:V(0,4,0)}, /* 每页一个机位 */];
let camAnim=null; const curLook=new THREE.Vector3();
function tweenTo(idx){
  if(camAnim) camAnim.cancelled=true;                  // 旧 tween 必须可打断
  const from=camera.position.clone(), to=SLIDES[idx].pos.clone();
  const mid=from.clone().lerp(to,.5);
  mid.y=Math.max(mid.y, Math.max(from.y,to.y)+18);     // 中点抬高 → 俯冲弧线
  const curve=new THREE.QuadraticBezierCurve3(from,mid,to);
  const fromLook=curLook.clone(), t0=performance.now(), anim={cancelled:false};
  camAnim=anim;
  (function step(){
    if(anim.cancelled) return;
    const t=Math.min(1,(performance.now()-t0)/2000);
    const e=t<.5 ? 2*t*t : 1-Math.pow(-2*t+2,2)/2;     // easeInOutQuad
    camera.position.copy(curve.getPointAt(e));
    curLook.lerpVectors(fromLook,SLIDES[idx].look,e);  // 注视点必须同步插值
    camera.lookAt(curLook);
    if(t<1) requestAnimationFrame(step); else camAnim=null;
  })();
}
```

参数：飞行 1.5–2.3s；HTML slide opacity 过渡 0.6–0.9s 与运镜起步重叠；落定后 idle 呼吸漂移 `sin(t*.18)*0.5`（只在 !camAnim 时加）；穿模航线可加 forceStart 瞬移起点做穿越 dolly。
坑：只 lerp 位置不插值 look 会瞬间甩头；快速连翻必须 cancelled 标志防新旧 tween 抢相机；进度基于 performance.now 而非帧计数；层级写死 canvas 1 < slide 5 < HUD 50。

## 全局动态背景（background）

> **背景默认就该"活"**（持续微动；纯静态渐变是丢分，除非前景自带持续动态）。**类型按题材选**：科技/AI/抽象/数据/网络 → 「3D 主视觉天体（节点球 / Fresnel 球）」「shader 流场」——**这些是灵动背景层，不必是可巡游场景，广泛适用**；有空间主体的题材（建筑/天体/地形地貌）→ 「代码搭建 3D 漫游场景」；自然/人文/数据 → 「粒子流场」「Canvas-2D 星座」「shader 噪声」「CSS 程序化」。**别做静态渐变，也别一律粒子 / 一律 3D 漫游**——选最能表达本题材的那种。

### 代码搭建 3D 场景（建筑 / 地形 / 天体 —— 紫禁城级招牌）★高天花板
用参数化几何体在代码里搭出一个**真实的 3D 场景**当全场背景脊梁：BoxGeometry 砌台基/墙体、PlaneGeometry 铺水面/地面、Cone/Cylinder 做屋顶/竹木、Torus 做拱桥、Sphere 做山石/天体，配 Ambient+Directional+Point 三类光，全 deck 共用这一个常驻场景，翻页驱动相机沿弧线巡游（见「单一 3D 世界相机航点运镜」）。**建筑/文旅/天文/科学/产品题材的招牌王牌**，参考标杆（紫禁城/园林 3D 漫游）即此模式。

```js
const scene=new THREE.Scene(); scene.fog=new THREE.Fog(0x0b1a2a,40,160);   // 雾色配 --bg
const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,2)); renderer.setSize(1280,720);
const camera=new THREE.PerspectiveCamera(50,1280/720,.1,500);
scene.add(new THREE.AmbientLight(0x88aacc,.6));
const sun=new THREE.DirectionalLight(0xffe6b0,1.1); sun.position.set(40,60,30); scene.add(sun);
const M=c=>new THREE.MeshLambertMaterial({color:c});                       // 颜色全取 deck token
function building(x,z,w,h,d,roof){                                          // 参数化"一栋"
  const g=new THREE.Group();
  const base=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),M(0x7a3b2e)); base.position.y=h/2;
  const top=new THREE.Mesh(new THREE.ConeGeometry(w*0.85,h*0.5,4),M(roof)); // 四角攒尖顶
  top.position.y=h+h*0.25; top.rotation.y=Math.PI/4;
  g.add(base,top); g.position.set(x,0,z); return g;
}
for(let i=0;i<12;i++) scene.add(building((i%4-1.5)*16,(Math.floor(i/4)-1)*20,
  10,6+Math.random()*6,8,0x123a2a));                                        // 12+ 实体堆出院落
scene.add(new THREE.Mesh(new THREE.PlaneGeometry(400,400),M(0x0e2233))      // 水/地面
  .rotateX(-Math.PI/2));
(function loop(){ requestAnimationFrame(loop); renderer.render(scene,camera); })();
```

参数：实体 ≥10 个才有"场景"感（紫禁城级 50–180 个 mesh）；几何体复用 `Group`+循环生成，别手写一堆；光三件套（环境+主平行光+点光暖调）缺一场景就发灰；相机 fov 45–55、雾色必须等于 `--bg` 否则远景出"硬边"。
坑：锁 Three.js r128（见 SKILL §8）；`MeshLambert/Phong` 必须有光否则全黑；几何体在骨架期一次性建好，逐页只移相机不重建场景；`pixelRatio` 封顶 2 防移动端卡死；canvas 放 `#bg-layer`、z-index 最低。

### 背景-前景分离 scrim（3D / 重动态背景 deck 的内容页必用）
全屏 3D / 粒子背景上放 SVG 图解、密集标注或数据表时，前景**必须自带底板**，否则背景的高光/几何体/游动粒子从笔画缝隙透上来与前景线条竞争、正文糊成一团。**不要全局压暗背景**（会杀死封面/章节页的 3D），只在前景容器局部托底，并按页型给背景降密。

```css
/* 软边径向 scrim：托住图解又不切硬方框，3D 仍从四周透出（首选） */
.diagram-wrap{position:relative;background:radial-gradient(70% 70% at 50% 50%,
  rgba(12,16,20,.85) 0%, rgba(12,16,20,.55) 60%, rgba(12,16,20,0) 100%)}  /* rgba 用 --bg 同色 */
/* 信息密度高时用卡片 + backdrop-filter：blur 把背景高频细节糊掉，线条立刻浮出 */
.data-card{background:linear-gradient(180deg,rgba(12,16,20,.78),rgba(12,16,20,.9));
  backdrop-filter:blur(6px);border:1px solid rgba(255,255,255,.08)}
```
```js
// 按页型给背景降密：进内容/数据页压低粒子与高光，翻回封面恢复
function bgIntensity(type){ const dim = (type==='content'||type==='data');
  dust.material.opacity = dim ? .25 : .55;        // 微尘
  if(glow) glow.intensity = dim ? .5 : 1.8; }     // 主光/辉光
```
参数：scrim 中心 alpha .8–.9、60% 处 .5、边缘 0；卡片底 .75–.92 + blur 5–8px；内容页粒子 opacity 砍到 ~.25–.3、glow 砍半。
坑：**绝不允许裸 `<svg><g stroke>` 直接挂 `.slide`**（背景必透上来）；scrim/卡片 rgba 必须用 `--bg` 同色（异色发灰）；backdrop-filter 每块一次离屏合成，密集页 ≤ 几块；**封面/章节页别加这些底板**（要露出完整 3D）；stroke-opacity ≥ .5、线宽 ≥ 1.2 再淡也别低于背景对比。

### 2D canvas 氛围粒子（辉光浮尘 / 三层视差星空）
几十个极慢速辉光点全局漂移，立刻让深色 deck"活"起来。**最轻量的一种背景，不是默认答案**——题材能承载 3D/沉浸时优先上重型招牌，这个用于真不需要具象空间的场合。**庄重档可用**（粒子少、速度慢、低 alpha）。

```js
const colors=['rgba(94,234,212,','rgba(167,139,250,','rgba(244,114,182,'];  // 换成 deck 主题色
const ps=Array.from({length:42},()=>({x:Math.random()*1280,y:Math.random()*720,
  vx:(Math.random()-.5)*.18, vy:(Math.random()-.5)*.18,
  r:Math.random()*1.6+.4, a:Math.random()*.5+.25, c:colors[(Math.random()*3)|0]}));
(function draw(){
  ctx.clearRect(0,0,1280,720);
  for(const p of ps){
    p.x+=p.vx; p.y+=p.vy;
    if(p.x<-5)p.x=1285; if(p.x>1285)p.x=-5;            // 出界回绕
    if(p.y<-5)p.y=725;  if(p.y>725)p.y=-5;
    ctx.fillStyle=p.c+p.a+')'; ctx.shadowColor=p.c+'1)'; ctx.shadowBlur=8;
    ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,Math.PI*2); ctx.fill();
  }
  ctx.shadowBlur=0;                                    // 每帧用完复位
  requestAnimationFrame(draw);
})();
```

参数：30–60 个；速度 <0.2px/帧（再快就是雪花不是氛围）；alpha .25–.75；shadowBlur 6–10；星空变体分三层（180/90/40 颗，速度比 1:3:7，近层加光晕）做深度视差。
坑：shadowBlur 是 canvas 最贵状态，粒子 ≤60 且每帧复位；canvas 固定 1280×720 放最底层 z-index、不自适应窗口。

### 纯 CSS 纹理层（CRT 扫描线 / 半调网点 + mask 渐隐）
repeating 渐变做 CRT 扫描线，或漫画/波普风的半调网点，mask 让纹理向版心强烈渐隐。零 JS 零资源。**庄重档可用**（低 opacity 单层）。

> **禁用：网格类背景**——方格纸 / 蓝图网格（`background-size:Npx Npx` 的方格平铺）/ 透视网格地面 / 规则点阵满铺，**一律不要**（被严重滥用的 AI 套路，见使用说明第 7 条）。要纵深用渐变光晕 / shader 噪声 / 粒子流场。半调网点仅限漫画·波普风作为**风格纹理**，且必须 mask 向版心强渐隐、绝不满铺当通用底纹。

```css
/* CRT 扫描线（赛博/复古屏幕感）：横向细线，screen 混合，叠 radial 暗角 */
.deck::before{content:'';position:absolute;inset:0;pointer-events:none;z-index:1;
  background-image:repeating-linear-gradient(0deg,rgba(0,229,255,.05) 0 1px,transparent 1px 4px);
  mix-blend-mode:screen;
  -webkit-mask-image:radial-gradient(120% 120% at 50% 50%,#000 55%,transparent 100%);
          mask-image:radial-gradient(120% 120% at 50% 50%,#000 55%,transparent 100%)}
/* 半调网点（仅漫画/波普风，强渐隐、不满铺）：
   background-image:radial-gradient(var(--accent) 1.4px,transparent 1.6px);background-size:14px 14px;
   opacity:.12; mask-image:linear-gradient(135deg,#000 25%,transparent 60%)  ← 必须强渐隐 */
```

参数：扫描线 1px 线 / 3–4px 间距、alpha .04–.06、screen 混合；半调点径 1.2–1.8px、间距 12–26px、opacity ≤.15 且强 mask 渐隐。
坑：**任何 `background-size:Npx Npx` 的方格平铺都算网格底纹，禁用**；纹理层 pointer-events:none 且 z-index 低于 slide；半调只在漫画/波普风出现，别当通用背景。

### 玻璃碎片漂浮 + 高光扫掠
blur 大色斑垫底，5 片 backdrop-filter 玻璃碎片各自慢速漂移，叠 7s 循环斜向高光。**glassmorphism / 优雅杂志风封面标配**，克制可入庄重档。

```css
.deck::before{content:'';position:absolute;width:600px;height:600px;border-radius:50%;
  background:var(--accent);top:-200px;left:-180px;filter:blur(90px);opacity:.32}
.shard{position:absolute;border-radius:16px;overflow:hidden;
  background:linear-gradient(135deg,rgba(111,177,255,.18),rgba(179,136,255,.07));
  backdrop-filter:blur(14px);border:1px solid rgba(255,255,255,.18);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.25),0 30px 60px rgba(0,0,0,.35)}
.shard::after{content:'';position:absolute;inset:0;
  background:linear-gradient(115deg,transparent 28%,rgba(255,255,255,.22) 50%,transparent 72%);
  animation:sweep 7s linear infinite}
@keyframes sweep{from{transform:translateX(-120%)}to{transform:translateX(120%)}}
@keyframes drift1{0%,100%{transform:translate(0,0) rotate(14deg)}
  50%{transform:translate(18px,-26px) rotate(17deg)}}
/* 每片不同 driftN 时长 7–11s，其中一片加 reverse 去同步 */
```

参数：碎片 4–6 片、90–300px；drift 振幅 10–26px、旋转摆动 ±3–5°；色斑 blur 80–100px、opacity .25–.35。
坑：backdrop-filter 每片一次离屏合成，≤6 片；各片时长必须错开+一片 reverse，否则全场同步呼吸非常假；漂移振幅 >30px 像漂走的 bug。

### 流动线 + 曲线粒子流
虚线 dashoffset 无限流动（纯 CSS）或 Three.js CatmullRom 曲线上的光点河，表达路线/流程/数据流/能量流。**SVG 版庄重档可用**。

```css
.flow{fill:none;stroke-width:2.4;stroke-linecap:round;
  stroke-dasharray:8 7;animation:flow 2.6s linear infinite}
@keyframes flow{to{stroke-dashoffset:-90}}   /* 90 = (8+7)×6，必须取周期整数倍才无缝 */
```
```js
// Three.js 版：粒子按各自相位沿曲线推进
const curve=new THREE.CatmullRomCurve3(waypoints,false,'catmullrom',0.4);
for(let i=0;i<N;i++){
  prog[i]+=dt*0.13; if(prog[i]>1) prog[i]-=1;          // -=1 回绕保持间距不抖
  const p=curve.getPoint(prog[i]);
  pos.set([p.x, p.y+Math.sin(t*2+i*.3)*.12, p.z], i*3); // 正弦浮动
}
geo.attributes.position.needsUpdate=true;               // 每帧必须
// 材质固定搭配：AdditiveBlending + depthWrite:false + transparent
```

参数：dash 6–10/gap 5–8、周期 2–3.5s 必须 linear；粒子 24–300、流速 0.1–0.25 进度/秒、曲线张力 0.3–0.5。
坑：offset 非周期整数倍每圈结尾跳一下；流向由 path 绘制方向决定；Additive 粒子不配 depthWrite:false 会出黑色方块遮挡。

### 负 delay 预热主题粒子喷发
配置表批量生成多层 DOM/SVG 粒子（烟/火/花瓣/气泡）各挂无限循环 keyframes，animationDelay 取负随机值让首帧即满场。**仅自由档**，持续氛围主视觉（火山/烟花/蒸汽/香火）。

```js
const layers=[ {count:14,cls:'smoke',size:[140,260],speed:[14,22]},
               {count:22,cls:'spark',size:[8,16],  speed:[2.5,4.2]} ];
layers.forEach(cfg=>{
  for(let i=0;i<cfg.count;i++){
    const p=document.createElement('div'); p.className=cfg.cls;
    const sz=rand(cfg.size), dur=rand(cfg.speed);
    p.style.width=p.style.height=sz+'px';
    p.style.left=spawnX()+'px';
    p.style.animationDuration=dur+'s';
    p.style.animationDelay=(-Math.random()*dur)+'s';   // 负延迟 = 首帧满场，灵魂所在
    holder.appendChild(p);
  }
});
/* 每类一条循环 keyframes，首尾帧 opacity:0 保证循环接缝不可见 */
```

参数：单层 10–25、全场 DOM 粒子 ≤70；快慢层速度差 ≥3 倍拉纵深；blur ≤12px、大粒子 ≤15 个；轨迹随机参数走 CSS 变量。
坑：不加负 delay 开场是尴尬的"空场逐渐冒烟"；动画只绑 `.slide.active` 下离页即停；工厂函数判 childElementCount 幂等防重复插入。

### 3D 主视觉天体（节点球 / Fresnel 线框地球 / fbm 恒星）
旋转的 3D 球体主视觉：2D canvas 手写神经节点球（零依赖）、Three.js 经纬线框球 + BackSide 菲涅尔辉光壳、或 GLSL fbm 沸腾恒星。**科技/AI/地理/天文档封面王牌**；也可**只作灵动背景层**用在任何科技/抽象/数据/网络题材的 deck 上（不必整套走沉浸漫游）。

```js
// 节点球（零依赖）：200 节点球壳分布，初始化时一次性算 k=3 近邻连边（O(N²) 严禁进 draw 循环）
// 每帧双轴旋转 + 透视投影 p=620/(620+z)，边透明度 clamp(.4-avgZ/800, .04, .4)
// Fresnel 辉光壳（Three.js 版）：
const halo=new THREE.Mesh(new THREE.SphereGeometry(R*1.05,64,64), new THREE.ShaderMaterial({
  vertexShader:`varying vec3 vN;void main(){vN=normalize(normalMatrix*normal);
    gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
  fragmentShader:`varying vec3 vN;void main(){float r=pow(1.0-abs(vN.z),3.0);
    gl_FragColor=vec4(vec3(.58,.84,.7),r*.45);}`,       // 颜色换 deck 主题色
  transparent:true, side:THREE.BackSide, depthWrite:false,
  blending:THREE.AdditiveBlending}));
scene.add(halo);
```

参数：节点 150–250、近邻 k 2–3、转速 0.003–0.005 rad/帧；辉光壳半径 ×1.03–1.1、Fresnel 指数 2.5–3.5；fbm 恒星 5-octave（移动端降 3–4）；可加 UnrealBloom（strength ~1.0、threshold .15）整体提档。
坑：辉光壳三件套 BackSide+transparent+Additive 缺一即糊死球面；canvas 内部分辨率开 2 倍保证线条锐利；pixelRatio 封顶 2；多页复用时共享构建函数、参数切配色。

## 交互彩蛋（interaction）

### data-depth 分层鼠标视差（DOM / 3D 相机 lerp）
卡片按各自深度随鼠标错动，或 3D 相机向鼠标方向 lerp。廉价但高级感明显。**幅度取下限可入庄重档**。

```js
deck.addEventListener('mousemove', e=>{
  const r=deck.getBoundingClientRect();
  const mx=(e.clientX-r.left-r.width/2)/r.width, my=(e.clientY-r.top-r.height/2)/r.height;
  document.querySelectorAll('.slide.active .parallax').forEach(el=>{
    const d=parseFloat(el.dataset.depth||1);          // <div class="parallax" data-depth=".5">
    el.style.transform=`translate(${mx*12*d}px,${my*12*d}px)`;
  });
});
deck.addEventListener('mouseleave', ()=>
  document.querySelectorAll('.parallax').forEach(el=>el.style.transform=''));
// 3D 版：camera.position.x += (mx*0.5 - camera.position.x)*0.05  指数趋近，离开自动归位
// 或不污染朝向技：camera.position.add(off); camera.lookAt(target); camera.position.sub(off);
```

参数：基础幅度 8–16px（庄重档 ≤8px）；depth 0.5–1.6 分 2–3 档；3D 趋近系数 .04–.08；每页 parallax 元素 <10。
坑：直接覆写 inline transform，被视差元素不能再靠 transform 布局/居中；mouseleave 必须全量复位防翻页残留偏移。

### 双向 hover 联动（dim 其余 + 发光高亮 / 硬阴影详情面板）
列表与图形靠共享 data-id 双向联动：hover 任一侧压暗其余、高亮匹配项发光；变体为 hover 卡片磁吸抬起+右侧详情面板实时切换。**庄重档可用**（地图/图表/架构图页）。

```css
.map.dim .item:not(.hl){opacity:.18}
.item.hl{stroke-width:4;filter:drop-shadow(0 0 6px currentColor)}
.item{transition:opacity .35s,stroke-width .35s}
/* neo-brutalist 变体：.cell:hover,.cell.act{transform:translate(-3px,-3px);
   box-shadow:6px 6px 0 var(--ink)}  0 模糊硬阴影=磁吸抬起 */
```
```js
terms.forEach(t=>{
  t.addEventListener('mouseenter',()=>{ map.classList.add('dim');
    items.forEach(c=>c.classList.toggle('hl', c.dataset.id===t.dataset.id)); });
  t.addEventListener('mouseleave',()=>{ map.classList.remove('dim');
    items.forEach(c=>c.classList.remove('hl')); });
});
```

参数：压暗 opacity .15–.25；高亮线宽 ×1.5–2、drop-shadow 4–8px 用 currentColor；过渡 .3–.4s；硬阴影偏移=位移 2 倍、模糊恒 0。
坑：dim 挂容器 + `:not(.hl)` 排除，比 JS 逐个改样式干净；mouseleave 必须清干净 dim 和 hl；deck 级点击翻页监听要 `e.target.closest(...)` 排除这些交互区。

### Raycaster 点击聚焦 + 信息卡滑入
3D 场景点击目标→相机飞向环绕位+毛玻璃信息卡滑入，点空白复位。**3D deck 的核心交互闭环**（产品展示/星系/地图探索）。

```js
cv.addEventListener('mousedown',e=>{down={x:e.clientX,y:e.clientY};drag=false});
cv.addEventListener('mousemove',e=>{ if(down &&
  (e.clientX-down.x)**2+(e.clientY-down.y)**2>30) drag=true; });
cv.addEventListener('mouseup',e=>{ if(!drag) pick(e); down=null; });   // 拖拽松手不算点击
function pick(e){
  const r=cv.getBoundingClientRect();
  mouse.set(((e.clientX-r.left)/r.width)*2-1, -((e.clientY-r.top)/r.height)*2+1);
  ray.setFromCamera(mouse,camera);
  let obj=ray.intersectObjects(targets,true)[0]?.object;
  while(obj && !obj.userData.info) obj=obj.parent;     // 命中子 mesh，向上爬找业务数据
  focused=obj||null; card.classList.toggle('show',!!obj);
}
// 每帧：focused 时 camera.position.lerp(环绕位,0.06) + lookAt(focused.position)
// CSS：.card{opacity:0;transform:translateX(20px);transition:.4s;pointer-events:none}
```

参数：拖拽判别阈值 25–50（位移平方）；相机趋近 .05–.08 或 1.2–1.8s cubic ease-out 飞行；环绕距离=目标半径×3–5+常数；ESC 也绑关闭。
坑：不判别 drag/click 旋转松手即误选中；小目标配 visible:false 的大号隐形碰撞体；点空白必须清 focused 否则相机锁死；聚焦期间关 autoRotate、关卡后恢复。

### 光标辉光团 / 主题自定义光标
两团错位模糊光斑带拖尾跟随鼠标（screen 混合发光），或 cursor:none 换成主题小动物/粒子群弹簧跟随。**仅自由档**（暗色科技 / 主题叙事）。

```css
.bloom{position:absolute;width:520px;height:520px;border-radius:50%;pointer-events:none;
  background:radial-gradient(circle,rgba(0,229,255,.18) 0%,transparent 60%);
  filter:blur(30px);mix-blend-mode:screen;will-change:transform;
  transition:transform .35s cubic-bezier(.2,.8,.3,1)}   /* transition 即拖尾 */
```
```js
document.addEventListener('mousemove',e=>{
  const r=deck.getBoundingClientRect(), sc=r.width/1280;   // 必须反算回 deck 坐标系
  const x=(e.clientX-r.left)/sc, y=(e.clientY-r.top)/sc;
  bloom1.style.transform=`translate(${x-260}px,${y-260}px)`;
  bloom2.style.transform=`translate(${x-210}px,${y-290}px)`;  // 第二团错位制造体积
});
// 主题光标变体：弹簧跟随 v=v*0.82+(target-pos)*0.06，朝向 atan2(vy,vx)，尾迹 8–12 帧
```

参数：光团 400–600px、blur 24–36px、中心 alpha .12–.20；拖尾 transition .3–.4s；弹簧阻尼 .8–.86、系数 .05–.08。
坑：deck 被 transform:scale 后坐标必须 ÷ 实时缩放比，否则光团不跟手；screen 混合+blur 缺一就成死色块；cursor:none 后所有可点元素必须有 hover 反馈代偿。

### 控件三联反馈（数值 flash + 图形重构 + 粒子 burst）
slider/按钮/点击改变参数时三层即时反馈：数值实时重算、数字发光脉冲、图形重建并喷一波光点。把参数变化变成"打到了"的手感。**演示/教学/数据交互页**，burst 部分仅自由档。

```js
slider.addEventListener('input', e=>{
  val.textContent = fmt(compute(+e.target.value));   // 1. 公式数值联动
  val.classList.add('flash');                        // 2. .flash{transform:scale(1.05);
  setTimeout(()=>val.classList.remove('flash'),320); //    color/text-shadow 用强调色}
  rebuild(+e.target.value);                          // 3. 重建图形（内部先 dispose 旧物）
  burst(24);                                         //    + 同步粒子爆发
});
// 粒子池：life 每帧 -=0.018，opacity=life；死亡 remove + material.dispose()
// DOM 版 burst：初速 ±10px/帧、gravity .25、life 80–120 帧、最后 30 帧 alpha 衰减
```

参数：burst 16–32 颗、约 0.7–1.1s 消亡；flash 250–400ms 与 CSS transition 匹配；发光贴图必须缓存复用。
坑：Three.js 粒子死亡必须 dispose 防 GPU 泄漏；deck 全局点击翻页监听必须排除控件区域；连续拖动靠粒子池上限兜底。

### 鼠标驱动文字色差（glitch 彩蛋）
按光标偏心给全 deck 设一对反向红/蓝 text-shadow，形成跟随鼠标的亚像素 RGB 错位。**仅自由档**（CRT/赛博/故障风），一行 inline style 全场生效。

```js
addEventListener('mousemove', e=>{
  const r=deck.getBoundingClientRect();
  const dx=(e.clientX-r.left-r.width/2)/r.width, dy=(e.clientY-r.top-r.height/2)/r.height;
  deck.style.textShadow=
    `${dx*.6}px ${dy*.6}px 0 rgba(255,80,80,.35), `+
    `${-dx*.6}px ${-dy*.6}px 0 rgba(80,180,255,.35)`;   // 两道必须方向相反
});
```

参数：错位系数 0.3–1px（再大正文糊掉）；红/蓝对 alpha .3–.4。
坑：靠 text-shadow 继承生效，自带 text-shadow 的标题会覆盖它——恰好形成"正文轻微色差、标题保持辉光"的自然分层；勿用 filter:drop-shadow 实现（整层重绘贵一个量级）。
